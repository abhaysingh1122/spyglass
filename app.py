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


def derive_name(url: str) -> str:
    slug = re.sub(r"[?#].*$", "", url.rstrip("/")).split("/")[-1]
    slug = slug.replace("-", " ").replace("_", " ").strip()
    return slug.title() if slug else url


# --- /setcomp ------------------------------------------------------------
@app.command("/setcomp")
def handle_setcomp(ack, respond, command):
    ack()  # must respond within 3s
    text = (command.get("text") or "").strip()
    match = URL_RE.search(text)
    if not match:
        respond(":warning: Usage: `/setcomp https://linkedin.com/company/acme`")
        return
    url = match.group(0)
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
    header = "🔍 Already watching this competitor" if existed else "🔍 Competitor locked in"
    respond(
        blocks=[
            {"type": "header", "text": {"type": "plain_text", "text": header}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Name:*\n{name}"},
                {"type": "mrkdwn", "text": f"*Platform:*\n{platform}"},
                {"type": "mrkdwn", "text": f"*Handle:*\n<{url}>"},
            ]},
            {"type": "context", "elements": [
                {"type": "mrkdwn", "text": "SpyGlass is now watching. Daily scans will surface their new posts here."}
            ]},
        ],
        text=f"Competitor locked in: {name} ({platform})",
    )


# --- /spy router: check | list | ask ------------------------------------
TONE = {"current": "default"}  # /tone easter egg state


@app.command("/spy")
def handle_spy(ack, respond, command, client):
    ack()
    text = (command.get("text") or "").strip()
    sub, _, rest = text.partition(" ")
    sub = sub.lower()

    if sub == "check":
        target = rest.strip() or None
        scope = f" on *{target}*" if target else ""
        respond(f"🔍 SpyGlass is on the case{scope} — scanning now…")
        from spyglass import flows
        try:
            status = flows.run_daily(client, command.get("channel_id"),
                                     tone=TONE["current"], name_filter=target)
        except Exception as e:
            respond(f":x: Scan failed:\n```{e}```")
            return
        if status == "quiet":
            respond("🕯️ Nothing new in the last 24h, and no posts due a growth re-check. "
                    "The street is quiet.")
    elif sub == "analyze":
        target = rest.strip()
        if not target:
            respond("Usage: `/spy analyze <competitor>` — e.g. `/spy analyze openai`")
            return
        respond(f"🗂️ Compiling the content dossier on *{target}* — pulling a month of posts, "
                "decoding the playbook. Give me a minute…")
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
        respond("🔍 *Watchlist:*\n" + "\n".join(lines))
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
            f"🔍 *SpyGlass Status*\n"
            f"*Competitors:* {s['competitors']}   *Posts tracked:* {s['posts']}   "
            f"*Briefs sent:* {s['briefs']}\n\n*Watched socials:*\n{watched}")
    elif sub == "edit":
        from spyglass import render
        respond(blocks=render.build_edit_blocks(db.list_competitors_with_socials()),
                text="Manage watchlist")
    elif sub == "predict":
        target = rest.strip()
        if not target:
            respond("Usage: `/spy predict <competitor>` — forecast their next moves")
            return
        respond(f"🔮 Reading *{target}*'s patterns to forecast their next moves…")
        from spyglass import ai as ai_mod, render
        posts = db.get_posts_for_competitor_name(target)
        if not posts:
            respond(f"No stored intel on *{target}* yet. Run `/spy analyze {target}` first.")
            return
        try:
            pred = ai_mod.predict(target, posts, tone=TONE["current"])
        except Exception as e:
            respond(f":x: Prediction failed:\n```{e}```")
            return
        respond(blocks=render.build_prediction_blocks(target, pred),
                text=f"SpyGlass forecast — {target}")
    elif sub == "compare":
        board = db.leaderboard()
        if not board:
            respond("No data yet to compare. Run `/spy check` first.")
            return
        medals = ["🥇", "🥈", "🥉"] + ["▪️"] * 20
        lines = [f"{medals[i]} *{r['name']}* — {r['avg']:,} avg engagement "
                 f"({r['posts']} posts · {r['likes']:,}👍 {r['comments']:,}💬 {r['shares']:,}🔁)"
                 for i, r in enumerate(board)]
        respond("🏆 *Competitor Leaderboard* (by avg engagement)\n" + "\n".join(lines))
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
    client.chat_postMessage(channel=ch, text="🔍 SpyGlass is scanning your competitors now…")
    from spyglass import flows

    def work():
        try:
            status = flows.run_daily(client, ch, tone=TONE["current"])
            if status == "quiet":
                client.chat_postMessage(channel=ch, text="🕯️ Nothing new in the last 24h. The street is quiet.")
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


@app.action("menu_predict")
def menu_predict(ack, body, client):
    ack()
    from spyglass import render
    client.views_open(trigger_id=body["trigger_id"],
                      view=render.competitor_select_modal("run_predict", "Predict Next Moves",
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


@app.view("run_predict")
def run_predict_modal(ack, body, view, client):
    ack()
    import threading
    name = view["state"]["values"]["competitor"]["v"]["selected_option"]["value"]
    dest = view.get("private_metadata") or body["user"]["id"]

    def work():
        from spyglass import ai as ai_mod, render
        posts = db.get_posts_for_competitor_name(name)
        if not posts:
            client.chat_postMessage(channel=dest, text=f"No intel on *{name}* yet — analyze first.")
            return
        try:
            pred = ai_mod.predict(name, posts, tone=TONE["current"])
            client.chat_postMessage(channel=dest, blocks=render.build_prediction_blocks(name, pred),
                                    text=f"Forecast — {name}")
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


@app.action("edit_remove_comp")
def act_edit_remove(ack, body, client):
    ack()
    comp = db.get_competitor(body["actions"][0]["value"])
    name = comp["name"] if comp else "Competitor"
    db.remove_competitor(body["actions"][0]["value"])
    _repost_watchlist(client, _menu_channel(body), f"🗑 Removed *{name}* from the watchlist.")


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
    """Runs the daily flow automatically once per day at DAILY_HOUR local time."""
    import time
    import datetime as dt
    from spyglass import flows
    hour = int(os.environ.get("DAILY_HOUR", "9"))
    last_run_date = None
    while True:
        now = dt.datetime.now()
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

    with socketserver.TCPServer(("", port), H) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    import threading
    threading.Thread(target=_health_server, daemon=True).start()
    threading.Thread(target=_scheduler, daemon=True).start()
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("SpyGlass running (Socket Mode) — health server + daily scheduler armed")
    handler.start()
