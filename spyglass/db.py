"""Supabase data layer for SpyGlass. Matches supabase/schema.sql.
Pure DB ops — no API credits involved."""
import os
from supabase import create_client, Client

_sb = None


def sb() -> Client:
    global _sb
    if _sb is None:
        _sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    return _sb


# --- competitors ---------------------------------------------------------
def add_competitor(name, platform, handle_url, added_by=None,
                   slack_channel=None, website_url=None) -> dict:
    """Create competitor + its social handle. Dedup on handle_url."""
    existing = (sb().table("competitor_socials")
                .select("*, competitors(*)").eq("handle_url", handle_url).execute())
    if existing.data:
        return {"social": existing.data[0], "existed": True}

    comp = sb().table("competitors").insert({
        "name": name, "added_by": added_by, "slack_channel": slack_channel,
    }).execute()
    competitor_id = comp.data[0]["id"]

    social = sb().table("competitor_socials").insert({
        "competitor_id": competitor_id, "platform": platform,
        "handle_url": handle_url, "website_url": website_url,
    }).execute()
    return {"competitor": comp.data[0], "social": social.data[0], "existed": False}


def get_active_socials() -> list:
    """All social handles to scan on the daily run (with competitor info)."""
    return (sb().table("competitor_socials")
            .select("*, competitors(name, slack_channel)")
            .eq("active", True).execute().data)


def list_competitors_with_socials() -> list:
    """Grouped view for /spy edit: each competitor + its platforms."""
    comps = sb().table("competitors").select("id,name").order("created_at").execute().data
    socials = sb().table("competitor_socials").select(
        "id,competitor_id,platform,handle_url").execute().data
    by_comp = {}
    for s in socials:
        by_comp.setdefault(s["competitor_id"], []).append(s)
    for c in comps:
        c["socials"] = by_comp.get(c["id"], [])
    return comps


def add_social_to_competitor(competitor_id, platform, handle_url) -> None:
    existing = (sb().table("competitor_socials").select("id")
                .eq("handle_url", handle_url).execute().data)
    if existing:
        return
    sb().table("competitor_socials").insert({
        "competitor_id": competitor_id, "platform": platform, "handle_url": handle_url,
    }).execute()


def replace_social(social_id, new_platform, new_url) -> None:
    sb().table("competitor_socials").update({
        "platform": new_platform, "handle_url": new_url, "last_scraped_at": None,
    }).eq("id", social_id).execute()


def remove_social(social_id) -> None:
    sb().table("competitor_socials").delete().eq("id", social_id).execute()


def remove_competitor(competitor_id) -> None:
    sb().table("competitors").delete().eq("id", competitor_id).execute()


def get_competitor(competitor_id) -> dict:
    r = sb().table("competitors").select("id,name").eq("id", competitor_id).execute().data
    return r[0] if r else None


def update_last_scraped(social_id, iso_ts) -> None:
    sb().table("competitor_socials").update(
        {"last_scraped_at": iso_ts}).eq("id", social_id).execute()


# --- posts ---------------------------------------------------------------
def post_exists(post_url) -> bool:
    r = sb().table("posts").select("id").eq("post_url", post_url).execute()
    return bool(r.data)


def save_post(row: dict) -> dict:
    """Upsert a post; dedup on post_url."""
    return sb().table("posts").upsert(row, on_conflict="post_url").execute().data


def add_snapshot(post_id, likes=None, comments=None, shares=None, views=None) -> None:
    sb().table("metric_snapshots").insert({
        "post_id": post_id, "likes": likes, "comments": comments,
        "shares": shares, "views": views,
    }).execute()


def posts_due_for_check(cutoff_iso) -> list:
    """Posts whose last_checked_at is older than the cutoff (7-day growth loop)."""
    return (sb().table("posts").select("*")
            .lte("last_checked_at", cutoff_iso).execute().data)


def refresh_post_metrics(post_id, likes, comments, shares, checked_iso) -> None:
    sb().table("posts").update({
        "likes": likes, "comments": comments, "shares": shares,
        "engagement_total": (likes or 0) + (comments or 0) + (shares or 0),
        "last_checked_at": checked_iso,
    }).eq("id", post_id).execute()


