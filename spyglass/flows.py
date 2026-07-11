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
def _base_row(social, platform, post_url, external_id, content, media_type,
              media_urls, posted_iso, likes, comments, shares, views, raw):
    likes, comments, shares = likes or 0, comments or 0, shares or 0
    return {
        "social_id": social["id"], "competitor_id": social["competitor_id"],
        "platform": platform, "post_url": post_url, "external_id": str(external_id or ""),
        "content": content, "media_type": media_type, "media_urls": media_urls or [],
        "posted_at": posted_iso, "likes": likes, "comments": comments, "shares": shares,
        "views": views, "engagement_total": likes + comments + shares,
        "raw": raw, "last_checked_at": _now().isoformat(),
    }


def normalize_linkedin(item: dict, social: dict) -> dict:
    eng = item.get("engagement") or {}
    posted = (item.get("postedAt") or {}).get("timestamp")
    posted_iso = (dt.datetime.fromtimestamp(posted / 1000, dt.timezone.utc).isoformat()
                  if isinstance(posted, (int, float)) else (item.get("postedAt") or {}).get("date"))
    media_urls = item.get("postImages") or []
    media_type = "image" if media_urls else ("document" if item.get("document") else "text")
    return _base_row(social, "linkedin", item.get("linkedinUrl"), item.get("id"),
                     item.get("content"), media_type, media_urls, posted_iso,
                     eng.get("likes"), eng.get("comments"), eng.get("shares"), None, item)


def normalize_instagram(item: dict, social: dict) -> dict:
    ts = item.get("timestamp")  # ISO string
    t = (item.get("type") or "").lower()
    media_type = "video" if t == "video" else ("carousel" if t == "sidecar" else "image")
    media_urls = [u for u in [item.get("displayUrl"), item.get("videoUrl")] if u]
    return _base_row(social, "instagram", item.get("url"), item.get("id"),
                     item.get("caption"), media_type, media_urls, ts,
                     item.get("likesCount"), item.get("commentsCount"), None,
                     item.get("videoViewCount"), item)


def normalize_twitter(item: dict, social: dict) -> dict:
    created = item.get("createdAt")  # "Wed Jan 14 17:17:06 +0000 2026"
    try:
        posted_iso = dt.datetime.strptime(created, "%a %b %d %H:%M:%S %z %Y").isoformat()
    except Exception:
        posted_iso = None
    media = item.get("media") or []
    media_urls = [m.get("url") for m in media if isinstance(m, dict) and m.get("url")]
    media_type = "video" if any((m.get("type") or "").startswith("video") for m in media if isinstance(m, dict)) else ("image" if media_urls else "text")
    return _base_row(social, "twitter", item.get("url"), item.get("id"),
                     item.get("fullText") or item.get("text"), media_type, media_urls,
                     posted_iso, item.get("likeCount"), item.get("replyCount"),
                     item.get("retweetCount"), None, item)


def normalize_website(url: str, title: str, social: dict) -> dict:
    return _base_row(social, "website", url, url, title, "article", [url], None,
                     None, None, None, None, {"source_url": url})


def _slug_title(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1].split("?")[0].split("#")[0]
    return slug.replace("-", " ").replace("_", " ").strip().title() or url


def _website_articles(scrape_result, base_url: str, limit: int = 12) -> list:
    """Extract likely article/update links from a Firecrawl scrape of a site."""
    from urllib.parse import urlparse
    data = scrape_result.get("data", scrape_result) if isinstance(scrape_result, dict) else {}
    links = data.get("links") or []
    base_host = urlparse(base_url).netloc.replace("www.", "")
    skip = ("tag/", "category/", "author/", "page/", "login", "signup", "pricing",
            "contact", "careers", "privacy", "terms")
    out, seen = [], set()
    for l in links:
        if not isinstance(l, str):
            continue
        pu = urlparse(l)
        if pu.netloc.replace("www.", "") != base_host:
            continue
        path = pu.path.strip("/")
        if not path or "/" not in path:          # want article-depth paths
            continue
        if any(x in path.lower() for x in skip):
            continue
        if l in seen:
            continue
        seen.add(l)
        out.append(l)
    return out[:limit]


def _within_window(posted_iso, cutoff) -> bool:
    if not posted_iso:
        return True  # keep if unknown; dedup still protects us
    try:
        posted = dt.datetime.fromisoformat(str(posted_iso).replace("Z", "+00:00"))
        return posted >= cutoff
    except Exception:
        return True


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


def _handle_slug(url: str) -> str:
    return url.rstrip("/").split("/")[-1].split("?")[0]


