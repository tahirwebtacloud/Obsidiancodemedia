"""
LinkedIn Profile Scraper (Phase 1C)
Uses Apify's linkedin-profile-scraper actor to fetch current title + company
for high-value CRM contacts still missing title data after connection lookup
and LLM inference.

Eligibility for enrichment:
  - title_source == "unknown"
  - behavioral_tag in ('warm_lead', 'client', 'referrer')
  - linkedin_url is populated
"""

import os
from typing import Dict, List, Optional
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

PROFILE_SCRAPER_ACTOR = "dev_fusion/linkedin-profile-scraper"
HIGH_VALUE_TAGS = {"warm_lead", "client", "referrer"}


def _get_apify_key() -> Optional[str]:
    """Return first available Apify API key from env vars."""
    for i in range(1, 6):
        suffix = f"_{i}" if i > 1 else ""
        key = os.getenv(f"APIFY_API_KEY{suffix}")
        if key:
            return key
    return None


def _normalize_url(url: str) -> str:
    """Normalize a LinkedIn profile URL for consistent key matching."""
    return (url or "").strip().rstrip("/").lower()


def _extract_current_company(item: dict) -> str:
    """Extract current company from nested experience/positions fields."""
    try:
        for field in ("experiences", "positions", "jobs"):
            entries = item.get(field) or []
            if isinstance(entries, list) and entries:
                first = entries[0]
                if isinstance(first, dict):
                    name = (
                        first.get("companyName")
                        or first.get("company")
                        or first.get("organization")
                        or ""
                    )
                    if name:
                        return str(name).strip()
    except Exception:
        pass
    return ""


def scrape_linkedin_profiles(
    profile_urls: List[str],
    api_key: Optional[str] = None,
) -> Dict[str, Dict]:
    """
    Scrape LinkedIn profiles for title + company data via Apify.

    Args:
        profile_urls: LinkedIn profile URLs to scrape
        api_key: Apify API key (falls back to env var)

    Returns:
        Dict mapping normalized_url → {title, company, full_name}
        Empty dict on failure or no API key.
    """
    api_key = api_key or _get_apify_key()
    if not api_key:
        print("[ProfileScraper] No Apify API key available — skipping enrichment")
        return {}

    urls = list({_normalize_url(u) for u in profile_urls if u and u.strip()})
    if not urls:
        return {}

    print(f"[ProfileScraper] Scraping {len(urls)} LinkedIn profiles via Apify...")

    try:
        client = ApifyClient(api_key)
        run = client.actor(PROFILE_SCRAPER_ACTOR).call(
            run_input={"profileUrls": urls},
            timeout_secs=180,
        )

        if run.get("status") != "SUCCEEDED":
            print(f"[ProfileScraper] Actor status: {run.get('status')} — aborting")
            return {}

        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        print(f"[ProfileScraper] Received {len(items)} profile records")

        results: Dict[str, Dict] = {}
        for item in items:
            raw_url = (
                item.get("linkedInUrl")
                or item.get("profileUrl")
                or item.get("url")
                or ""
            )
            url_key = _normalize_url(raw_url)
            if not url_key:
                continue

            title = str(item.get("headline") or item.get("jobTitle") or "").strip()
            company = str(
                item.get("currentCompany")
                or item.get("company")
                or _extract_current_company(item)
                or ""
            ).strip()
            full_name = str(item.get("fullName") or item.get("name") or "").strip()

            results[url_key] = {
                "title": title,
                "company": company,
                "full_name": full_name,
            }

        return results

    except Exception as e:
        print(f"[ProfileScraper] Error: {e}")
        return {}


def enrich_contacts_with_profiles(
    contacts: List[Dict],
    api_key: Optional[str] = None,
) -> tuple:
    """
    Enrich eligible CRM contacts using Apify profile data.

    Eligibility: title_source == "unknown", high-value tag, linkedin_url set.

    Args:
        contacts: List of CRM contact dicts (mutated in place)
        api_key: Apify API key

    Returns:
        Tuple of (updated_contacts, enriched_count)
    """
    eligible = [
        c for c in contacts
        if (
            c.get("behavioral_tag") in HIGH_VALUE_TAGS
            and c.get("linkedin_url", "").strip()
            and (c.get("title_source") or "unknown") == "unknown"
        )
    ]

    if not eligible:
        print("[ProfileScraper] No eligible contacts for profile enrichment")
        return contacts, 0

    print(f"[ProfileScraper] {len(eligible)} contacts eligible for Apify enrichment")
    urls = [c["linkedin_url"].strip() for c in eligible]
    profile_data = scrape_linkedin_profiles(urls, api_key=api_key)

    if not profile_data:
        return contacts, 0

    enriched_count = 0
    for contact in eligible:
        url_key = _normalize_url(contact.get("linkedin_url", ""))
        data = profile_data.get(url_key)
        if not data:
            continue

        meta = contact.get("metadata", {}) if isinstance(contact.get("metadata"), dict) else {}
        changed = False

        if data.get("title") and not contact.get("position"):
            contact["position"] = data["title"]
            meta["title_source"] = "apify_profile"
            meta["title_confidence"] = "high"
            contact["title_source"] = "apify_profile"
            contact["title_confidence"] = "high"
            changed = True

        if data.get("company") and not contact.get("company"):
            contact["company"] = data["company"]
            changed = True

        if changed:
            contact["metadata"] = meta
            enriched_count += 1

    print(f"[ProfileScraper] Enriched {enriched_count}/{len(eligible)} contacts")
    return contacts, enriched_count


if __name__ == "__main__":
    import json
    test_urls = ["https://www.linkedin.com/in/keithmortier/"]
    result = scrape_linkedin_profiles(test_urls)
    print(json.dumps(result, indent=2))
