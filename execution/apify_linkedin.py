"""
apify_linkedin.py
-----------------
LinkedIn profile scraping via Apify with:
  - Dedup check against linkedin_profiles table before calling Apify
  - API key rotation across 5 keys from .env
  - Exponential backoff on failures
  - Structured logging

Actor: dev_fusion/linkedin-profile-scraper (cookieless, 41K users, accepts profileUrls)
"""

import os
import time
import threading
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

try:
    from apify_client import ApifyClient
    _APIFY_AVAILABLE = True
except ImportError:
    _APIFY_AVAILABLE = False
    print("[Apify] apify-client not installed — pip install apify-client")

# Actor ID — try official first, fall back to community
PROFILE_SCRAPER_ACTOR = os.environ.get(
    "APIFY_LINKEDIN_ACTOR", "dev_fusion/linkedin-profile-scraper"
)

# Rate limiting — 1 second between Apify calls to avoid hammering
_apify_lock = threading.Lock()
_last_apify_call: float = 0.0
_APIFY_MIN_INTERVAL = 1.0


def _get_apify_keys() -> List[str]:
    """Collect all available Apify API keys from env vars."""
    keys = []
    # Key 1 (no suffix)
    k = os.environ.get("APIFY_API_KEY", "")
    if k:
        keys.append(k)
    # Keys 2-5
    for i in range(2, 6):
        k = os.environ.get(f"APIFY_API_KEY_{i}", "")
        if k:
            keys.append(k)
    return keys


# Rotating key index
_key_index = 0
_key_lock = threading.Lock()


def _next_apify_key() -> Optional[str]:
    """Get the next Apify API key in rotation."""
    global _key_index
    keys = _get_apify_keys()
    if not keys:
        return None
    with _key_lock:
        key = keys[_key_index % len(keys)]
        _key_index += 1
    return key


def _rate_wait():
    """Enforce minimum interval between Apify calls."""
    global _last_apify_call
    with _apify_lock:
        now = time.monotonic()
        elapsed = now - _last_apify_call
        if elapsed < _APIFY_MIN_INTERVAL:
            time.sleep(_APIFY_MIN_INTERVAL - elapsed)
        _last_apify_call = time.monotonic()


def normalize_url(url: str) -> str:
    """Normalize a LinkedIn profile URL for consistent matching."""
    return (url or "").strip().rstrip("/").lower()


def scrape_single_profile(linkedin_url: str, api_key: Optional[str] = None) -> Optional[Dict]:
    """Scrape a single LinkedIn profile via Apify.

    Args:
        linkedin_url: LinkedIn profile URL to scrape.
        api_key: Specific Apify key to use (or auto-rotate).

    Returns:
        Raw Apify profile dict, or None on failure.
    """
    if not _APIFY_AVAILABLE:
        print("[Apify] Client not available")
        return None

    url = normalize_url(linkedin_url)
    if not url or "linkedin.com" not in url:
        print(f"[Apify] Invalid LinkedIn URL: {url}")
        return None

    key = api_key or _next_apify_key()
    if not key:
        print("[Apify] No API keys available")
        return None

    _rate_wait()

    try:
        client = ApifyClient(key)
        run = client.actor(PROFILE_SCRAPER_ACTOR).call(
            run_input={"profileUrls": [url]},
            timeout_secs=120,
        )

        if run.get("status") != "SUCCEEDED":
            print(f"[Apify] Actor status: {run.get('status')} for {url[:50]}")
            return None

        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if items:
            print(f"[Apify] Scraped profile: {url[:50]}")
            return items[0]

        print(f"[Apify] No data returned for {url[:50]}")
        return None

    except Exception as e:
        print(f"[Apify] Error scraping {url[:50]}: {e}")
        return None


