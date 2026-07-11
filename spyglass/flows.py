"""SpyGlass orchestration — Abhay's flow contract, n8n architecture in code.

DAILY FLOW (cron or /spy check):
  Part A — NEW POSTS (24h window):
    load active socials -> skip platforms we don't have ->
    Apify postedLimit="24h" (max 20 posts) -> normalize -> dedup -> save new.
    If nothing new AND nothing to growth-check -> do nothing (no AI call, no Slack noise).
  Part B — GROWTH RE-CHECK (uses last_checked_at, NOT last_scraped_at):
    posts whose last_checked_at <= now-7d -> re-scrape those exact post URLs ->
    snapshot engagement -> update last_checked_at.
  Part C — ONE AI call over the whole batch -> Slack brief + Word doc.
"""
import datetime as dt

from . import db, sources, ai, report

MAX_DAILY_POSTS = 20        # Abhay: only 20 posts max per 24h scan
GROWTH_INTERVAL_DAYS = 7    # re-check engagement weekly per post
MAX_COMMENTS = 5


def _now():
    return dt.datetime.now(dt.timezone.utc)


# ---------- normalizers (platform output -> unified posts row) ----------
def normalize_linkedin(item: dict, social: dict) -> dict:
    eng = item.get("engagement") or {}
    posted = (item.get("postedAt") or {}).get("timestamp")
    posted_iso = (dt.datetime.fromtimestamp(posted / 1000, dt.timezone.utc).isoformat()
                  if isinstance(posted, (int, float)) else (item.get("postedAt") or {}).get("date"))
    likes = eng.get("likes") or 0
    comments = eng.get("comments") or 0
    shares = eng.get("shares") or 0
    media_urls = item.get("postImages") or []
    media_type = "image" if media_urls else ("document" if item.get("document") else "text")
    return {
        "social_id": social["id"],
        "competitor_id": social["competitor_id"],
        "platform": "linkedin",
        "post_url": item.get("linkedinUrl"),
        "external_id": str(item.get("id") or ""),
        "content": item.get("content"),
        "media_type": media_type,
        "media_urls": media_urls,
        "posted_at": posted_iso,
        "likes": likes, "comments": comments, "shares": shares,
        "views": None,
        "engagement_total": likes + comments + shares,
        "raw": item,
        "last_checked_at": _now().isoformat(),
    }


# ---------- Part A: scan for new posts (24h) ----------
def _split_posts_comments(items: list):
    """Actor emits comments as separate items (type: post|comment).
    Keep posts; attach each comment to its parent post via the post id in its URL."""
    posts = [i for i in items if i.get("type") == "post"]
    comments = [i for i in items if i.get("type") == "comment"]
    for p in posts:
        pid = str(p.get("id") or "")
        p["scraped_comments"] = [
            {"text": c.get("content") or c.get("text"),
             "author": (c.get("author") or {}).get("name")}
            for c in comments if pid and pid in str(c.get("linkedinUrl") or "")
        ]
    return posts


def scan_new_posts(name_filter: str = None, posted_limit: str = "24h",
                   max_posts: int = MAX_DAILY_POSTS) -> list:
    new_rows = []
    for social in db.get_active_socials():
        if social["platform"] != "linkedin":
            continue  # more platforms wired later; don't scrape what we can't handle
        comp_name = (social.get("competitors") or {}).get("name", "")
        if name_filter and name_filter.lower() not in comp_name.lower():
            continue
        items = sources.linkedin_posts_windowed(
            [social["handle_url"]], posted_limit=posted_limit,
            max_posts=max_posts, max_comments=MAX_COMMENTS,
        )
        for item in _split_posts_comments(items):
            url = item.get("linkedinUrl")
            if not url or db.post_exists(url):
                continue
            row = normalize_linkedin(item, social)
            saved = db.save_post(row)
            if saved:
                new_rows.append(saved[0] if isinstance(saved, list) else row)
        db.update_last_scraped(social["id"], _now().isoformat())
    return new_rows


