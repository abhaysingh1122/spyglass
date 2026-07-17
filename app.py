"""SpyGlass — Slack competitor-intelligence agent.
Run: python app.py   (needs SLACK_BOT_TOKEN + SLACK_APP_TOKEN in .env)
Uses Socket Mode, so no public URL / tunnel is required for local dev.
"""
import os
import re
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from spyglass import db

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])


# --- helpers -------------------------------------------------------------
def detect_platform(url: str) -> str:
    u = url.lower()
    if "linkedin.com" in u:
        return "linkedin"
    if "instagram.com" in u:
        return "instagram"
    if "twitter.com" in u or "x.com" in u:
        return "twitter"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    return "website"


URL_RE = re.compile(r"https?://[^\s|>]+")


def extract_url(text: str):
    """Pull a URL from text, accepting scheme-less forms like www.linkedin.com/in/x."""
    text = (text or "").strip().strip("<>")
    m = URL_RE.search(text)
    if m:
        return m.group(0)
    m = re.search(r"(?:www\.)?[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?:/[^\s|>]*)?", text, re.I)
    return "https://" + m.group(0) if m else None


def derive_name(url: str) -> str:
    slug = re.sub(r"[?#].*$", "", url.rstrip("/")).split("/")[-1]
    slug = slug.replace("-", " ").replace("_", " ").strip()
    return slug.title() if slug else url


# --- /setcomp ------------------------------------------------------------
@app.command("/setcomp")
def handle_setcomp(ack, respond, command):
    ack()  # must respond within 3s
    text = (command.get("text") or "").strip()
    url = extract_url(text)
    if not url:
        respond(":warning: Usage: `/setcomp linkedin.com/company/acme`")
        return
    platform = detect_platform(url)
    name = derive_name(url)

    try:
        result = db.add_competitor(
            name, platform, url,
            added_by=command.get("user_id"),
            slack_channel=command.get("channel_id"),
        )
    except Exception as e:
        respond(f":x: Couldn't save competitor — is the Supabase schema applied?\n```{e}```")
        return

    existed = result.get("existed")
    header = phrase("comp_existed") if existed else phrase("comp_new")
    respond(
        blocks=[
            {"type": "header", "text": {"type": "plain_text", "text": header}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Name:*\n{name}"},
                {"type": "mrkdwn", "text": f"*Platform:*\n{platform}"},
                {"type": "mrkdwn", "text": f"*Handle:*\n<{url}>"},
            ]},
            {"type": "context", "elements": [
                {"type": "mrkdwn", "text": phrase("comp_watching")}
            ]},
        ],
        text=f"Competitor locked in: {name} ({platform})",
    )


# --- /spy router: check | list | ask ------------------------------------
TONE = {"current": "default"}  # /tone easter egg state


