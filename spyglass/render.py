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


def _menu_action_rows() -> list:
    return [
        {"type": "actions", "elements": [
            {"type": "button", "action_id": "menu_scan", "style": "primary",
             "text": {"type": "plain_text", "text": "🔍 Scan Now"}},
            {"type": "button", "action_id": "menu_analyze",
             "text": {"type": "plain_text", "text": "🗂️ Analyze"}},
            {"type": "button", "action_id": "menu_predict",
             "text": {"type": "plain_text", "text": "🔮 Predict"}},
        ]},
        {"type": "actions", "elements": [
            {"type": "button", "action_id": "menu_ask",
             "text": {"type": "plain_text", "text": "💬 Ask"}},
            {"type": "button", "action_id": "menu_compare",
             "text": {"type": "plain_text", "text": "🏆 Compare"}},
            {"type": "button", "action_id": "menu_manage",
             "text": {"type": "plain_text", "text": "⚙️ Manage"}},
        ]},
    ]


def build_menu_blocks() -> list:
    return [
        {"type": "header", "text": {"type": "plain_text", "text": "🔍 SpyGlass", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": "Your competitor-intelligence command center. Pick an action:"}},
        *_menu_action_rows(),
    ]


def build_home_view(status: dict, competitors: list) -> dict:
    watched = ", ".join(c["name"] for c in competitors) or "_none yet_"
    blocks = [
        {"type": "header", "text": {"type": "plain_text",
            "text": "🔍 SpyGlass — Competitor Intelligence", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"*{status.get('competitors', 0)}* competitors  ·  "
                    f"*{status.get('posts', 0)}* posts tracked  ·  "
                    f"*{status.get('briefs', 0)}* briefs sent"}]},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Watching:* {watched}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*What do you want to do?*"}},
        *_menu_action_rows(),
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": "➕ *Add a competitor:* type `/setcomp <url>` in any channel."}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "_SpyGlass is watching_ 🔍"}]},
    ]
    return {"type": "home", "blocks": blocks}


def competitor_select_modal(callback_id: str, title: str, competitors: list,
                            include_question: bool = False, channel: str = "") -> dict:
    opts = [{"text": {"type": "plain_text", "text": c["name"]}, "value": c["name"]}
            for c in competitors] or [
        {"text": {"type": "plain_text", "text": "No competitors yet"}, "value": "none"}]
    blocks = [{"type": "input", "block_id": "competitor",
               "label": {"type": "plain_text", "text": "Competitor"},
               "element": {"type": "static_select", "action_id": "v", "options": opts}}]
    if include_question:
        blocks.append({"type": "input", "block_id": "question",
            "label": {"type": "plain_text", "text": "Your question"},
            "element": {"type": "plain_text_input", "action_id": "v", "multiline": True,
                        "placeholder": {"type": "plain_text",
                                        "text": "What did they post this week? How do we counter it?"}}})
    return {"type": "modal", "callback_id": callback_id,
            "private_metadata": channel or "",
            "title": {"type": "plain_text", "text": title[:24]},
            "submit": {"type": "plain_text", "text": "Run"},
            "close": {"type": "plain_text", "text": "Cancel"}, "blocks": blocks}


PLATFORM_OPTIONS = [
    {"text": {"type": "plain_text", "text": p.title()}, "value": p}
    for p in ["linkedin", "instagram", "twitter", "website", "youtube"]
]

PLAT_EMOJI = {"linkedin": "💼", "instagram": "📸", "twitter": "🐦",
              "website": "🌐", "youtube": "▶️"}


def build_edit_blocks(competitors: list) -> list:
    """Interactive watchlist editor for /spy edit."""
    blocks = [
        {"type": "header", "text": {"type": "plain_text",
            "text": "⚙️ Manage Watchlist", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": "Add or swap the platforms SpyGlass watches for each competitor."}]},
        {"type": "divider"},
    ]
    if not competitors:
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": "No competitors yet. Use `/setcomp <url>` to add one."}})
        return blocks

    for c in competitors:
        plats = " ".join(f"{PLAT_EMOJI.get(s['platform'], '•')} {s['platform']}"
                         for s in c["socials"]) or "_no platforms_"
        blocks.append({"type": "section",
            "text": {"type": "mrkdwn", "text": f"*{c['name']}*\n{plats}"},
            "accessory": {"type": "button", "action_id": "edit_add",
                "text": {"type": "plain_text", "text": "➕ Add platform"},
                "value": c["id"]}})
        elements = [{"type": "button", "action_id": "edit_replace",
                     "text": {"type": "plain_text", "text": "🔁 Replace"},
                     "value": c["id"]}]
        elements.append({"type": "button", "action_id": "edit_remove_open",
            "style": "danger",
            "text": {"type": "plain_text", "text": "🗑 Remove"},
            "value": c["id"]})
        blocks.append({"type": "actions", "elements": elements})
        blocks.append({"type": "divider"})
    return blocks


def add_platform_modal(competitor_id: str, competitor_name: str, channel: str = "") -> dict:
    return {
        "type": "modal", "callback_id": "edit_add_submit",
        "private_metadata": f"{competitor_id}|{channel}",
        "title": {"type": "plain_text", "text": "Add Platform"},
        "submit": {"type": "plain_text", "text": "Add"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Add a platform for *{competitor_name}*"}},
            {"type": "input", "block_id": "platform",
             "label": {"type": "plain_text", "text": "Platform"},
             "element": {"type": "static_select", "action_id": "v",
                         "options": PLATFORM_OPTIONS}},
            {"type": "input", "block_id": "url",
             "label": {"type": "plain_text", "text": "Handle / Profile URL"},
             "element": {"type": "plain_text_input", "action_id": "v",
                         "placeholder": {"type": "plain_text", "text": "https://instagram.com/theirhandle"}}},
        ],
    }


def remove_modal(competitor_id: str, competitor_name: str, socials: list,
                 channel: str = "") -> dict:
    opts = [{"text": {"type": "plain_text", "text": "🗑 Entire competitor (all platforms)"},
             "value": "ALL"}]
    for s in socials:
        opts.append({"text": {"type": "plain_text",
                              "text": f"Just {s['platform']} — {s['handle_url'][:45]}"},
                     "value": s["id"]})
    return {
        "type": "modal", "callback_id": "edit_remove_submit",
        "private_metadata": f"{competitor_id}|{channel}",
        "title": {"type": "plain_text", "text": "Remove"},
        "submit": {"type": "plain_text", "text": "Remove"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f"What should I stop watching for *{competitor_name}*?"}},
            {"type": "input", "block_id": "target",
             "label": {"type": "plain_text", "text": "Remove"},
             "element": {"type": "static_select", "action_id": "v", "options": opts}},
        ],
    }


def replace_platform_modal(competitor_id: str, competitor_name: str, socials: list,
                           channel: str = "") -> dict:
    opts = [{"text": {"type": "plain_text",
                      "text": f"{s['platform']} — {s['handle_url'][:60]}"},
             "value": s["id"]} for s in socials]
    return {
        "type": "modal", "callback_id": "edit_replace_submit",
        "private_metadata": f"{competitor_id}|{channel}",
        "title": {"type": "plain_text", "text": "Replace Platform"},
        "submit": {"type": "plain_text", "text": "Replace"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Swap a platform for *{competitor_name}*"}},
            {"type": "input", "block_id": "which",
             "label": {"type": "plain_text", "text": "Which handle to replace"},
             "element": {"type": "static_select", "action_id": "v", "options": opts}},
            {"type": "input", "block_id": "platform",
             "label": {"type": "plain_text", "text": "New platform"},
             "element": {"type": "static_select", "action_id": "v", "options": PLATFORM_OPTIONS}},
            {"type": "input", "block_id": "url",
             "label": {"type": "plain_text", "text": "New handle / URL"},
             "element": {"type": "plain_text_input", "action_id": "v"}},
        ],
    }


def _pct(prev, cur):
    prev = prev or 0
    if prev == 0:
        return "new" if cur else "0%"
    return f"{'+' if cur >= prev else ''}{round((cur - prev) / prev * 100)}%"


def build_growth_blocks(updates: list, verdict: dict) -> list:
    blocks = [
        {"type": "header", "text": {"type": "plain_text",
            "text": "📈 Weekly Growth Report", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"7-day engagement change across *{len(updates)}* tracked post(s)"}]},
        {"type": "divider"},
    ]
    for u in updates:
        p, c = u.get("previous", {}), u.get("current", {})
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*<{u.get('post_url', '')}|Post>*\n"
                    f"👍 {p.get('likes', 0):,} → *{c.get('likes', 0):,}* ({_pct(p.get('likes'), c.get('likes'))})   "
                    f"💬 {p.get('comments', 0):,} → *{c.get('comments', 0):,}*   "
                    f"🔁 {p.get('shares', 0):,} → *{c.get('shares', 0):,}*"}})
    for line in verdict.get("lines", []) or []:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"🧠 {line}"}]})
    if verdict.get("overall"):
        blocks += [{"type": "divider"},
                   {"type": "section", "text": {"type": "mrkdwn",
                    "text": f"📊 *The read:* {verdict['overall']}"}}]
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
        "text": "_SpyGlass is watching_ 🔍"}]})
    return blocks


def build_prediction_blocks(name: str, pred: dict) -> list:
    conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}
    blocks = [
        {"type": "header", "text": {"type": "plain_text",
            "text": f"🔮 Forecast — {name.title()}", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*Trajectory:* {pred.get('trajectory', '—')}"}},
        {"type": "divider"},
    ]
    for i, p in enumerate(pred.get("predictions", []), 1):
        c = (p.get("confidence") or "medium").lower()
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{i}. {p.get('move', '—')}*  {conf_emoji.get(c, '🟡')} _{c} confidence_\n"
                    f">{p.get('reasoning', '')}\n🕐 _{p.get('timeframe', '')}_"}})
    if pred.get("neglecting"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": "🕳️ *Where they're neglecting*\n" +
                    "\n".join(f"• {n}" for n in pred["neglecting"])}})
    if pred.get("your_opening"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"⚔️ *Your opening:* {pred['your_opening']}"}})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
        "text": "Forecast is inference from their patterns · _SpyGlass is watching_ 🔍"}]})
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