def update_post_analysis(post_url, analysis: dict) -> None:
    sb().table("posts").update({
        "hook": analysis.get("hook"),
        "hook_type": analysis.get("hook_type"),
        "content_type": analysis.get("content_type"),
        "strategy": analysis.get("strategy"),
        "analysis": analysis,
    }).eq("post_url", post_url).execute()


def system_status() -> dict:
    """Counts for /spy status — the visibility view."""
    comps = sb().table("competitors").select("id", count="exact").execute()
    socials = sb().table("competitor_socials").select("id,platform,last_scraped_at").execute().data
    posts = sb().table("posts").select("id", count="exact").execute()
    briefs = sb().table("daily_briefs").select("id", count="exact").execute()
    return {
        "competitors": comps.count, "posts": posts.count, "briefs": briefs.count,
        "socials": socials,
    }


def leaderboard() -> list:
    """Aggregate engagement per competitor for /spy compare."""
    posts = sb().table("posts").select(
        "competitor_id,likes,comments,shares,engagement_total").execute().data
    comps = {c["id"]: c["name"] for c in
             sb().table("competitors").select("id,name").execute().data}
    agg = {}
    for p in posts:
        cid = p["competitor_id"]
        a = agg.setdefault(cid, {"name": comps.get(cid, "?"), "posts": 0,
                                 "likes": 0, "comments": 0, "shares": 0, "total": 0})
        a["posts"] += 1
        a["likes"] += p.get("likes") or 0
        a["comments"] += p.get("comments") or 0
        a["shares"] += p.get("shares") or 0
        a["total"] += p.get("engagement_total") or 0
    rows = list(agg.values())
    for r in rows:
        r["avg"] = round(r["total"] / r["posts"]) if r["posts"] else 0
    return sorted(rows, key=lambda r: r["avg"], reverse=True)


def get_momentum_series(name_fragment) -> list:
    """Aggregate engagement across ALL a competitor's posts, per week — momentum trend."""
    posts = get_posts_for_competitor_name(name_fragment)
    ids = [p["id"] for p in posts]
    if not ids:
        return []
    snaps = (sb().table("metric_snapshots")
             .select("captured_at,likes,comments,shares")
             .in_("post_id", ids).order("captured_at").execute().data)
    from collections import defaultdict
    buckets = defaultdict(lambda: {"likes": 0, "comments": 0, "shares": 0})
    for s in snaps:
        day = str(s["captured_at"])[:10]
        buckets[day]["likes"] += s.get("likes") or 0
        buckets[day]["comments"] += s.get("comments") or 0
        buckets[day]["shares"] += s.get("shares") or 0
    return [{"date": d, **v} for d, v in sorted(buckets.items())]


def get_snapshot_series(name_fragment) -> list:
    """Time-series engagement per post (from metric_snapshots) for charting."""
    posts = get_posts_for_competitor_name(name_fragment)
    series = []
    for p in posts:
        snaps = (sb().table("metric_snapshots")
                 .select("captured_at,likes,comments,shares")
                 .eq("post_id", p["id"]).order("captured_at").execute().data)
        if len(snaps) >= 2:  # need >=2 points to draw a growth line
            title = (p.get("content") or p.get("post_url") or "post").strip()
            series.append({"title": title[:34], "snaps": snaps})
    return series


def recent_posts_all(limit=30) -> list:
    return (sb().table("posts").select("*")
            .order("posted_at", desc=True).limit(limit).execute().data)


def get_posts_for_competitor_name(name_fragment) -> list:
    """All stored intel for /spy ask — competitor matched by name fragment."""
    comps = (sb().table("competitors").select("id,name")
             .ilike("name", f"%{name_fragment}%").execute().data)
    if not comps:
        return []
    ids = [c["id"] for c in comps]
    return (sb().table("posts").select("*")
            .in_("competitor_id", ids).order("posted_at", desc=True)
            .limit(30).execute().data)


# --- daily brief ---------------------------------------------------------
def save_daily_brief(competitor_ids, summary, docx_path=None, slack_ts=None) -> None:
    sb().table("daily_briefs").insert({
        "competitor_ids": competitor_ids, "summary": summary,
        "docx_path": docx_path, "slack_ts": slack_ts,
    }).execute()
