"""
lead_scraper.py
---------------
Phase 3 — Lead Intelligence Scraper

For each post URL in .tmp/surveillance_data.json:
  1. Calls Apify's linkedin-post-comments-scraper actor (max 50 comments/post)
  2. Decodes the URN timestamp from the post URL to get the exact posting date
  3. Scores each commenter on:
     - Job title keywords  (CEO, Founder, VP, Director, Head of, Owner, CMO, CTO, COO)
     - Comment length       (>100 chars = engaged)
     - Reaction type weight
  4. Assigns lead tier: A (top decision-maker), B (senior/engaged), C (other)
  5. Saves deduplicated lead list to .tmp/leads_data.json
"""

import os
import json
import sys
import re
import argparse
from datetime import datetime, timezone
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────
# URN Timestamp Decoder
# ─────────────────────────────────────────────────────────────

def decode_urn_timestamp(post_url: str) -> str | None:
    """
    Extract the numeric activity ID from a LinkedIn post URL and decode the
    approximate posting timestamp embedded in its leading 41 bits.

    Formats supported:
      https://linkedin.com/feed/update/urn:li:activity:7217...
      https://linkedin.com/posts/.../activity-7217...-xxxx/
    """
    urn_match = re.search(r'activity[:\-](\d{18,20})', post_url or "")
    if not urn_match:
        return None
    try:
        activity_id = int(urn_match.group(1))
        # LinkedIn IDs encode milliseconds since epoch in the top 41 bits
        ms = activity_id >> 22
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Lead Scoring
# ─────────────────────────────────────────────────────────────

TITLE_A_KEYWORDS = [
    "ceo", "chief executive", "founder", "co-founder", "owner",
    "managing director", "president",
]
TITLE_B_KEYWORDS = [
    "cmo", "cto", "coo", "cfo", "vp", "vice president",
    "director", "head of", "general manager", "partner",
]

def score_lead(commenter: dict) -> dict:
    """
    Returns enriched commenter dict with `score` (0-100) and `tier` (A/B/C).
    """
    title_raw = (commenter.get("authorHeadline") or commenter.get("authorTitle") or commenter.get("headline") or commenter.get("jobTitle") or "").lower()
    
    # Reactors usually don't have text, but we extract reactionType.
    reaction_type = commenter.get("reactionType") or commenter.get("type") or "Liked"
    comment_text = commenter.get("text") or commenter.get("commentText") or ""
    comment_len = len(comment_text.strip())

    score = 0

    # Job title scoring (50 pts max)
    if any(k in title_raw for k in TITLE_A_KEYWORDS):
        score += 50
    elif any(k in title_raw for k in TITLE_B_KEYWORDS):
        score += 30

    # Comment length (30 pts max)
    if comment_len >= 200:
        score += 30
    elif comment_len >= 100:
        score += 20
    elif comment_len >= 40:
        score += 10

    # Reaction weight (20 pts max)
    # Datadoping provides specific reactionTypes, we can score them (e.g. insightful > like)
    rt_up = reaction_type.upper()
    if rt_up in ["INSIGHTFUL", "PRAISE", "EMPATHY"]:
        score += 20
    elif rt_up in ["LIKE", "APPRECIATION", "INTEREST", "ENTERTAINMENT"]:
        score += 10
    else: 
        score += 10

    if score >= 50:
        tier = "A"
    elif score >= 20:
        tier = "B"
    else:
        tier = "C"
        
    excerpt = comment_text[:200].strip() if comment_text else f"Reaction: {reaction_type.title()}"

    return {
        **commenter,
        "score": score,
        "tier": tier,
        "comment_excerpt": excerpt,
    }


# ─────────────────────────────────────────────────────────────
# Apify API Keys
# ─────────────────────────────────────────────────────────────

def get_apify_keys():
    keys = []
    for i in range(1, 6):
        suffix = f"_{i}" if i > 1 else ""
        key = os.getenv(f"APIFY_API_KEY{suffix}")
        if key:
            keys.append(key)
    return keys


# ─────────────────────────────────────────────────────────────
# Core Scraper
# ─────────────────────────────────────────────────────────────

