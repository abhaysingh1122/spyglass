# SpyGlass — Orchestration Flows (build contract)

> Credit-discipline is law: only locked-in competitors, only NEW posts (incremental),
> one AI call per batch. Never re-scrape what we already have.

## Flow 1 — Daily Task (from Abhay's Excalidraw)

```
Daily trigger (cron)
  ├─ Load locked-in competitors
  └─ Fetch their social handles from Supabase
        → Skip socials with no handle (don't scrape what we don't have)
        → For each platform: INCREMENTAL scrape via Apify
             (fetch latest small N → filter posted_at > last_scraped_at → dedup by post_url)
        → Save NEW posts + per-platform details to Supabase (each platform stored separately)
        → Update last_scraped_at per competitor-platform
  → AI Agent (single pass over the day's new posts):
        - drafts documented brief message
        - drafts a Word (.docx) document
        - posts brief to Slack + attaches the .docx
        - brief = which competitor posted, how long ago, engagement; may cover >1 post
```

### Incremental scraping note
Apify actors have NO native "since date" filter (only maxPosts / resultsLimit / maxItems).
So incremental = fetch latest small N, filter `posted_at > last_scraped_at` in code, dedup by
`post_url`, save only new. Keeps credits minimal, never double-saves.

### Requires (table design)
- `last_scraped_at` per competitor-platform (the incremental cutoff)
- per-platform detail storage (separate fields/tables per social)

### Word doc → Slack
Generate .docx (python-docx) → upload via Slack `files_upload_v2`.

---

## Flow 2+ — (pending from Abhay)
- On-demand `/spy ask <competitor>`
- Manual trigger / re-scan
- Weekly re-sync for growth tracking (metric snapshots over time)
- Hook/strategy analysis ("growth by strategy or luck?")
