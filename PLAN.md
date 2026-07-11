# SpyGlass — Build Order

## Phase 0 — Foundation (in progress)
- [x] Repo scaffold (README, requirements, .env.example)
- [x] Supabase schema (competitors / posts / metric_snapshots)
- [x] Bolt app skeleton + `/setcomp` (Socket Mode)
- [ ] Slack app created + tokens (Abhay)
- [ ] Supabase project created + schema applied
- [ ] Bot runs, `/setcomp` responds in Slack

## Phase 1 — MVP spine (demo core)
- [ ] `/setcomp <url>` → store competitor in Supabase
- [ ] `/spy check <name>` → scrape latest posts (hero platform first)
- [ ] AI analyze: hook · hook_type · content_type · strategy
- [ ] Post result as Block Kit card + Slack Canvas
- [ ] `/spy ask <name>` → answer from stored intel (RTS + AI)

## Phase 2 — Automation + growth
- [ ] Scheduled daily scan → channel alert on new post
- [ ] Weekly re-sync of old posts → metric_snapshots (growth delta)
- [ ] "strategy vs luck" growth verdict

## Phase 3 — MCP + polish
- [ ] Expose tools as SpyGlass MCP server (setcomp/check/ask)
- [ ] Multi-platform (add 2nd + 3rd source)
- [ ] Architecture diagram
- [ ] Demo video (<3 min) + submission text

## Stretch
- [ ] PDF report builder
- [ ] Feature-gap analysis (where they push vs neglect)
- [ ] Predict next move + motive
- [ ] `/tone` easter egg — switch AI voice to Sherlock Holmes (detective persona for competitor deduction)

## Command roadmap
- `/setcomp <url>` — add competitor (Phase 0 ✅ scaffolded)
- `/spy check <name>` — force scan + analysis
- `/spy ask <name>` — query stored intel
- `/spy list` — show tracked competitors
- `/tone <sherlock|default>` — switch AI persona (easter egg)

## Decisions pending (Abhay)
- Hero platform #1 for the demo (recommend: **YouTube** = rock-solid public metrics via free API, OR **LinkedIn** via your Apify actor)
- Which AI model for analysis (OpenRouter default?)
