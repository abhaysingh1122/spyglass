"""SpyGlass AI agent — n8n-agent style, credit-disciplined.

Pattern (per Abhay's n8n architecture):
  raw data in -> ONE agent call (ROLE -> RULES -> OUTPUT FORMAT) -> parse with guards after.
Never pre-summarize before the AI. Never loop per-post. One call per batch.
Model: minimax/minimax-m3 via OpenRouter.
"""
import os
import json
import re
import requests

_API = "https://openrouter.ai/api/v1/chat/completions"

# Personas — /tone easter egg
PERSONAS = {
    "default": "You are SpyGlass, a sharp competitor-intelligence analyst.",
    "sherlock": (
        "You are SpyGlass, a competitor-intelligence analyst who speaks and reasons "
        "like Sherlock Holmes: precise deductions, dry wit, 'the game is afoot' energy. "
        "Quote-worthy but never longer than needed. Deduce, don't speculate."
    ),
}


def _call(system: str, user: str, max_tokens: int = 1800) -> str:
    """Single-shot chat call. Tight prompts, low temperature, bounded output."""
    r = requests.post(
        _API,
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": os.environ.get("OPENROUTER_MODEL", "minimax/minimax-m3"),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _parse_json(text: str):
    """Guardrail code-node: strip fences, extract JSON, repair truncation. Loud on failure."""
    text = re.sub(r"```(?:json)?", "", text).strip().strip("`")
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    # Truncation repair: output started as JSON but was cut off — close open structures.
    start = text.find("{")
    if start == -1:
        raise ValueError(f"AI returned no JSON object. Raw head: {text[:300]}")
    frag = text[start:]
    frag = re.sub(r',\s*"[^"]*$', "", frag)          # drop trailing half key/value
    frag = re.sub(r':\s*"[^"]*$', ': ""', frag)      # close half-open string value
    opens = frag.count("{") - frag.count("}")
    opens_arr = frag.count("[") - frag.count("]")
    frag += "]" * max(opens_arr, 0) + "}" * max(opens, 0)
    try:
        return json.loads(frag)
    except Exception:
        raise ValueError(f"AI JSON truncated beyond repair. Raw head: {text[:300]}")


def daily_brief(new_posts: list, growth_updates: list, tone: str = "default") -> dict:
    """ONE call over the whole day's batch. Returns brief + per-post analysis."""
    system = (
        PERSONAS.get(tone, PERSONAS["default"]) + "\n"
        "You write for a marketing team that already KNOWS the numbers — they want to know "
        "WHY it works and WHAT to steal. Never write like a news reporter.\n"
        "RULES:\n"
        "1. You receive RAW scraped competitor posts (last 24h, comments included) and growth "
        "updates (7-day re-checks).\n"
        "2. For EACH new post produce:\n"
        "   - one_liner: what the post IS, <=12 words.\n"
        "   - ai_take: YOUR read — what are they really doing, why this angle, what it signals. "
        "2-3 sharp sentences. This is the star of the show.\n"
        "   - steal_this: ONE tactic our team could copy, <=15 words.\n"
        "   - hook: the exact opening line that grabs; hook_type (question/bold-claim/story/stat/"
        "contrarian/listicle); content_type (promo/thought-leadership/hiring/product/meme/case-study); "
        "strategy (one line).\n"
        "   - audience_reaction: read the scraped comments — sentiment + what people say, <=15 words.\n"
        "3. overall_pattern: 1-2 sentences — what today's posts reveal about their playbook.\n"
        "4. growth_lines: for each growth update, one line — strategy or luck, and why.\n"
        "BE CONCISE. OUTPUT FORMAT: valid JSON only, no explanation:\n"
        '{"overall_pattern": str, "growth_lines": [str], '
        '"posts": [{"post_url": str, "one_liner": str, "ai_take": str, "steal_this": str, '
        '"hook": str, "hook_type": str, "content_type": str, "strategy": str, '
        '"audience_reaction": str}]}'
    )
    user = json.dumps(
        {"new_posts_last_24h": new_posts, "growth_updates_7d": growth_updates},
        ensure_ascii=False, default=str,
    )
    return _parse_json(_call(system, user, max_tokens=4000))


def dossier(competitor: str, posts: list, tone: str = "default") -> dict:
    """Content-spy deep dive: ONE call over a month of posts -> full playbook dossier."""
    system = (
        PERSONAS.get(tone, PERSONAS["default"]) + "\n"
        f"You are compiling a CONTENT-SPY DOSSIER on '{competitor}' from their recent posts "
        "(engagement + comments included). The reader wants their PLAYBOOK decoded — what "
        "works, why, and what to steal. Insight over reporting. BE CONCISE.\n"
        "RULES:\n"
        "1. verdict: one punchy sentence — is their growth engineered strategy or luck?\n"
        "2. hook_matrix: for each hook_type they use -> {hook_type, times_used, avg_engagement, "
        "verdict (<=10 words: does it work?)}.\n"
        "3. content_mix: for each content_type -> {content_type, share_pct, note (<=10 words)}.\n"
        "4. cadence: posting rhythm in one line (frequency, timing patterns).\n"
        "5. top_post: {one_liner, why_it_won (2 sentences), engagement}.\n"
        "6. weaknesses: 2-3 gaps in their content game we can exploit (each <=15 words).\n"
        "7. playbook: 3-4 concrete tactics OUR team should copy, each <=15 words.\n"
        "OUTPUT FORMAT: valid JSON only, no explanation:\n"
        '{"verdict": str, "hook_matrix": [{"hook_type": str, "times_used": int, '
        '"avg_engagement": int, "verdict": str}], "content_mix": [{"content_type": str, '
        '"share_pct": int, "note": str}], "cadence": str, '
        '"top_post": {"one_liner": str, "why_it_won": str, "engagement": str}, '
        '"weaknesses": [str], "playbook": [str]}'
    )
    slim = [{k: p.get(k) for k in ("post_url", "content", "posted_at", "likes",
                                    "comments", "shares", "media_type", "hook",
                                    "hook_type", "content_type")} for p in posts]
    user = json.dumps({"competitor": competitor, "posts": slim},
                      ensure_ascii=False, default=str)
    return _parse_json(_call(system, user, max_tokens=3000))


def ask(question: str, context_posts: list, tone: str = "default") -> str:
    """/spy ask — answer from stored intel. One call, plain-text answer."""
    system = (
        PERSONAS.get(tone, PERSONAS["default"]) + "\n"
        "RULES:\n"
        "1. Answer ONLY from the provided competitor data (posts, metrics, snapshots).\n"
        "2. If the data can't answer it, say what's missing — never invent numbers.\n"
        "3. <=150 words, Slack-friendly plain text.\n"
    )
    user = json.dumps({"question": question, "data": context_posts},
                      ensure_ascii=False, default=str)
    return _call(system, user, max_tokens=600)