REACTIONS_ACTOR = "datadoping/linkedin-post-reactions-scraper-no-cookie"
COMMENTS_ACTOR = "apimaestro/linkedin-post-comments-replies-engagements-scraper-no-cookies"

def scrape_reactions_for_post(post_url: str, api_key: str, max_reactions: int = 100) -> list:
    """Calls the Apify reactions actor for a single post URL."""
    client = ApifyClient(api_key)
    run_input = {
        "post_urls": [post_url],
        "max_reactions_per_post": max_reactions,
    }
    print(f"    >>> Scraping reactions for: {post_url[:80]}...")

    try:
        run = client.actor(REACTIONS_ACTOR).call(run_input=run_input, timeout_secs=120)
        if run["status"] == "SUCCEEDED":
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            print(f"    >>> Got {len(items)} reactions")
            return items
        else:
            print(f"    >>> Apify run status: {run['status']}")
            return []
    except Exception as e:
        print(f"    >>> Error scraping reactions: {e}")
        return []


def scrape_comments_for_post(post_url: str, api_key: str, max_comments: int = 50) -> list:
    """Calls the Apify comments actor for a single post URL."""
    import re
    client = ApifyClient(api_key)
    
    post_id_match = re.search(r'activity-(\d+)', post_url)
    if not post_id_match:
        post_id_match = re.search(r'(\d{19})', post_url)
    post_id = post_id_match.group(1) if post_id_match else None

    run_input = {
        "postIds": [post_id] if post_id else [post_url],
        "limit": max_comments,
    }
    
    print(f"    >>> Scraping comments for: {post_url[:80]}...")

    try:
        run = client.actor(COMMENTS_ACTOR).call(run_input=run_input, timeout_secs=120)
        if run["status"] == "SUCCEEDED":
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            print(f"    >>> Got {len(items)} comments")
            return items
        else:
            print(f"    >>> Comments run status: {run['status']}")
            return []
    except Exception as e:
        print(f"    >>> Error scraping comments: {e}")
        return []


