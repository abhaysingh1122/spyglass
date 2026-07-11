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

_apify = None


def apify() -> ApifyClient:
    global _apify
    if _apify is None:
        _apify = ApifyClient(os.environ["APIFY_TOKEN"])
    return _apify


def _dataset_items(run) -> list:
    """apify-client may return a Run object or dict depending on version."""
    ds_id = getattr(run, "default_dataset_id", None) or (
        run.get("defaultDatasetId") if isinstance(run, dict) else None)
    return list(apify().dataset(ds_id).iterate_items())


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
    run = apify().actor("harvestapi/linkedin-profile-posts").call(run_input=run_input)
    return _dataset_items(run)


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
    run = apify().actor("harvestapi/linkedin-profile-posts").call(run_input=run_input)
    return _dataset_items(run)


# --- Instagram: apify/instagram-post-scraper ----------------------------
def instagram_posts(usernames, results_limit=10, detail_level="basicData") -> list:
    run_input = {
        "username": usernames,              # handle, profile url, or post url
        "resultsLimit": results_limit,
        "dataDetailLevel": detail_level,
    }
    run = apify().actor("apify/instagram-post-scraper").call(run_input=run_input)
    return _dataset_items(run)


# --- Twitter/X: parseforge/x-com-scraper --------------------------------
def twitter_posts(usernames, max_items=10) -> list:
    run_input = {"maxItems": max_items, "usernames": usernames}
    run = apify().actor("parseforge/x-com-scraper").call(run_input=run_input)
    return _dataset_items(run)


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