# Persona-flavored status lines — the tone colors EVERY reply, not just the AI analysis.
PHRASES = {
    "default": {
        "self_detected": "🪞 That's *your* account — pulling your full history and auditing you…",
        "scan_start":    "🔍 SpyGlass is on the case{scope} — scanning now…",
        "scan_menu":     "🔍 SpyGlass is scanning your competitors now…",
        "quiet":         "🕯️ Nothing new in the last 24h, and no posts due a growth re-check. The street is quiet.",
        "quiet_short":   "🕯️ Nothing new in the last 24h. The street is quiet.",
        "dossier_start": "🗂️ Compiling the content dossier on *{target}* — pulling a month of posts, decoding the playbook. Give me a minute…",
        "audit_start":   "🪞 Auditing your account — finding pain points and quick wins…",
        "audit_short":   "🪞 Auditing your account…",
        "compare_start": "⚔️ Comparing you against *{comp}*…",
        "compare_named": "⚔️ Comparing *{me}* vs *{comp}*…",
        "list_header":   "🔍 *Watchlist:*",
        "status_header": "🔍 *SpyGlass Status*",
        "board_header":  "🏆 *Competitor Leaderboard* (by avg engagement)",
        "comp_new":      "🔍 Competitor locked in",
        "comp_existed":  "🔍 Already watching this competitor",
        "comp_watching": "SpyGlass is now watching. Daily scans will surface their new posts here.",
    },
    "sherlock": {
        "self_detected": "🎩 *Ah — your own file.* Allow me to retrieve your complete history and deduce what it betrays…",
        "scan_start":    "🔍 *The game is afoot{scope}.* I shall survey the field for fresh tracks…",
        "scan_menu":     "🔍 *The game is afoot.* I turn my glass upon your rivals…",
        "quiet":         "🕯️ *Curious — the dog did not bark.* Nothing new these 24 hours, and no post awaits re-examination. The trail is cold… for now.",
        "quiet_short":   "🕯️ *The dog did not bark* — nothing new in 24 hours. The trail is cold.",
        "dossier_start": "🗂️ *A most instructive subject.* Grant me a moment to study a month of *{target}*'s conduct and deduce their methods…",
        "audit_start":   "🔍 *Elementary — let us turn the glass upon ourselves.* Reading your record for the tells you cannot see…",
        "audit_short":   "🔍 *Turning the glass upon yourself…*",
        "compare_start": "⚔️ *Let us lay the two records side by side* — you against *{comp}*. The deductions will be telling…",
        "compare_named": "⚔️ *Two files, one comparison* — *{me}* set against *{comp}*…",
        "list_header":   "🔍 *The subjects under surveillance:*",
        "status_header": "🔍 *The State of the Investigation*",
        "board_header":  "🏆 *The Field, Ranked* (by average engagement)",
        "comp_new":      "🔍 A new subject enters the casebook",
        "comp_existed":  "🔍 This subject is already under my glass",
        "comp_watching": "The subject is now under surveillance. Each day I shall note their fresh movements here.",
    },
}


def phrase(key, **kw):
    """Return a status line in the current persona's voice."""
    table = PHRASES.get(TONE["current"], PHRASES["default"])
    return table.get(key, PHRASES["default"][key]).format(**kw)