def run_lead_scan(post_urls: list = None, uid: str = "default") -> dict:
    """
    Main entry point. Accepts explicit post_urls list or reads from surveillance data.
    Returns the lead results dict and saves to .tmp/leads_data_{uid}.json.
    """
    # ── 1. Get post URLs ──────────────────────────────────────
    if not post_urls:
        surv_path = ".tmp/surveillance_data.json"
        if not os.path.exists(surv_path):
            print("Error: No surveillance data found. Run a surveillance refresh first.")
            return {"error": "No surveillance data found", "leads": []}

        with open(surv_path, "r", encoding="utf-8") as f:
            surv_data = json.load(f)

        posts = surv_data.get("posts", [])
        if not posts:
            return {"error": "No posts in surveillance data", "leads": []}

        # Prefer top posts by engagement (A-tier posts)
        top_posts = sorted(posts, key=lambda p: p.get("engagement_score", 0), reverse=True)[:5]
        post_urls = [p["url"] for p in top_posts if p.get("url")]

    if not post_urls:
        return {"error": "No valid post URLs found", "leads": []}

    print(f"\n>>> Lead Scan: scanning {len(post_urls)} post(s) for reactions + comments...")

    # ── 2. Iterate Apify keys ─────────────────────────────────
    keys = get_apify_keys()
    all_leads = []
    seen_profiles = set()

    for post_url in post_urls:
        post_date = decode_urn_timestamp(post_url)

        # --- Scrape Reactions (datadoping) ---
        reactions = []
        for api_key in keys:
            reactions = scrape_reactions_for_post(post_url, api_key)
            if reactions:
                break

        # --- Scrape Comments (curious_coder) ---
        comments = []
        for api_key in keys:
            comments = scrape_comments_for_post(post_url, api_key)
            if comments is not None:
                break

        # --- Base structure definition to normalize ---
        def get_profile_key(url, user_name):
            return url.lower().strip("/") or user_name.lower()

        merged_items = {}

        # 1) Collect Reactions
        for r in reactions:
            reactor_obj = r.get("reactor", {})
            p_url = r.get("reactor_profile_url") or reactor_obj.get("profile_url") or ""
            p_name = r.get("reactor_name") or reactor_obj.get("name") or "Unknown"
            
            d_key = get_profile_key(p_url, p_name)
            if not d_key:
                continue

            merged_items[d_key] = {
                "_type": "reaction",
                "profile_url": p_url,
                "name": p_name,
                "headline": reactor_obj.get("headline", ""),
                "profile_picture": (
                    r.get("reactor_profile_picture")
                    or reactor_obj.get("profile_pictures", {}).get("small")
                    or ""
                ),
                "reactionType": r.get("reaction_type", "LIKE"),
                "text": "",
            }

        # 2) Collect Comments (Merge if exists)
        for c in comments:
            author_obj = c.get("author", {})
            p_url = author_obj.get("profile_url") or c.get("authorProfileUrl") or c.get("profileUrl") or c.get("authorUrl") or ""
            p_name = author_obj.get("name") or c.get("authorName") or c.get("fullName") or "Unknown"

            d_key = get_profile_key(p_url, p_name)
            if not d_key:
                continue

            comment_text = c.get("text") or c.get("commentText") or c.get("comment") or ""
            headline = author_obj.get("headline") or c.get("authorHeadline") or c.get("headline") or c.get("jobTitle") or ""
            pic_url = author_obj.get("profile_picture") or c.get("authorProfilePicture") or c.get("authorAvatar") or c.get("pictureUrl") or ""

            if d_key in merged_items:
                # User already reacted: keep reactionType, but upgrade _type and add text
                merged_items[d_key]["_type"] = "reaction+comment"
                merged_items[d_key]["text"] = comment_text
                # Also if for some reason the picture/headline is missing, we could update it
                if not merged_items[d_key]["headline"]:
                    merged_items[d_key]["headline"] = headline
            else:
                merged_items[d_key] = {
                    "_type": "comment",
                    "profile_url": p_url,
                    "name": p_name,
                    "headline": headline,
                    "profile_picture": pic_url,
                    "reactionType": "COMMENT",
                    "text": comment_text,
                }

        if not merged_items:
            print(f"    >>> No reactions or comments found for {post_url[:60]}")
            continue

        # --- Score and build final list ---
        for dedup_key, item in merged_items.items():
            if dedup_key in seen_profiles:
                continue
            seen_profiles.add(dedup_key)

            mock = {
                "authorHeadline": item["headline"],
                "reactionType": item["reactionType"],
                "text": item["text"],
            }
            lead = score_lead(mock)
            lead["source_post_url"] = post_url
            lead["source_post_date"] = post_date
            lead["name"] = item["name"]
            lead["headline"] = item["headline"]
            lead["profile_url"] = item["profile_url"]
            lead["profile_picture"] = item["profile_picture"]
            lead["interaction_type"] = item["_type"]  # 'reaction', 'comment', or 'reaction+comment'

            all_leads.append(lead)



    # ── 3. Sort and tier ──────────────────────────────────────
    all_leads.sort(key=lambda x: x["score"], reverse=True)

    summary = {
        "status": "completed",
        "total_leads": len(all_leads),
        "tier_a": sum(1 for l in all_leads if l["tier"] == "A"),
        "tier_b": sum(1 for l in all_leads if l["tier"] == "B"),
        "tier_c": sum(1 for l in all_leads if l["tier"] == "C"),
        "scanned_posts": len(post_urls),
        "scanned_urls": post_urls,
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    result = {"status": "completed", "summary": summary, "leads": all_leads}

    os.makedirs(".tmp", exist_ok=True)
    out_file = f".tmp/leads_data_{uid}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n>>> Lead Scan complete: {summary['total_leads']} leads "
          f"({summary['tier_a']} A / {summary['tier_b']} B / {summary['tier_c']} C)")

    return result


# ─────────────────────────────────────────────────────────────
# CLI Entry
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lead Intelligence Scraper")
    parser.add_argument("--urls", help="Comma-separated post URLs to scan (optional; defaults to top surveillance posts)")
    args = parser.parse_args()

    urls = [u.strip() for u in args.urls.split(",")] if args.urls else None
    result = run_lead_scan(post_urls=urls)
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)
    print(json.dumps(result["summary"], indent=2))
