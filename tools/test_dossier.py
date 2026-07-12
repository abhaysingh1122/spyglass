"""Live test: run the dossier on Microsoft's real posts to confirm JSON mode fixed the French/no-JSON bug."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from spyglass import db, ai

name = "Microsoft"
posts = db.get_posts_for_competitor_name(name)
print(f"Loaded {len(posts)} posts for {name}")
print("Calling ai.dossier (json_mode now on)...")
try:
    d = ai.dossier(name, posts)
    print("\n=== DOSSIER RETURNED VALID JSON ===")
    print("verdict:", d.get("verdict"))
    print("cadence:", d.get("cadence"))
    print("hook_matrix rows:", len(d.get("hook_matrix") or []))
    print("weaknesses:", d.get("weaknesses"))
    tp = d.get("top_post") or {}
    print("top_post.one_liner:", tp.get("one_liner"))
    print("\n(English check ^ — verdict/weaknesses should be English even though posts are French)")
except Exception as e:
    print("\n!!! STILL FAILING:", type(e).__name__, e)