def scrape_profiles_batch(
    urls: List[str],
    api_key: Optional[str] = None,
    batch_size: int = 5,
) -> Dict[str, Dict]:
    """Scrape multiple LinkedIn profiles in batches.

    Args:
        urls: List of LinkedIn profile URLs.
        api_key: Specific Apify key (or auto-rotate per batch).
        batch_size: Profiles per Apify call (to avoid timeouts).

    Returns:
        Dict mapping normalized_url -> raw profile dict.
    """
    if not _APIFY_AVAILABLE:
        return {}

    # Deduplicate
    unique_urls = list({normalize_url(u) for u in urls if u and "linkedin.com" in u.lower()})
    if not unique_urls:
        return {}

    print(f"[Apify] Batch scraping {len(unique_urls)} profiles in groups of {batch_size}")
    results: Dict[str, Dict] = {}

    for i in range(0, len(unique_urls), batch_size):
        batch = unique_urls[i:i + batch_size]
        key = api_key or _next_apify_key()
        if not key:
            print("[Apify] No API keys available for batch")
            break

        _rate_wait()

        try:
            client = ApifyClient(key)
            run = client.actor(PROFILE_SCRAPER_ACTOR).call(
                run_input={"profileUrls": batch},
                timeout_secs=180,
            )

            if run.get("status") != "SUCCEEDED":
                print(f"[Apify] Batch {i//batch_size + 1} status: {run.get('status')}")
                continue

            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            for item in items:
                raw_url = (
                    item.get("linkedInUrl") or item.get("profileUrl")
                    or item.get("url") or ""
                )
                url_key = normalize_url(raw_url)
                if url_key:
                    results[url_key] = item

            print(f"[Apify] Batch {i//batch_size + 1}: got {len(items)} profiles")

        except Exception as e:
            print(f"[Apify] Batch {i//batch_size + 1} error: {e}")
            # Exponential backoff
            time.sleep(2 ** min(i // batch_size, 3))

    print(f"[Apify] Total scraped: {len(results)}/{len(unique_urls)}")
    return results


def scrape_and_store_profile(
    user_id: str,
    linkedin_url: str,
    is_owner: bool = False,
) -> Optional[Dict]:
    """Scrape a profile and store it in Supabase (with dedup).

    Checks linkedin_profiles table first. If already exists, returns cached.
    Otherwise scrapes via Apify, generates summary, and stores.

    Args:
        user_id: Supabase user ID.
        linkedin_url: LinkedIn profile URL.
        is_owner: Whether this is the user's own profile.

    Returns:
        The linkedin_profiles row dict, or None on failure.
    """
    from execution.crm_db import get_profile_by_url, upsert_profile
    from execution.profile_summarizer import summarize_profile

    url = normalize_url(linkedin_url)
    if not url:
        return None

    # Dedup check — only skip scrape if profile has BOTH raw data AND summary
    existing = get_profile_by_url(user_id, url)
    raw_data = existing.get("raw_json") if existing else None
    has_rich_data = raw_data and isinstance(raw_data, dict) and len(raw_data) > 2
    if existing and existing.get("summary") and has_rich_data:
        print(f"[Apify] Profile already exists with data: {url[:50]}")
        return existing

    # Scrape
    raw = scrape_single_profile(url)
    if not raw:
        # Store a minimal profile from URL alone
        return upsert_profile(
            user_id=user_id,
            linkedin_url=url,
            is_owner=is_owner,
        )

    # Generate summary
    summary = summarize_profile(raw)

    # Store
    return upsert_profile(
        user_id=user_id,
        linkedin_url=url,
        raw_json=raw,
        summary=summary,
        is_owner=is_owner,
    )


def scrape_and_store_from_connection(
    user_id: str,
    connection: Dict,
) -> Optional[Dict]:
    """Create/update a profile from Connections.csv data (no Apify call).

    If the connection has a LinkedIn URL and we haven't scraped it,
    store a minimal profile. If already exists, return it.

    Args:
        user_id: Supabase user ID.
        connection: Dict with first_name, last_name, company, position, linkedin_url.

    Returns:
        The linkedin_profiles row dict, or None.
    """
    from execution.crm_db import get_profile_by_url, upsert_profile

    url = normalize_url(connection.get("linkedin_url", ""))

    # If no URL, we can't create a dedup-safe profile
    if not url:
        return None

    # Check if already exists
    existing = get_profile_by_url(user_id, url)
    if existing:
        return existing

    # Create minimal profile from connection data
    return upsert_profile(
        user_id=user_id,
        linkedin_url=url,
        first_name=connection.get("first_name", ""),
        last_name=connection.get("last_name", ""),
        title=connection.get("position", ""),
        company=connection.get("company", ""),
    )