@app.command("/spy")
def handle_spy(ack, respond, command, client):
    ack()
    text = (command.get("text") or "").strip()
    sub, _, rest = text.partition(" ")
    sub = sub.lower()

    if sub == "check":
        target = rest.strip() or None
        me = db.get_self()
        # Is the target OUR own account? Then full-history backfill + audit, not a 24h scan.
        is_self = bool(target and me and target.lower() in me["name"].lower())
        ch = command.get("channel_id")
        if is_self:
            respond(phrase("self_detected"))
            from spyglass import flows, ai as ai_mod, render
            try:
                flows.backfill_account(me["name"])
                posts = db.get_self_posts()
                if not posts:
                    respond("Couldn't pull any posts for your account — is the profile public?")
                    return
                audit = ai_mod.self_audit(posts, tone=TONE["current"])
                client.chat_postMessage(channel=ch,
                    blocks=render.build_self_audit_blocks(me["name"], audit, tone=TONE["current"]), text="Your audit")
            except Exception as e:
                respond(f":x: Audit failed:\n```{e}```")
            return
        # Competitor path: 24h incremental scan
        scope = f" on *{target}*" if target else ""
        respond(phrase("scan_start", scope=scope))
        from spyglass import flows
        try:
            status = flows.run_daily(client, ch, tone=TONE["current"], name_filter=target)
        except Exception as e:
            respond(f":x: Scan failed:\n```{e}```")
            return
        if status == "quiet":
            respond(phrase("quiet"))
    elif sub == "analyze":
        target = rest.strip()
        if not target:
            respond("Usage: `/spy analyze <competitor>` — e.g. `/spy analyze openai`")
            return
        respond(phrase("dossier_start", target=target))
        from spyglass import flows
        try:
            status = flows.run_deep_analysis(client, command.get("channel_id"),
                                             target, tone=TONE["current"])
        except Exception as e:
            respond(f":x: Dossier failed:\n```{e}```")
            return
        if status == "none":
            respond(f"No competitor matching *{target}* on the watchlist. `/spy list` to see who's locked in.")
    elif sub == "list":
        socials = db.get_active_socials()
        if not socials:
            respond("No competitors locked in yet. Use `/setcomp <url>`.")
            return
        lines = [f"• *{s['competitors']['name']}* — {s['platform']} — <{s['handle_url']}>"
                 + (f" _(last scraped {s['last_scraped_at'][:16]})_" if s.get("last_scraped_at") else " _(never scraped)_")
                 for s in socials]
        respond(phrase("list_header") + "\n" + "\n".join(lines))
    elif sub == "ask":
        if not rest.strip():
            respond("Usage: `/spy ask <competitor> <question>` — e.g. `/spy ask openai what hooks work for them?`")
            return
        comp, _, question = rest.partition(" ")
        from spyglass import ai as ai_mod
        posts = db.get_posts_for_competitor_name(comp)
        if not posts:
            respond(f"No stored intel on *{comp}* yet. Run `/spy check` first.")
            return
        try:
            answer = ai_mod.ask(question or "give me a full read on this competitor",
                                posts, tone=TONE["current"])
        except Exception as e:
            respond(f":x: Analysis failed:\n```{e}```")
            return
        respond(f"🔍 *SpyGlass on {comp}:*\n{answer}")
    elif sub == "status":
        s = db.system_status()
        watched = "\n".join(
            f"• {so['platform']} — " +
            (f"scanned {so['last_scraped_at'][:16]}" if so.get("last_scraped_at") else "never scanned")
            for so in s["socials"]) or "_none_"
        respond(
            phrase("status_header") + "\n"
            f"*Competitors:* {s['competitors']}   *Posts tracked:* {s['posts']}   "
            f"*Briefs sent:* {s['briefs']}\n\n*Watched socials:*\n{watched}")
    elif sub == "edit":
        from spyglass import render
        respond(blocks=render.build_edit_blocks(db.list_competitors_with_socials()),
                text="Manage watchlist")
    elif sub == "weekly":
        target = rest.strip() or None
        scope = f" for *{target}*" if target else ""
        respond(f"📈 Running the 7-day growth check{scope} — re-scraping posts due a re-check…")
        from spyglass import flows
        try:
            status = flows.run_weekly(client, command.get("channel_id"),
                                      tone=TONE["current"], name_filter=target)
        except Exception as e:
            respond(f":x: Weekly check failed:\n```{e}```")
            return
        if status == "none":
            respond("🕯️ No posts are due a 7-day growth re-check yet. "
                    "(Posts become due once they're 7 days past their last check.)")
    elif sub == "setself":
        url = extract_url(rest)
        if not url:
            respond("Usage: `/spy setself <your profile url>` — register YOUR account")
            return
        name = derive_name(url)
        try:
            db.add_competitor(name, detect_platform(url), url,
                              added_by=command.get("user_id"),
                              slack_channel=command.get("channel_id"), is_self=True)
        except Exception as e:
            respond(f":x: Couldn't set your account:\n```{e}```")
            return
        respond(f"🪞 Set *{name}* as *your* account. Now `/spy check {name}` to scan it, "
                f"then `/spy me` for your audit or `/spy vs <competitor>` to compare.")
    elif sub == "me":
        respond(phrase("audit_start"))
        from spyglass import ai as ai_mod, render
        me = db.get_self()
        posts = db.get_self_posts()
        if not me:
            respond("You haven't set your own account yet. Use `/spy setself <your profile url>`.")
            return
        if not posts:
            respond(f"Your account *{me['name']}* is set, but not scanned yet. "
                    f"Run `/spy check {me['name']}` first.")
            return
        try:
            audit = ai_mod.self_audit(posts, tone=TONE["current"])
        except Exception as e:
            respond(f":x: Audit failed:\n```{e}```")
            return
        respond(blocks=render.build_self_audit_blocks(me["name"], audit, tone=TONE["current"]),
                text="Your account audit")
    elif sub == "vs":
        comp = rest.strip()
        if not comp:
            respond("Usage: `/spy vs <competitor>` — compare your account against them")
            return
        respond(phrase("compare_start", comp=comp))
        from spyglass import ai as ai_mod, render
        me = db.get_self()
        my_posts = db.get_self_posts()
        if not me or not my_posts:
            respond("Set + scan your own account first: `/spy setself <url>` then `/spy check`.")
            return
        comp_posts = db.get_posts_for_competitor_name(comp)
        if not comp_posts:
            respond(f"No intel on *{comp}* yet — run `/spy check {comp}` first.")
            return
        try:
            cmp = ai_mod.compare(me["name"], my_posts, comp, comp_posts, tone=TONE["current"])
        except Exception as e:
            respond(f":x: Comparison failed:\n```{e}```")
            return
        respond(blocks=render.build_comparison_blocks(me["name"], comp, cmp, tone=TONE["current"]),
                text=f"You vs {comp}")
    elif sub == "compare":
        board = db.leaderboard()
        if not board:
            respond("No data yet to compare. Run `/spy check` first.")
            return
        medals = ["🥇", "🥈", "🥉"] + ["▪️"] * 20
        lines = [f"{medals[i]} *{r['name']}* — {r['avg']:,} avg engagement "
                 f"({r['posts']} posts · {r['likes']:,}👍 {r['comments']:,}💬 {r['shares']:,}🔁)"
                 for i, r in enumerate(board)]
        respond(phrase("board_header") + "\n" + "\n".join(lines))
    elif not text:
        from spyglass import render
        respond(blocks=render.build_menu_blocks(), text="SpyGlass menu")
    else:
        # Natural-language question — figure out the competitor, answer from intel.
        def _norm(s):
            return "".join(ch for ch in s.lower() if ch.isalnum())
        norm_text = _norm(text)
        matched = next((c["name"] for c in db.list_competitors_with_socials()
                        if _norm(c["name"]) in norm_text), None)
        respond(f"🔍 Digging through the intel{' on *' + matched + '*' if matched else ''}…")
        from spyglass import ai as ai_mod
        posts = (db.get_posts_for_competitor_name(matched) if matched
                 else db.recent_posts_all())
        if not posts:
            respond("No intel stored yet — run `/spy check` first so I have something to reason over.")
            return
        try:
            answer = ai_mod.ask(text, posts, tone=TONE["current"])
        except Exception as e:
            respond(f":x: Couldn't answer:\n```{e}```")
            return
        respond(f"🔍 {answer}")