def scan_new_posts(name_filter: str = None, posted_limit: str = "24h",
                   max_posts: int = MAX_DAILY_POSTS, window_hours: int = 24) -> list:
    """Multi-platform incremental scan. LinkedIn uses server-side postedLimit;
    Instagram/X fetch latest N and filter by window in code. All dedup by post_url."""
    new_rows = []
    cutoff = _now() - dt.timedelta(hours=window_hours) if posted_limit == "24h" else \
        _now() - dt.timedelta(days=32)
    for social in db.get_active_socials():
        plat = social["platform"]
        comp_name = (social.get("competitors") or {}).get("name", "")
        if name_filter and name_filter.lower() not in comp_name.lower():
            continue

        if plat == "website":
            try:
                res = sources.website_scrape(social["handle_url"])
            except Exception as e:
                print(f"[scan] website scrape failed for {social['handle_url']}: {e}")
                continue
            for url in _website_articles(res, social["handle_url"]):
                if db.post_exists(url):
                    continue
                row = normalize_website(url, _slug_title(url), social)
                saved = db.save_post(row)
                if saved:
                    new_rows.append(saved[0] if isinstance(saved, list) else row)
            db.update_last_scraped(social["id"], _now().isoformat())
            continue

        if plat == "linkedin":
            items = _split_posts_comments(sources.linkedin_posts_windowed(
                [social["handle_url"]], posted_limit=posted_limit,
                max_posts=max_posts, max_comments=MAX_COMMENTS))
            norm, url_key = normalize_linkedin, "linkedinUrl"
        elif plat == "instagram":
            items = sources.instagram_posts([social["handle_url"]], results_limit=max_posts)
            items = [i for i in items if _within_window(i.get("timestamp"), cutoff)]
            norm, url_key = normalize_instagram, "url"
        elif plat == "twitter":
            items = sources.twitter_posts([_handle_slug(social["handle_url"])], max_items=max_posts)
            norm, url_key = normalize_twitter, "url"
        else:
            continue  # website handled by enrichment, not the post feed

        for item in items:
            url = item.get(url_key)
            if not url or db.post_exists(url):
                continue
            row = norm(item, social)
            saved = db.save_post(row)
            if saved:
                new_rows.append(saved[0] if isinstance(saved, list) else row)
        db.update_last_scraped(social["id"], _now().isoformat())
    return new_rows


# ---------- Part B: growth re-check (7-day, via last_checked_at) ----------
def growth_recheck(name_filter: str = None) -> list:
    cutoff = (_now() - dt.timedelta(days=GROWTH_INTERVAL_DAYS)).isoformat()
    due = db.posts_due_for_check(cutoff)
    if name_filter:
        ok_ids = {c["id"] for c in db.list_competitors_with_socials()
                  if name_filter.lower() in c["name"].lower()}
        due = [p for p in due if p["competitor_id"] in ok_ids]
    # LinkedIn re-check (the platform with reliable historical re-scrape)
    due = [p for p in due if p.get("platform") == "linkedin"]
    if not due:
        return []
    url_map = {p["post_url"]: p for p in due}
    items = sources.linkedin_posts_windowed(list(url_map.keys()),
                                            posted_limit="any",
                                            max_posts=max(len(url_map), 5))
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
            "content": post.get("content"),
            "previous": {"likes": post.get("likes"), "comments": post.get("comments"),
                          "shares": post.get("shares")},
            "current": {"likes": likes, "comments": comments, "shares": shares},
            "posted_at": post.get("posted_at"),
        })
    return updates


# ---------- Growth board: /spy chart <name> ----------
def run_chart(slack_client, channel: str, name: str) -> str:
    from . import render
    series = db.get_momentum_series(name)
    if not series:
        return "none"
    blocks = render.build_momentum_blocks(name.title(), series)
    slack_client.chat_postMessage(channel=channel, blocks=blocks,
                                  text=f"{name.title()} — momentum")
    return "sent"


# ---------- Weekly growth report: /spy weekly ----------
def run_weekly(slack_client, channel: str, tone: str = "default",
               name_filter: str = None) -> str:
    """Re-check posts due for a 7-day growth read, then post a growth report."""
    updates = growth_recheck(name_filter=name_filter)
    if not updates:
        return "none"
    from . import ai, render
    verdict = ai.growth_verdict(updates, tone=tone)
    blocks = render.build_growth_blocks(updates, verdict)
    slack_client.chat_postMessage(channel=channel, blocks=blocks,
                                  text="SpyGlass Weekly Growth Report")
    return "sent"


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
