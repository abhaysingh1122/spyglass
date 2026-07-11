"""Block Kit rendering for SpyGlass reports — the daily intel must LOOK like intel."""
import datetime as dt


def _ago(posted_iso) -> str:
    if not posted_iso:
        return ""
    try:
        posted = dt.datetime.fromisoformat(str(posted_iso).replace("Z", "+00:00"))
        delta = dt.datetime.now(dt.timezone.utc) - posted
        hours = int(delta.total_seconds() // 3600)
        if hours < 1:
            return "just now"
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except Exception:
        return ""


def build_daily_blocks(result: dict, new_posts: list, competitor_names: dict = None) -> list:
    """result = ai.daily_brief output; new_posts = DB rows (engagement numbers)."""
    by_url = {p.get("post_url"): p for p in new_posts}
    names = competitor_names or {}
    today = dt.date.today().strftime("%b %d")

    blocks = [
        {"type": "header",
         "text": {"type": "plain_text", "text": f"🔍 SpyGlass Daily Intel — {today}", "emoji": True}},
        {"type": "context", "elements": [
            {"type": "mrkdwn",
             "text": f"*{len(result.get('posts', []))} new post(s)* detected in the last 24h"}]},
        {"type": "divider"},
    ]

    for i, p in enumerate(result.get("posts", []), 1):
        row = by_url.get(p.get("post_url"), {})
        comp = names.get(row.get("competitor_id"), "")
        eng = (f"👍 {row.get('likes', 0):,}   💬 {row.get('comments', 0):,}   "
               f"🔁 {row.get('shares', 0):,}")
        ago = _ago(row.get("posted_at"))
        title_bits = [b for b in [comp, ago] if b]
        blocks += [
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f"*{i}️⃣  {p.get('one_liner', 'New post')}*\n"
                        f"_{' · '.join(title_bits)}_   {eng}   <{p.get('post_url', '')}|View post ↗>"}},
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f"🧠 *AI's take:*\n>{p.get('ai_take', '—')}"}},
            {"type": "context", "elements": [
                {"type": "mrkdwn", "text": f"🪝 *Hook:* {p.get('hook_type', '?')}"},
                {"type": "mrkdwn", "text": f"📂 {p.get('content_type', '?')}"},
                {"type": "mrkdwn", "text": f"👥 {p.get('audience_reaction', '')}"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f"💡 *Steal this:* {p.get('steal_this', '—')}"}},
            {"type": "divider"},
        ]

    if result.get("overall_pattern"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"📊 *The pattern:* {result['overall_pattern']}"}})

    for line in result.get("growth_lines", []) or []:
        blocks.append({"type": "section",
                       "text": {"type": "mrkdwn", "text": f"📈 {line}"}})

    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn", "text": "Full breakdown in the attached document · _SpyGlass is watching_ 🔍"}]})
    return blocks


def build_dossier_blocks(name: str, result: dict, n_posts: int) -> list:
    """Content-spy dossier — the competitor's decoded playbook."""
    blocks = [
        {"type": "header", "text": {"type": "plain_text",
            "text": f"🗂️ Content Dossier — {name.title()}", "emoji": True}},
        {"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"Compiled from *{n_posts} posts* · SpyGlass Content Spy"}]},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"⚖️ *Verdict:* {result.get('verdict', '—')}"}},
        {"type": "divider"},
    ]

    hm = result.get("hook_matrix") or []
    if hm:
        lines = [f"• *{h.get('hook_type', '?')}* — used {h.get('times_used', '?')}×, "
                 f"~{h.get('avg_engagement', 0):,} avg engagement — _{h.get('verdict', '')}_"
                 for h in hm]
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": "🪝 *Hook Matrix* (what grabs, what flops)\n" + "\n".join(lines)}})

    cm = result.get("content_mix") or []
    if cm:
        lines = [f"• {c.get('content_type', '?')}: *{c.get('share_pct', 0)}%* — {c.get('note', '')}"
                 for c in cm]
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": "📂 *Content Mix*\n" + "\n".join(lines)}})

    if result.get("cadence"):
        blocks.append({"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"⏱️ *Cadence:* {result['cadence']}"}]})

    tp = result.get("top_post") or {}
    if tp:
        blocks += [{"type": "divider"},
                   {"type": "section", "text": {"type": "mrkdwn",
                    "text": f"🏆 *Their best weapon:* {tp.get('one_liner', '—')} "
                            f"({tp.get('engagement', '')})\n>{tp.get('why_it_won', '')}"}}]

    if result.get("weaknesses"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": "🎯 *Exploitable gaps*\n" + "\n".join(f"• {w}" for w in result["weaknesses"])}})

    if result.get("playbook"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": "💡 *Steal-this playbook*\n" + "\n".join(f"{i}. {p}" for i, p in
                                                             enumerate(result["playbook"], 1))}})

    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn", "text": "Full dossier in the attached document · _SpyGlass is watching_ 🔍"}]})
    return blocks
