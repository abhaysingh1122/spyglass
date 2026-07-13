# SpyGlass — Devpost Submission Copy

Paste-ready. Edit anything that doesn't sound like you — it should sound like you, not like a press release.

---

## ELEVATOR PITCH (one line, ~200 char limit)

> SpyGlass watches your competitors on LinkedIn, Instagram and X — then turns the lens around and audits you, so you know exactly what to copy and what you can't.

**Alternates:**
- "A Slack agent that spies on your competitors' content — and then tells you, honestly, why you're losing to them."
- "Competitor intel in Slack. It scrapes their posts, audits yours, and separates what you can copy from what you can't."

---

## ABOUT THE PROJECT

### Inspiration

Every company says "keep an eye on the competition." Almost nobody actually does it.

Because doing it properly means opening LinkedIn, Instagram and X every single morning, scrolling through what your competitors posted, trying to remember what they did last week, and then guessing which of it is actually working. Nobody has time for that, so it just doesn't happen — or it happens once, badly, in a spreadsheet that dies in three weeks.

I wanted something that just sat in Slack, where my team already lives, and did that job on its own.

But halfway through building it I realised the "watch your competitor" part is the easy half, and honestly the boring half. Knowing that a competitor got 400 likes tells you nothing you can act on. The question I actually cared about was: **why are they beating me, and which part of that can I even copy?**

Because some of it you can't. If someone has two million followers, you're not copying that this week. But their hooks, their posting rhythm, their formats — you can copy those today.

So SpyGlass does something most tools refuse to do: it turns the lens around and audits *you* too. It's not flattering. That's the point.

### What it does

- You add a competitor with one command: `/setcomp <their LinkedIn / Instagram / X / website>`
- It scrapes their post history and keeps watching — new posts land in your Slack channel as intel, automatically
- `/spy analyze <name>` builds a full content dossier — their hooks, cadence, top-performing topics — and drops a Word document into the channel
- `/spy check <your own name>` audits **you**: it pulls your whole history and tells you the truth about your cadence, your hooks, and your engagement
- **Compare vs** puts you head-to-head with a competitor and splits the gap into two lists — **STRUCTURAL** (things you can't copy, like follower count) and **ALGORITHMIC** (things you can copy, today). That second list is the strategy.
- You can just ask it anything in plain English, right in Slack.

### How I built it

The whole thing runs as a Slack Bolt (Python) app in **Socket Mode**, so there's no public webhook to expose and nothing to leave open on the internet. It's deployed on Render and holds a persistent socket to Slack.

- **Slack** — slash commands, Block Kit buttons and modals, the Assistant pane, plus @mentions. Everything happens where the user already is. No dashboard, no second tab. That was a hard rule.
- **Apify** — three actors for the three platforms: `harvestapi/linkedin-profile-posts` for LinkedIn, `apify/instagram-post-scraper` for Instagram, `parseforge/x-com-scraper` for X.
- **Firecrawl** — for competitor websites, so it can spot new articles and newsroom posts too.
- **Supabase (Postgres)** — competitors, their social accounts, every post, and engagement snapshots over time.
- **OpenRouter → MiniMax M3** — one tight, single-shot call per analysis rather than a chatty agent loop, which keeps it fast and cheap.

The most important architectural decision was about **honesty**, and it shaped everything else.

An LLM handed a pile of scraped posts will absolutely invent statistics. It will tell you a competitor "posts 3x more video" when it has never seen a single video. That's worse than useless in an intel tool — if one number is fake, you can't trust any of them.

So I split the job in two:
- **Every number is computed in Python**, from the actual rows in the database. Average engagement, posting cadence, consistency, comment-to-like ratio — all arithmetic, no model involved.
- **The model only gets to interpret**, never to count. And every prompt carries a grounding guardrail that forbids inventing a statistic and forces it to hedge inferences ("suggests", "likely") instead of stating them as fact.

Then I checked it. I ran the self-audit on my own LinkedIn and verified every single claim against the raw data by hand — 7 posts, average engagement of 33, a 14.6% comment-to-like ratio, exactly 4 total shares. Every number it reported was correct. Nothing was invented.

### Challenges I ran into

**The AI kept making things up, and I had to kill features because of it.**
I built a "predict what they'll post next" feature. It looked amazing. It was also completely fabricated — it invented a product launch that didn't exist and criticised the competitor for "neglecting video" when video wasn't in the data at all. I deleted the whole feature. I also built a growth-over-time chart, and cut that too, because with thin data it was just drawing confident lines through noise. Cutting features you've already built is miserable, but shipping a tool that lies confidently is worse.

**LinkedIn's scraper returns comments as posts.**
The actor returns comments and posts in the same list, distinguished only by a `type` field. So my first runs cheerfully saved other people's comments as competitor posts and analysed them. Every engagement number downstream was quietly wrong. I had to split them apart and re-attach comments to their parent post.

**Slack lets a bot post text into a channel it isn't in — but not files.**
`chat.postMessage` works in a public channel without joining it. `files.upload` does not. So in a fresh channel the text intel arrived perfectly and the Word document just... didn't, with no error anywhere the user could see. The bot now joins the channel first, and if an upload still fails it says so out loud in the channel instead of dying silently in a log file.

**Scraped posts break JSON.**
People write posts full of quotes and line breaks. The model embeds that text into a JSON string, doesn't always escape it, and the parser dies with `Expecting ',' delimiter`. Worse, I had written repair logic for exactly this — and a bug meant it could never actually run. Now it escalates: strict parse, then lenient, then structural repair.

**Free-tier hosting sleeps.**
Render spins a free service down after 15 minutes, which quietly kills the Slack socket. A keep-alive ping fixed it — but the pinger sends `HEAD`, and my health endpoint only answered `GET`, so it returned 501 and I thought the whole deploy was broken.

### What I learned

That in any tool whose entire value is *telling you the truth about your numbers*, the guardrail isn't a feature — it's the product. The moment a competitor-intel tool invents one statistic, every other number it ever shows you is worthless.

Also: the honest version of a feature is usually smaller than the impressive version. I shipped fewer features than I designed, and the tool is better for it.

### What's next

- Weekly digest — what changed across every competitor in one Monday message
- Alerting on a competitor's breakout post the moment it takes off, not the next morning
- Making the comparison two-sided: not just "why they win", but "what they're bad at that you're already better at"

---

## BUILT WITH

```
python, slack-bolt, slack-api, socket-mode, block-kit, supabase, postgresql,
apify, firecrawl, openrouter, minimax, render, python-docx
```

---

## TRY IT OUT (links)

- GitHub repo: `https://github.com/abhaysingh1122/spyglass`
- Slack developer sandbox: `https://spyglass.enterprise.slack.com`

### Judge access checklist (do BEFORE submitting)
- [ ] Invite `slackhack@salesforce.com` to the sandbox
- [ ] Invite `testing@devpost.com` to the sandbox
- [ ] SpyGlass app installed in the sandbox workspace
- [ ] `#spyglass` channel exists, bot is a member
- [ ] 2-3 competitors pre-loaded so /spy compare and /spy analyze return data instantly
- [ ] Pinned message in the channel: "Start here -> type /spy"

---

## SUBMISSION FIELD ANSWERS

| Field | Answer |
|---|---|
| **Track** | New Slack Agent |
| **Team** | Individual (solo) |
| **Country of residence** | India |
| **Video demo link** | YouTube link (public / unlisted-public — must be publicly visible) |
| **Slack App ID** | A0BF7UYF0QZ |
