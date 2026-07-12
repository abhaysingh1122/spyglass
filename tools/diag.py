"""Diagnostic: competitors, their slack channels, socials, and latest post dates."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from spyglass import db

sb = db.sb()

print("=== COMPETITORS ===")
comps = sb.table("competitors").select("*").execute().data
for c in comps:
    print(f"  id={c['id']}  name={c.get('name')!r}  added_by={c.get('added_by')!r}  slack_channel={c.get('slack_channel')!r}")

print("\n=== SOCIALS (active) ===")
socs = db.get_active_socials()
for s in socs:
    comp = s.get("competitors") or {}
    print(f"  comp={comp.get('name')!r}  platform={s.get('platform')}  url={s.get('handle_url')}  active={s.get('active')}  ch={comp.get('slack_channel')!r}")

print("\n=== LATEST POSTS per competitor ===")
posts = sb.table("posts").select("competitor_id,platform,posted_at,first_seen").order("posted_at", desc=True).limit(200).execute().data
from collections import defaultdict
by = defaultdict(list)
for p in posts:
    by[p["competitor_id"]].append(p)
name_of = {c["id"]: c.get("name") for c in comps}
for cid, plist in by.items():
    latest = plist[0]
    print(f"  {name_of.get(cid, cid)!r}: {len(plist)} posts (shown), newest posted_at={latest.get('posted_at')}  first_seen={latest.get('first_seen')}")

print("\n=== TOTAL posts in DB ===")
total = sb.table("posts").select("id", count="exact").execute()
print(f"  {total.count} rows")

print(f"\n=== SERVER TIME (this machine) ===")
import datetime as dt
print(f"  datetime.now() = {dt.datetime.now().isoformat()}  (hour={dt.datetime.now().hour})")
print(f"  utcnow()       = {dt.datetime.utcnow().isoformat()}  (hour={dt.datetime.utcnow().hour})")
print(f"  DAILY_HOUR env = {os.environ.get('DAILY_HOUR', '(not set -> default 9)')}")