# --- App Home dashboard --------------------------------------------------
@app.event("app_home_opened")
def handle_home_opened(client, event):
    from spyglass import render
    client.views_publish(
        user_id=event["user"],
        view=render.build_home_view(db.system_status(), db.list_competitors_with_socials()))


# --- Menu button handlers -----------------------------------------------
def _menu_channel(body):
    return (body.get("channel") or {}).get("id") or body["user"]["id"]


@app.action("menu_scan")
def menu_scan(ack, body, client):
    ack()
    import threading
    ch = _menu_channel(body)
    client.chat_postMessage(channel=ch, text=phrase("scan_menu"))
    from spyglass import flows

    def work():
        try:
            status = flows.run_daily(client, ch, tone=TONE["current"])
            if status == "quiet":
                client.chat_postMessage(channel=ch, text=phrase("quiet_short"))
        except Exception as e:
            client.chat_postMessage(channel=ch, text=f":x: Scan failed: {e}")
    threading.Thread(target=work, daemon=True).start()


@app.action("menu_analyze")
def menu_analyze(ack, body, client):
    ack()
    from spyglass import render
    client.views_open(trigger_id=body["trigger_id"],
                      view=render.competitor_select_modal("run_analyze", "Analyze Competitor",
                                                          db.list_competitors_with_socials(),
                                                          channel=_menu_channel(body)))




@app.action("menu_ask")
def menu_ask(ack, body, client):
    ack()
    from spyglass import render
    client.views_open(trigger_id=body["trigger_id"],
                      view=render.competitor_select_modal("run_ask", "Ask SpyGlass",
                                                          db.list_competitors_with_socials(),
                                                          include_question=True,
                                                          channel=_menu_channel(body)))