# ---------- Part B: growth re-check (7-day, via last_checked_at) ----------
def growth_recheck() -> list:
    cutoff = (_now() - dt.timedelta(days=GROWTH_INTERVAL_DAYS)).isoformat()
    due = db.posts_due_for_check(cutoff)
    if not due:
        return []
    url_map = {p["post_url"]: p for p in due}
    items = sources.linkedin_posts_windowed(list(url_map.keys()),
                                            posted_limit="any", max_posts=1)
    updates = []
    for item in items:
        post = url_map.get(item.get("linkedinUrl"))
        if not post:
            continue
        eng = item.get("engagement") or {}
        likes, comments, shares = (eng.get("likes") or 0, eng.get("comments") or 0,
                                   eng.get("shares") or 0)
        db.add_snapshot(post["id"], likes=likes, comments=comments, shares=shares)
        db.refresh_post_metrics(post["id"], likes, comments, shares, _now().isoformat())
        updates.append({
            "post_url": post["post_url"], "competitor_id": post["competitor_id"],
            "previous": {"likes": post.get("likes"), "comments": post.get("comments"),
                          "shares": post.get("shares")},
            "current": {"likes": likes, "comments": comments, "shares": shares},
            "posted_at": post.get("posted_at"),
        })
    return updates


# ---------- Content Spy deep-dive: /spy analyze <name> ----------
def run_deep_analysis(slack_client, channel: str, name: str,
                      tone: str = "default") -> str:
    """Pull a month of the competitor's content -> ONE AI dossier pass -> Slack + docx."""
    scan_new_posts(name_filter=name, posted_limit="month", max_posts=30)
    posts = db.get_posts_for_competitor_name(name)
    if not posts:
        return "none"
    result = ai.dossier(name, posts, tone=tone)
    comp_names = {c["id"]: c["name"] for c in
                  db.sb().table("competitors").select("id,name").execute().data}
    from . import render
    blocks = render.build_dossier_blocks(name, result, len(posts))
    docx_path = report.build_dossier_docx(name, result, posts, comp_names)
    slack_client.chat_postMessage(channel=channel, blocks=blocks,
                                  text=f"SpyGlass Content Dossier — {name}")
    try:
        slack_client.files_upload_v2(channel=channel, file=docx_path,
                                     title=f"SpyGlass Dossier — {name}",
                                     initial_comment="🗂️ Full content-spy dossier attached.")
    except Exception as e:
        print(f"[flows] dossier docx upload failed: {e}")
    return "sent"


# ---------- Part C: one AI pass -> Slack ----------
def run_daily(slack_client, channel: str, tone: str = "default",
              name_filter: str = None) -> str:
    new_posts = scan_new_posts(name_filter=name_filter)
    growth = growth_recheck()

    if not new_posts and not growth:
        return "quiet"  # Abhay: no post in 24h + nothing due -> do nothing

    result = ai.daily_brief(new_posts, growth, tone=tone)

    # write per-post analysis back to DB (code-node guard already parsed JSON)
    for p in result.get("posts", []):
        db.update_post_analysis(p.get("post_url"), p)

    comp_names = {c["id"]: c["name"] for c in
                  db.sb().table("competitors").select("id,name").execute().data}
    from . import render
    blocks = render.build_daily_blocks(result, new_posts, comp_names)

    docx_path = report.build_docx(result, new_posts, growth, comp_names)
    resp = slack_client.chat_postMessage(
        channel=channel, blocks=blocks,
        text=f"SpyGlass Daily Intel — {len(new_posts)} new post(s)")
    if docx_path:
        try:
            slack_client.files_upload_v2(channel=channel, file=docx_path,
                                         title="SpyGlass Daily Intel",
                                         initial_comment="📄 Full breakdown attached.")
        except Exception as e:
            print(f"[flows] docx upload failed (scope?): {e}")
    db.save_daily_brief([p.get("competitor_id") for p in new_posts],
                        result.get("overall_pattern", ""), docx_path, resp["ts"])
    return "sent"
