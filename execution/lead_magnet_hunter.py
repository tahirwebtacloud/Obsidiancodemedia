"""
lead_magnet_hunter.py
---------------------
Dedicated Lead Magnet Hunter — runs on gemini-2.5-pro (separate from main caption LLM).

Flow:
  1. LLM analyzes the topic + research context to generate targeted search queries
  2. Tavily searches the web for relevant resources (tools, repos, guides)
  3. Each URL is verified with a HEAD request (must return HTTP 200)
  4. Dead links are filtered out; if ALL are dead, retry with a different query
  5. Returns verified lead magnets with name, URL, and description

Called by generate_text_post.py and generate_carousel.py BEFORE the main caption LLM.
"""

import os
import json
import requests
import time
from typing import List, Dict, Optional
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path)

# Use a lighter/cheaper model for lead magnet hunting
_HUNTER_MODEL = os.getenv("GEMINI_LEAD_MAGNET_MODEL", "gemini-2.5-pro-preview-05-06")


def _verify_url(url: str, timeout: int = 8) -> bool:
    """Check if a URL is reachable (HTTP 200-399). Uses HEAD with GET fallback."""
    if not url or not url.startswith("http"):
        return False
    try:
        # Try HEAD first (faster, less bandwidth)
        resp = requests.head(url, timeout=timeout, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 (compatible; LinkChecker/1.0)"})
        if resp.status_code < 400:
            return True
        # Some servers block HEAD, fallback to GET
        resp = requests.get(url, timeout=timeout, allow_redirects=True, stream=True,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; LinkChecker/1.0)"})
        return resp.status_code < 400
    except Exception:
        return False


def _tavily_search(query: str, max_results: int = 5) -> List[Dict]:
    """Search web via Tavily API. Returns list of {title, url, content}."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("[LeadMagnet] WARNING: TAVILY_API_KEY not found — skipping web search")
        return []

    try:
        print(f"[LeadMagnet] Tavily search: {query}")
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": False,
                "include_raw_content": False,
                "max_results": max_results,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            return [{"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")} for r in results]
        else:
            print(f"[LeadMagnet] Tavily error: {resp.status_code} {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"[LeadMagnet] Tavily exception: {e}")
        return []


def _generate_search_queries(topic: str, research_context: str = "", attempt: int = 0) -> List[str]:
    """Use gemini-2.5-pro to generate targeted search queries for lead magnets."""
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        # Fallback to simple query construction
        return [f"best free tools resources for {topic} 2025", f"{topic} github repo guide tutorial"]

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        retry_note = ""
        if attempt > 0:
            retry_note = (
                f"\n\nIMPORTANT: This is retry attempt #{attempt + 1}. "
                "Previous search queries returned broken/dead links. "
                "Generate COMPLETELY DIFFERENT queries targeting different resources, "
                "newer tools, or alternative platforms. Avoid the same search terms."
            )

        prompt = f"""You are a lead magnet research assistant. Your job is to generate 2-3 targeted web search queries that will find the BEST free resources, tools, GitHub repos, guides, or templates related to this topic.

Topic: {topic}

Research Context (what the post is about):
{research_context[:2000] if research_context else "No additional context."}
{retry_note}

RULES:
- Queries should find SPECIFIC, ACTIONABLE resources (not generic articles)
- Prioritize: GitHub repos, free tools, interactive demos, cheat sheets, templates
- Include the current year (2025/2026) to find recent resources
- Make queries specific to the topic, not generic

Return ONLY a JSON array of 2-3 search query strings. No explanation.
Example: ["best AI code review tools github 2025", "free AI pair programming extensions VS Code"]"""

        config = types.GenerateContentConfig(
            temperature=0.5,
            response_mime_type="application/json",
        )

        response = client.models.generate_content(
            model=_HUNTER_MODEL,
            contents=prompt,
            config=config,
        )

        text = response.text.strip()
        # Clean markdown fences if present
        import re
        text = re.sub(r'^```[a-zA-Z]*\s*\n', '', text)
        text = re.sub(r'\n\s*```$', '', text)
        queries = json.loads(text.strip())

        if isinstance(queries, list) and len(queries) > 0:
            print(f"[LeadMagnet] LLM generated {len(queries)} search queries")
            return queries[:3]

    except Exception as e:
        print(f"[LeadMagnet] Query generation error: {e}")

    # Fallback queries
    return [f"best free tools for {topic} 2025", f"{topic} github repository guide"]


def hunt_lead_magnets(topic: str, research_context: str = "", max_retries: int = 2) -> List[Dict]:
    """
    Main entry point — find and verify lead magnets for a topic.

    Returns list of verified lead magnets:
    [{"name": "...", "url": "...", "description": "..."}, ...]

    Empty list if nothing found or all links are dead after retries.
    """
    print(f"\n{'='*50}")
    print(f"LEAD MAGNET HUNTER — Topic: {topic}")
    print(f"{'='*50}")

    all_verified = []

    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"\n[LeadMagnet] Retry #{attempt} — previous results had dead links")

        # Step 1: Generate search queries
        queries = _generate_search_queries(topic, research_context, attempt=attempt)

        # Step 2: Search via Tavily
        all_results = []
        for q in queries:
            results = _tavily_search(q)
            all_results.extend(results)
            time.sleep(0.3)  # Brief delay between searches

        if not all_results:
            print(f"[LeadMagnet] No search results found (attempt {attempt + 1})")
            continue

        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for r in all_results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                unique_results.append(r)

        print(f"[LeadMagnet] Found {len(unique_results)} unique results — verifying URLs...")

        # Step 3: Verify each URL
        verified = []
        for r in unique_results:
            url = r["url"]
            is_alive = _verify_url(url)
            status = "✓ LIVE" if is_alive else "✗ DEAD"
            print(f"  {status}: {url[:80]}")

            if is_alive:
                verified.append({
                    "name": r["title"],
                    "url": r["url"],
                    "description": r["content"][:200] if r["content"] else r["title"],
                })

        if verified:
            all_verified = verified[:3]  # Cap at 3 lead magnets
            print(f"\n[LeadMagnet] ✓ {len(all_verified)} verified lead magnets found")
            break
        else:
            print(f"[LeadMagnet] All {len(unique_results)} URLs are dead — will retry with different queries")

    if not all_verified:
        print("[LeadMagnet] No verified lead magnets found after all attempts")

    # Track cost
    try:
        from cost_tracker import CostTracker
        tracker = CostTracker()
        tracker.add_gemini_cost("Lead Magnet Hunter", 500, 200, model=_HUNTER_MODEL)
    except Exception:
        pass

    return all_verified


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--context", default="")
    args = parser.parse_args()

    results = hunt_lead_magnets(args.topic, args.context)
    print(json.dumps(results, indent=2))
