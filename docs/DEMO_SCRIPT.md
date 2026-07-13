# SpyGlass — FULL Demo Video Runbook

**Length:** 2:50 (hard cap 3:00)
**Format:** Screen recording of Slack ONLY. No face. No live mic.
**Voice:** AI voiceover generated from the VO lines (or read aloud).
**Music:** Royalty-free ONLY — copyrighted music breaks the rules.
**Captions:** Burn in. Judges may watch muted.

---

# PART A — BEFORE YOU HIT RECORD

Do all of this FIRST. Do not record until every box is ticked.

- [ ] Bot is live and replying (fire one test command, confirm you get a reply)
- [ ] **2+ competitors already added** — so `/spy compare` has real data to show
- [ ] **Your own account already set** (`/spy setself <your linkedin url>`) and backfilled
- [ ] Slack window is CLEAN: close DMs, hide unrelated channels, no personal info on screen
- [ ] Zoom Slack to ~125% (Ctrl +) so text survives YouTube compression
- [ ] Record 1080p, screen only
- [ ] Create a fresh channel named `#spyglass` so it looks purposeful, not like a test dump

**IMPORTANT:** Run every command ONCE before recording. The scrapes take time. If a command is slow on camera, you cut the dead air out in editing — but you don't want a *failure* on camera.

---

# PART B — THE SHOT LIST (record in this exact order)

---

## 🎬 SHOT 1 — THE OPEN (0:00 – 0:08)

**START HERE. This is your first frame.**

**SCREEN:** A clean, empty `#spyglass` Slack channel. Nothing else. Hold still for 2 seconds.

**VO:**
> "Every company says: keep an eye on the competition."

**SCREEN:** Now slowly type `/spy` into the message box. Don't hit enter yet — let them read it.

**VO:**
> "Almost nobody actually does."

---

## 🎬 SHOT 2 — THE MENU (0:08 – 0:22)

**SCREEN:** Hit Enter on `/spy`. The button menu renders (🔍 Scan · 🗂️ Analyze · 💬 Ask · 🪞 My Account · 🏆 Compare · ⚙️ Manage). Let the buttons land on screen. Hold 2 seconds.

**VO:**
> "Because doing it properly means scrolling LinkedIn, Instagram and X every single day — and then guessing what's actually working."
> "SpyGlass does it for you. And it lives where your team already is. Slack."

---

## 🎬 SHOT 3 — ADD A COMPETITOR (0:22 – 0:40)

**SCREEN:** Type and send:
```
/setcomp https://www.linkedin.com/in/<competitor-handle>
```
Confirmation message appears.

**VO:**
> "Setup is one command. You point it at a competitor — a LinkedIn profile, an Instagram, an X account, or just their website."
> "SpyGlass pulls their post history, and starts watching."

---

## 🎬 SHOT 4 — THE DAILY INTEL (0:40 – 1:08)

**SCREEN:** Type and send:
```
/spy check <competitor name>
```
Show the "scanning" state, then the intel card rendering — new posts, engagement numbers.

*(In editing: cut the waiting time. Scan → card should feel instant.)*

**VO:**
> "Every morning, SpyGlass scans for anything new — and drops the intel straight into your channel."
> "What they posted. How it performed. What's working for them right now."
> "There's no dashboard to check. No extra tab. It comes to you."

---

## 🎬 SHOT 5 — THE DOSSIER (1:08 – 1:32)

**SCREEN:** Type and send:
```
/spy analyze <competitor name>
```
The dossier blocks render. **Then the Word document appears in the channel.** Click it — show the doc open for ~2 seconds, then close.

**VO:**
> "Push it further, and it builds a full content dossier."
> "Their hooks. Their posting cadence. The topics that actually land."
> "And it hands you a Word document you can walk straight into a meeting with."

---

## 🎬 SHOT 6 — ⭐ THE TWIST: IT AUDITS *YOU* (1:32 – 2:08)

**THIS IS THE MOST IMPORTANT SHOT IN THE VIDEO. Do not rush it.**

**SCREEN:** Click the 🪞 **My Account** button → panel opens → click **🪞 Audit me**. The self-audit renders: profile read, what's working, pain points, quick wins.

**Slowly scroll** through the pain points. Let the judges READ them.

**VO:**
> "But here's where SpyGlass is different."
> "Every other tool watches other people. SpyGlass turns the lens around — and audits *you*."
> "It pulls your entire post history, and it tells you the truth. Your cadence is thin. Your hooks are inconsistent. Your posts get likes — but almost nobody shares them."
> "And every single number on this screen was computed from your real, scraped data. Not guessed. Not invented."

---

## 🎬 SHOT 7 — PROFILE VS PROFILE (2:08 – 2:38)

**SCREEN:** Click ⚔️ **Compare vs** → select a competitor → the comparison renders.

**HOLD AND PAUSE on the ALGORITHMIC vs STRUCTURAL split.** This is the money shot — make sure it's legible.

**VO:**
> "Then it puts you head to head — and answers the only question that actually matters."
> "*Why* are they winning?"
> "And it splits the answer in two. Structural: the things you can't copy — like a follower base ten times your size."
> "And algorithmic: the things you *can* copy. Today."
> "That second list isn't analysis. That's your strategy."

---

## 🎬 SHOT 8 — GROUNDED, NOT HALLUCINATED (2:38 – 2:50)

**SCREEN:** Type a real question in plain English:
```
/spy what should I post this week to close the gap?
```
The grounded answer renders. Then let the screen rest on the SpyGlass menu for the final 2 seconds.

**VO:**
> "And you can just… ask it. In plain English. Right in Slack."
> "Every answer is grounded in real scraped data — with a guardrail that stops it inventing statistics."
> *(beat)*
> "**SpyGlass. It watches them. And it watches you.**"

**SCREEN:** Fade to black. End.

---

# PART C — EDITING NOTES

1. **Cut ALL dead air.** Every scrape takes seconds — the viewer should never wait. Command → result should feel instant.
2. **Burn in captions.** Judges watch muted.
3. **Zoom in** on the pain points (Shot 6) and the algorithmic/structural split (Shot 7). Those two screens win you the hackathon — make them impossible to miss.
4. **Music:** royalty-free, low volume, subtle. Kill it under the VO.
5. **Do not exceed 3:00.** Judges are not required to watch past it.

---

# PART D — IF YOU'RE OVER TIME

Cut in this order:
1. **Shot 5 (Dossier)** — good feature, but not what wins
2. **Shot 3 (Add competitor)** — compress to a 3-second silent shot

**NEVER CUT SHOT 6 OR SHOT 7.**
Every other team in this hackathon will build a "watch your competitor" bot. Only SpyGlass turns the lens around, audits the user, and separates *what you can copy* from *what you can't*. That is the entire reason it wins. Protect those 60 seconds at all costs.
