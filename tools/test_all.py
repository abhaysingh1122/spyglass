"""End-to-end feature test: exercises every Slack handler's underlying code path
against REAL data (real DB + real AI). If a check passes here, the button works in Slack.
Uses existing stored posts — NO Apify re-scrape (saves credits). Spends ~5 OpenRouter calls."""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from spyglass import db, ai, render, report

results = []
def check(name, fn):
    try:
        out = fn()
        results.append((name, True, out))
        print(f"[PASS] {name}: {out}")
    except Exception as e:
        results.append((name, False, f"{type(e).__name__}: {e}"))
        print(f"[FAIL] {name}: {type(e).__name__}: {e}")
        traceback.print_exc()

# ---- data prep ----
self_acct = db.get_self()
self_posts = db.get_self_posts()
comp_name = "Microsoft"
comp_posts = db.get_posts_for_competitor_name(comp_name)
print(f"self={self_acct and self_acct.get('name')!r} ({len(self_posts)} posts) | "
      f"{comp_name} ({len(comp_posts)} posts)\n")

# ---- 1. /spy status  &  /spy compare (no AI) ----
check("db.system_status (/spy status)", lambda: f"{db.system_status()}")
check("db.leaderboard (/spy compare)", lambda: f"{len(db.leaderboard())} rows")
check("render.build_menu_blocks (/spy menu)", lambda: f"{len(render.build_menu_blocks())} blocks")
check("render.build_me_panel_blocks (My Account panel)",
      lambda: f"{len(render.build_me_panel_blocks(self_acct and self_acct.get('name')))} blocks")
check("render.set_self_modal", lambda: render.set_self_modal("C123")["type"])
check("render.build_home_view (App Home)",
      lambda: render.build_home_view(db.system_status(), db.list_competitors_with_socials())["type"])

# ---- 2. /spy analyze <competitor>  (dossier + blocks + docx) ----
def t_dossier():
    d = ai.dossier(comp_name, comp_posts)
    blocks = render.build_dossier_blocks(comp_name, d, len(comp_posts))
    path = report.build_dossier_docx(comp_name, d, comp_posts)
    ok = os.path.exists(path)
    return f"verdict={d.get('verdict','')[:50]!r}... | {len(blocks)} blocks | docx={ok}"
check("/spy analyze (dossier -> blocks -> Word doc)", t_dossier)

# ---- 3. My Account -> Audit me  (self_audit + blocks) ----
def t_audit():
    a = ai.self_audit(self_posts)
    blocks = render.build_self_audit_blocks(self_acct["name"], a)
    return f"pains={len(a.get('pain_points') or [])} wins={len(a.get('quick_wins') or [])} | {len(blocks)} blocks"
check("My Account/Audit (self_audit -> blocks)", t_audit)

# ---- 4. Compare vs  (compare + blocks) ----
def t_compare():
    c = ai.compare(self_acct["name"], self_posts, comp_name, comp_posts)
    blocks = render.build_comparison_blocks(self_acct["name"], comp_name, c)
    return f"why_they_win={len(c.get('why_they_win') or [])} strategy={len(c.get('strategy') or [])} | {len(blocks)} blocks"
check("Compare vs (compare -> blocks)", t_compare)

# ---- 5. /spy ask <question>  (grounded Q&A, plain text) ----
def t_ask():
    ans = ai.ask("Which competitor posts the most and what topics dominate?",
                 comp_posts + self_posts)
    return f"{len(ans)} chars | head={ans[:60]!r}"
check("/spy ask (grounded Q&A)", t_ask)

# ---- 6. Daily 6am brief  (daily_brief + blocks + docx) — uses recent posts as 'new' ----
def t_daily():
    sample = comp_posts[:6]
    d = ai.daily_brief(sample, [])
    blocks = render.build_daily_blocks(d, sample, {comp_name: comp_name})
    path = report.build_docx(d, sample, [])
    return f"pattern={d.get('overall_pattern','')[:40]!r}... | {len(blocks)} blocks | docx={os.path.exists(path)}"
check("Daily 6am brief (daily_brief -> blocks -> Word doc)", t_daily)

# ---- summary ----
print("\n" + "=" * 60)
passed = sum(1 for _, ok, _ in results if ok)
print(f"RESULT: {passed}/{len(results)} checks passed")
for name, ok, _ in results:
    print(f"  {'OK ' if ok else 'XX '} {name}")
sys.exit(0 if passed == len(results) else 1)