@app.action("menu_me")
def menu_me(ack, body, client):
    ack()
    from spyglass import render
    me = db.get_self()
    client.chat_postMessage(channel=_menu_channel(body),
                            blocks=render.build_me_panel_blocks(me["name"] if me else None),
                            text="Your account")


@app.action("me_set")
def me_set(ack, body, client):
    ack()
    from spyglass import render
    client.views_open(trigger_id=body["trigger_id"],
                      view=render.set_self_modal(channel=_menu_channel(body)))


@app.view("set_self_submit")
def set_self_submit(ack, body, view, client):
    ack()
    channel = view.get("private_metadata") or body["user"]["id"]
    url = extract_url(view["state"]["values"]["url"]["v"]["value"])
    if not url:
        client.chat_postMessage(channel=channel,
            text=":warning: That didn't look like a URL. Try e.g. `linkedin.com/in/yourname`.")
        return
    name = derive_name(url)
    db.add_competitor(name, detect_platform(url), url, added_by=body["user"]["id"],
                      slack_channel=channel, is_self=True)
    client.chat_postMessage(channel=channel,
        text=f"🪞 Set *{name}* as your account — pulling your full history so I can audit you…")
    import threading
    from spyglass import flows

    def _bf():
        try:
            rows = flows.backfill_account(name)
            client.chat_postMessage(channel=channel,
                text=f"✅ Scanned *{name}* — {len(rows)} posts pulled. "
                     "Now hit *🪞 Audit me* or *⚔️ Compare vs…*")
        except Exception as e:
            client.chat_postMessage(channel=channel, text=f":x: Scan failed: {e}")
    threading.Thread(target=_bf, daemon=True).start()


@app.action("me_audit")
def me_audit(ack, body, client):
    ack()
    import threading
    ch = _menu_channel(body)

    def work():
        from spyglass import ai as ai_mod, render
        me = db.get_self()
        posts = db.get_self_posts()
        if not me:
            client.chat_postMessage(channel=ch, text="Set your account first (🪞 My Account → ➕).")
            return
        if not posts:
            client.chat_postMessage(channel=ch, text=f"*{me['name']}* isn't scanned yet — "
                                    f"run `/spy check {me['name']}` first.")
            return
        client.chat_postMessage(channel=ch, text=phrase("audit_short"))
        try:
            audit = ai_mod.self_audit(posts, tone=TONE["current"])
            client.chat_postMessage(channel=ch,
                blocks=render.build_self_audit_blocks(me["name"], audit, tone=TONE["current"]), text="Your audit")
        except Exception as e:
            client.chat_postMessage(channel=ch, text=f":x: {e}")
    threading.Thread(target=work, daemon=True).start()


@app.action("me_compare")
def me_compare(ack, body, client):
    ack()
    from spyglass import render
    comps = [c for c in db.list_competitors_with_socials()]
    client.views_open(trigger_id=body["trigger_id"],
                      view=render.competitor_select_modal("run_compare", "Compare vs Competitor",
                                                          comps, channel=_menu_channel(body)))


@app.view("run_compare")
def run_compare_modal(ack, body, view, client):
    ack()
    import threading
    comp = view["state"]["values"]["competitor"]["v"]["selected_option"]["value"]
    dest = view.get("private_metadata") or body["user"]["id"]

    def work():
        from spyglass import ai as ai_mod, render
        me = db.get_self()
        my_posts = db.get_self_posts()
        if not me or not my_posts:
            client.chat_postMessage(channel=dest, text="Set + scan your account first (🪞 My Account).")
            return
        comp_posts = db.get_posts_for_competitor_name(comp)
        if not comp_posts:
            client.chat_postMessage(channel=dest, text=f"No intel on *{comp}* yet — scan it first.")
            return
        client.chat_postMessage(channel=dest, text=phrase("compare_named", me=me['name'], comp=comp))
        try:
            cmp = ai_mod.compare(me["name"], my_posts, comp, comp_posts, tone=TONE["current"])
            client.chat_postMessage(channel=dest,
                blocks=render.build_comparison_blocks(me["name"], comp, cmp, tone=TONE["current"]), text="Comparison")
        except Exception as e:
            client.chat_postMessage(channel=dest, text=f":x: {e}")
    threading.Thread(target=work, daemon=True).start()


