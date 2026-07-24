"""Source adapters — thin wrappers around Abhay's chosen Apify actors + Firecrawl.

These are PURE FUNCTIONS: nothing runs (and no credits are spent) until the
orchestration layer (built from Abhay's n8n/Excalidraw flow) calls them.

Actors (Abhay's own Apify account):
  LinkedIn   -> harvestapi/linkedin-profile-posts   (profiles, companies, single posts)
  Instagram  -> apify/instagram-post-scraper         (handle / profile url / post url)
  Twitter/X  -> parseforge/x-com-scraper             (usernames)
  Website    -> Firecrawl v2 (scrape + search)       (find site from LinkedIn, then scrape)
"""
import os
import requests
from apify_client import ApifyClient

_apify_clients = {}
_token_idx = 0


def _tokens() -> list:
    """All Apify tokens, in rotation order. Accepts either a comma-separated
    APIFY_TOKENS, or APIFY_TOKEN / APIFY_TOKEN_2 / APIFY_TOKEN_3."""
    multi = os.environ.get("APIFY_TOKENS", "")
    if multi.strip():
        toks = [t.strip() for t in multi.split(",") if t.strip()]
    else:
        toks = [os.environ.get(k, "").strip() for k in
                ("APIFY_TOKEN", "APIFY_TOKEN_2", "APIFY_TOKEN_3")]
        toks = [t for t in toks if t]
    if not toks:
        raise RuntimeError("No Apify token configured (set APIFY_TOKEN or APIFY_TOKENS)")
    return toks


def apify() -> ApifyClient:
    """Client for the token we're currently on."""
    tok = _tokens()[_token_idx % len(_tokens())]
    if tok not in _apify_clients:
        _apify_clients[tok] = ApifyClient(tok)
    return _apify_clients[tok]


def _is_quota_error(e) -> bool:
    msg = str(e).lower()
    return any(s in msg for s in
               ("usage hard limit", "monthly usage", "exceeded", "limit exceeded",
                "quota", "payment required", "402"))


def _run_actor(actor_id: str, run_input: dict):
    """Run an actor, rotating to the next token when one is out of credit.
    Returns (run, client) — the dataset lives on the account that ran it, so the
    caller must read it back with that same client."""
    global _token_idx
    toks = _tokens()
    last = None
    for attempt in range(len(toks)):
        client = apify()
        try:
            run = client.actor(actor_id).call(run_input=run_input)
            return run, client
        except Exception as e:
            last = e
            if not _is_quota_error(e):
                raise                       # a real failure — don't burn other tokens
            _token_idx += 1                 # this account is spent; move to the next
            print(f"[apify] token {attempt + 1}/{len(toks)} out of credit, rotating")
    raise RuntimeError(f"All {len(toks)} Apify tokens are out of monthly credit. "
                       f"Last error: {last}")


def _dataset_items(run, client=None) -> list:
    """apify-client may return a Run object or dict depending on version."""
    ds_id = getattr(run, "default_dataset_id", None) or (
        run.get("defaultDatasetId") if isinstance(run, dict) else None)
    return list((client or apify()).dataset(ds_id).iterate_items())


# --- LinkedIn: harvestapi/linkedin-profile-posts ------------------------
def linkedin_posts(target_urls, max_posts=5, max_reactions=5, max_comments=5) -> list:
    run_input = {
        "targetUrls": target_urls,          # profile / company / post / feed-update URLs
        "maxPosts": max_posts,
        "maxReactions": max_reactions,
        "postNestedReactions": False,
        "maxComments": max_comments,
        "postNestedComments": False,
    }
    run, client = _run_actor("harvestapi/linkedin-profile-posts", run_input)
    return _dataset_items(run, client)


def linkedin_posts_windowed(target_urls, posted_limit="24h", max_posts=20,
                            max_comments=5) -> list:
    """Timeframe-scoped fetch — the credit-safe daily scan.
    posted_limit: any | 1h | 24h | week | month | 3months | 6months | year.
    Comments embedded in each post (Abhay: post + comment analysis)."""
    run_input = {
        "targetUrls": target_urls,
        "maxPosts": max_posts,
        "postedLimit": posted_limit,
        "scrapeComments": max_comments > 0,
        "maxComments": max_comments,
        "postNestedComments": True,
        "scrapeReactions": False,
        "includeReposts": False,
        "includeQuotePosts": True,
    }
    run, client = _run_actor("harvestapi/linkedin-profile-posts", run_input)
    return _dataset_items(run, client)


# --- Instagram: apify/instagram-post-scraper ----------------------------
def instagram_posts(usernames, results_limit=10, detail_level="basicData") -> list:
    run_input = {
        "username": usernames,              # handle, profile url, or post url
        "resultsLimit": results_limit,
        "dataDetailLevel": detail_level,
    }
    run, client = _run_actor("apify/instagram-post-scraper", run_input)
    return _dataset_items(run, client)


# --- Twitter/X: parseforge/x-com-scraper --------------------------------
def twitter_posts(usernames, max_items=10) -> list:
    run_input = {"maxItems": max_items, "usernames": usernames}
    run, client = _run_actor("parseforge/x-com-scraper", run_input)
    return _dataset_items(run, client)


# --- Website: Firecrawl v2 ----------------------------------------------
_FC_BASE = "https://api.firecrawl.dev/v2"


def _fc_headers():
    return {"Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}"}


def website_scrape(url) -> dict:
    r = requests.post(f"{_FC_BASE}/scrape", headers=_fc_headers(),
                      json={"url": url, "formats": ["markdown", "links"]}, timeout=60)
    r.raise_for_status()
    return r.json()


def website_search(query, limit=3) -> dict:
    """Find a competitor's website (e.g. from their name/LinkedIn) via Firecrawl search."""
    r = requests.post(f"{_FC_BASE}/search", headers=_fc_headers(),
                      json={"query": query, "limit": limit}, timeout=60)
    r.raise_for_status()
    return r.json()
