"""DEMO/TEST TOOL — fabricate a 'week ago' baseline so the 7-day growth loop
can be tested today without waiting a week.

For each of a competitor's stored posts:
  1. record the REAL current engagement,
  2. write a metric_snapshot with a fabricated LOWER value dated 7 days ago,
  3. set the post's stored numbers to that lower value,
  4. backdate last_checked_at to 8 days ago.

Then `growth_recheck()` (or /spy check) re-scrapes the REAL current numbers and
shows the growth: fabricated-past -> real-now.

Usage:  python tools/seed_weekly.py "hubspot"  [factor]
        factor = fraction of current used as the week-ago baseline (default 0.6)
"""
import sys
import os
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv  # noqa: E402
load_dotenv()
from spyglass import db  # noqa: E402


def seed(name: str, factor: float = 0.6):
    posts = db.get_posts_for_competitor_name(name)
    if not posts:
        print(f"No posts stored for '{name}'. Run /spy check {name} first.")
        return
    week_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).isoformat()
    eight_days = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)).isoformat()
    n = 0
    for p in posts:
        real = {"likes": p.get("likes") or 0, "comments": p.get("comments") or 0,
                "shares": p.get("shares") or 0, "views": p.get("views")}
        fake = {k: int((v or 0) * factor) if k != "views" else
                (int(v * factor) if v else None) for k, v in real.items()}
        # 1) snapshot the fabricated week-ago baseline
        db.sb().table("metric_snapshots").insert({
            "post_id": p["id"], "captured_at": week_ago,
            "likes": fake["likes"], "comments": fake["comments"],
            "shares": fake["shares"], "views": fake["views"],
        }).execute()
        # 2) set stored numbers to the baseline + backdate the clock
        db.sb().table("posts").update({
            "likes": fake["likes"], "comments": fake["comments"], "shares": fake["shares"],
            "views": fake["views"],
            "engagement_total": fake["likes"] + fake["comments"] + fake["shares"],
            "last_checked_at": eight_days,
        }).eq("id", p["id"]).execute()
        n += 1
        print(f"  seeded {p['post_url'][:60]}  now~{real['likes']} -> baseline {fake['likes']} likes")
    print(f"[done] {n} posts baselined for '{name}'. "
          f"Now run the growth re-check to see real-vs-baseline growth.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/seed_weekly.py \"<competitor name>\" [factor]")
        sys.exit(1)
    seed(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.6)
