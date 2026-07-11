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