@app.action("menu_compare")
def menu_compare(ack, body, client):
    ack()
    ch = _menu_channel(body)
    board = db.leaderboard()
    if not board:
        client.chat_postMessage(channel=ch, text="No data yet to compare. Scan first.")
        return
    medals = ["🥇", "🥈", "🥉"] + ["▪️"] * 20
    lines = [f"{medals[i]} *{r['name']}* — {r['avg']:,} avg ({r['posts']} posts)"
             for i, r in enumerate(board)]
    client.chat_postMessage(channel=ch, text="🏆 *Leaderboard*\n" + "\n".join(lines))


@app.action("menu_manage")
def menu_manage(ack, body, client):
    ack()
    from spyglass import render
    ch = _menu_channel(body)
    client.chat_postMessage(channel=ch, blocks=render.build_edit_blocks(
        db.list_competitors_with_socials()), text="Manage watchlist")


# --- Modal runners (analyze / predict / ask) — run async, post to DM -----
@app.view("run_analyze")
def run_analyze_modal(ack, body, view, client):
    ack()
    import threading
    name = view["state"]["values"]["competitor"]["v"]["selected_option"]["value"]
    dest = view.get("private_metadata") or body["user"]["id"]

    def work():
        from spyglass import flows
        client.chat_postMessage(channel=dest, text=f"🗂️ Compiling the dossier on *{name}*…")
        try:
            if flows.run_deep_analysis(client, dest, name, tone=TONE["current"]) == "none":
                client.chat_postMessage(channel=dest, text=f"No intel on *{name}* yet.")
        except Exception as e:
            client.chat_postMessage(channel=dest, text=f":x: {e}")
    threading.Thread(target=work, daemon=True).start()




@app.view("run_ask")
def run_ask_modal(ack, body, view, client):
    ack()
    import threading
    vals = view["state"]["values"]
    name = vals["competitor"]["v"]["selected_option"]["value"]
    question = vals["question"]["v"]["value"]
    dest = view.get("private_metadata") or body["user"]["id"]

    def work():
        from spyglass import ai as ai_mod
        posts = db.get_posts_for_competitor_name(name) or db.recent_posts_all()
        if not posts:
            client.chat_postMessage(channel=dest, text="No intel stored yet — scan first.")
            return
        try:
            answer = ai_mod.ask(question, posts, tone=TONE["current"])
            client.chat_postMessage(channel=dest,
                                    text=f"🔍 *You asked about {name}:*\n{answer}")
        except Exception as e:
            client.chat_postMessage(channel=dest, text=f":x: {e}")
    threading.Thread(target=work, daemon=True).start()


# --- /spy edit interactive handlers -------------------------------------
def _repost_watchlist(client, channel, note):
    """Confirmation + freshly-rendered Manage Watchlist panel, in the channel."""
    from spyglass import render
    if channel:
        client.chat_postMessage(channel=channel, text=note)
        client.chat_postMessage(channel=channel,
                                blocks=render.build_edit_blocks(db.list_competitors_with_socials()),
                                text="Manage watchlist")


@app.action("edit_add")
def act_edit_add(ack, body, client):
    ack()
    cid = body["actions"][0]["value"]
    comp = db.get_competitor(cid)
    from spyglass import render
    client.views_open(trigger_id=body["trigger_id"],
                      view=render.add_platform_modal(cid, comp["name"] if comp else "competitor",
                                                     channel=_menu_channel(body)))


@app.action("edit_replace")
def act_edit_replace(ack, body, client):
    ack()
    cid = body["actions"][0]["value"]
    comp = db.get_competitor(cid)
    socials = [s for c in db.list_competitors_with_socials()
               if c["id"] == cid for s in c["socials"]]
    if not socials:
        client.chat_postEphemeral(channel=_menu_channel(body), user=body["user"]["id"],
                                  text="No platforms to replace yet — use ➕ Add platform first.")
        return
    from spyglass import render
    client.views_open(trigger_id=body["trigger_id"],
                      view=render.replace_platform_modal(cid, comp["name"] if comp else "competitor",
                                                         socials, channel=_menu_channel(body)))


