# SpyGlass 🔍

**Competitor intelligence agent for Slack.** Add a competitor once — your team wakes up to their every move, analyzed, right inside Slack.

Built for the **Slack Agent Builder Challenge** (Track: New Slack Agent).

---

## What it does

1. **`/setcomp <url>`** — register a competitor (LinkedIn / Insta / X / YouTube / website).
2. **Watches** their handles daily; captures new posts + re-syncs old posts weekly to track growth.
3. **AI analyzes** each post: hooks, content type, engagement, strategy, pain-points — and asks *"did this grow by strategy or luck?"*
4. **Slack** = the interface: daily alerts, ask-anything (`/spy ask <competitor>`), manual re-scan (`/spy check <competitor>`).
5. Intelligence lives in Slack as **Canvases + Block Kit cards**; **Supabase** is the engine's memory.

## Architecture

```
Slack (Bolt + Block Kit + Canvas)
   ⇄ SpyGlass MCP server  →  tools: setcomp · check · ask · analyze
        ⇄ Data sources: Apify (LinkedIn/Insta) · YouTube Data API · Firecrawl (web)
        ⇄ AI analysis (hooks / strategy / growth delta)
        ⇄ Supabase (competitors · posts · metric snapshots)
   + Real-Time Search API  →  "show me everything on <competitor>"
```

**Required Slack tech used:** MCP server integration + Real-Time Search API + Slack AI surface.

## Tech
- Python 3.12 · slack-bolt (Socket Mode)
- Supabase (Postgres) for storage + time-series growth
- Apify · YouTube Data API · Firecrawl for sources
- OpenRouter / Gemini for analysis

## Status
🚧 Scaffolding. See `PLAN.md` for build order.