@app.action("edit_remove_open")
def act_edit_remove_open(ack, body, client):
    ack()
    cid = body["actions"][0]["value"]
    comp = db.get_competitor(cid)
    socials = [s for c in db.list_competitors_with_socials()
               if c["id"] == cid for s in c["socials"]]
    from spyglass import render
    client.views_open(trigger_id=body["trigger_id"],
                      view=render.remove_modal(cid, comp["name"] if comp else "competitor",
                                               socials, channel=_menu_channel(body)))


@app.view("edit_remove_submit")
def view_edit_remove(ack, body, view, client):
    ack()
    cid, _, channel = view["private_metadata"].partition("|")
    target = view["state"]["values"]["target"]["v"]["selected_option"]["value"]
    comp = db.get_competitor(cid)
    name = comp["name"] if comp else "Competitor"
    if target == "ALL":
        db.remove_competitor(cid)
        note = f"🗑 Removed *{name}* and all its platforms."
    else:
        db.remove_social(target)
        note = f"🗑 Removed one platform from *{name}*."
    _repost_watchlist(client, channel or body["user"]["id"], note)


@app.view("edit_add_submit")
def view_edit_add(ack, body, view, client):
    ack()
    cid, _, channel = view["private_metadata"].partition("|")
    vals = view["state"]["values"]
    platform = vals["platform"]["v"]["selected_option"]["value"]
    url = vals["url"]["v"]["value"].strip()
    db.add_social_to_competitor(cid, platform, url)
    comp = db.get_competitor(cid)
    name = comp["name"] if comp else "competitor"
    _repost_watchlist(client, channel or body["user"]["id"],
                      f"✅ Added *{platform}* to *{name}* — SpyGlass is now watching it.")


@app.view("edit_replace_submit")
def view_edit_replace(ack, body, view, client):
    ack()
    _cid, _, channel = view["private_metadata"].partition("|")
    vals = view["state"]["values"]
    social_id = vals["which"]["v"]["selected_option"]["value"]
    platform = vals["platform"]["v"]["selected_option"]["value"]
    url = vals["url"]["v"]["value"].strip()
    db.replace_social(social_id, platform, url)
    _repost_watchlist(client, channel or body["user"]["id"],
                      f"🔁 Replaced — now watching *{platform}*: {url}")


@app.command("/tone")
def handle_tone(ack, respond, command):
    ack()
    choice = (command.get("text") or "").strip().lower()
    if choice in ("sherlock", "default"):
        TONE["current"] = choice
        msg = ("🎩 *The game is afoot.* SpyGlass now deduces in the manner of Sherlock Holmes."
               if choice == "sherlock" else "Tone reset to default analyst.")
        respond(msg)
    else:
        respond("Usage: `/tone sherlock` or `/tone default`")


def _answer_from_intel(question: str) -> str:
    """Shared brain: detect competitor, pull their intel from Supabase, answer."""
    def _norm(s):
        return "".join(ch for ch in s.lower() if ch.isalnum())
    nq = _norm(question)
    matched = next((c["name"] for c in db.list_competitors_with_socials()
                    if _norm(c["name"]) in nq), None)
    posts = (db.get_posts_for_competitor_name(matched) if matched
             else db.recent_posts_all())
    if not posts:
        return "No intel stored yet — run a scan first (`/spy` → 🔍 Scan Now)."
    from spyglass import ai as ai_mod
    return ai_mod.ask(question, posts, tone=TONE["current"])


# --- @mention: conversational, answers from Supabase --------------------
@app.event("app_mention")
def handle_mention(event, say, client):
    text = re.sub(r"<@[\w]+>", "", event.get("text", "")).strip()
    if not text:
        say(text="🔍 Ask me anything about your competitors, or use `/spy` for the menu.",
            thread_ts=event.get("ts"))
        return
    say(text=f"🔍 {_answer_from_intel(text)}", thread_ts=event.get("ts"))


# --- Slack Assistant chat pane (Slack AI surface) -----------------------
try:
    from slack_bolt import Assistant
    assistant = Assistant()

    @assistant.thread_started
    def _assistant_start(say, set_suggested_prompts):
        say("🔍 *SpyGlass here.* Ask me anything about the competitors I'm watching — "
            "I answer from the intel I've gathered, not guesses.")
        try:
            set_suggested_prompts(prompts=[
                {"title": "This week's moves", "message": "What did my competitors post this week?"},
                {"title": "Best hook", "message": "Which competitor has the best-performing hooks?"},
                {"title": "How to counter", "message": "How can we overcome our top competitor?"},
            ])
        except Exception:
            pass

    @assistant.user_message
    def _assistant_reply(payload, say, set_status):
        try:
            set_status("digging through the intel…")
        except Exception:
            pass
        say(_answer_from_intel(payload.get("text", "")))

    app.assistant(assistant)
    print("Assistant chat pane wired")
except Exception as _e:
    print(f"Assistant not available: {_e}")


# --- daily auto-report scheduler ------------------------------------------
def _scheduler():
    """Runs the daily flow once per day at DAILY_HOUR in SCHEDULE_TZ (default 06:00 Asia/Kolkata / IST).
    Render servers run in UTC, so we convert explicitly — otherwise DAILY_HOUR=6 would mean 6am UTC (11:30am IST)."""
    import time
    import datetime as dt
    # Off by default — the daily scan re-scrapes every competitor through Apify and
    # burns credits. Set DAILY_ENABLED=1 to turn it back on (e.g. for a live demo).
    if os.environ.get("DAILY_ENABLED", "0") not in ("1", "true", "True"):
        print("[scheduler] daily auto-scan DISABLED (set DAILY_ENABLED=1 to enable)")
        return
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(os.environ.get("SCHEDULE_TZ", "Asia/Kolkata"))
    except Exception:
        tz = dt.timezone(dt.timedelta(hours=5, minutes=30))  # IST has no DST — fixed offset is always correct
    from spyglass import flows
    hour = int(os.environ.get("DAILY_HOUR", "6"))
    last_run_date = None
    print(f"[scheduler] armed: daily brief at {hour:02d}:00 {os.environ.get('SCHEDULE_TZ', 'Asia/Kolkata')}")
    while True:
        now = dt.datetime.now(tz)
        if now.hour == hour and last_run_date != now.date():
            try:
                socials = db.get_active_socials()
                channels = {s["competitors"].get("slack_channel") or
                            s.get("slack_channel") for s in socials}
                channels = {c for c in channels if c}
                for ch in channels or set():
                    flows.run_daily(app.client, ch, tone=TONE["current"])
                last_run_date = now.date()
                print(f"[scheduler] daily run complete {now.isoformat()}")
            except Exception as e:
                print(f"[scheduler] daily run FAILED: {e}")
                last_run_date = now.date()  # don't retry-spam credits same day
        time.sleep(300)  # check every 5 min


def _health_server():
    """Tiny HTTP server so free web hosts (Render) see an open PORT + a
    keep-alive target for an uptime pinger (prevents free-tier spin-down)."""
    import http.server
    import socketserver
    port = int(os.environ.get("PORT", "8080"))

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"SpyGlass is watching.")

        def do_HEAD(self):
            # UptimeRobot pings with HEAD by default — must answer 200.
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()

        def log_message(self, *a):
            pass

    # allow_reuse_address avoids WinError 10048 when a prior instance left the
    # port in TIME_WAIT; if it's still genuinely taken, skip quietly rather than
    # crashing a daemon thread with a scary traceback.
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", port), H) as httpd:
            httpd.serve_forever()
    except OSError as e:
        print(f"[health] port {port} unavailable ({e}); skipping health server (Slack socket unaffected)")


if __name__ == "__main__":
    import threading
    threading.Thread(target=_health_server, daemon=True).start()
    threading.Thread(target=_scheduler, daemon=True).start()
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("SpyGlass running (Socket Mode) — health server + daily scheduler armed")
    handler.start()
