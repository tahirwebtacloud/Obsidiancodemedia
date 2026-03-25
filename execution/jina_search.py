"""
Tavily-powered web search module with intelligent query optimization.
Features:
  - LLM-powered keyword extraction with structured output (Gemini Flash — near-zero cost)
  - Context-aware domain targeting (LLM suggests 5+ relevant domains per topic)
  - Relevance filtering via Tavily score
  - Flexible time_range with adaptive widening
  - Multi-key rotation with automatic failover
"""

import os
import json
from dotenv import load_dotenv
load_dotenv()
import argparse
from tavily import TavilyClient

# --- Tavily API Key Rotation ---
# Load up to 5 keys from environment variables. The system tries each key
# in order and automatically falls back to the next on auth/credit failures.

def _get_tavily_keys():
    """Retrieve all configured Tavily API keys from environment variables."""
    keys = []
    primary = os.getenv("TAVILY_API_KEY", "")
    if primary:
        keys.append(primary)
    for i in range(2, 6):
        k = os.getenv(f"TAVILY_API_KEY_{i}", "")
        if k:
            keys.append(k)
    return keys


# Fallback social domains when LLM extraction is unavailable
SOCIAL_DOMAINS = [
    "linkedin.com",
    "x.com",
    "instagram.com",
    "facebook.com",
    "reddit.com",
]

# Valid Tavily time_range values
VALID_TIME_RANGES = {"day", "week", "month", "year"}

# Minimum relevance score to keep a result (0-1). Anything below is noise.
MIN_RELEVANCE_SCORE = 0.3

# Time range widening order for adaptive fallback
_TIME_RANGE_WIDER = {"day": "week", "week": "month", "month": "year"}


# ─── Enhancement A: LLM-Powered Keyword Extraction (Structured Output) ──────
_KEYWORD_EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "keywords": {
            "type": "STRING",
            "description": "Search-optimized query string, 2-5 words. Focus ONLY on the core factual entities or news (e.g., 'Google Stitch tool updates'). DO NOT include the user's goal or post format (e.g., 'for my personal brand', 'how to use it for sales') in the search query, as it ruins search results."
        },
        "category": {
            "type": "STRING",
            "enum": ["tech_product", "person", "company", "social_trend", "general"],
            "description": "Topic classification for domain routing."
        },
        "entities": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Specific named entities (products, tools, people, companies) found in the topic."
        },
        "relevant_domains": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "5-8 web domains most likely to have authoritative content on this topic. Include official sites, documentation, news outlets, and community forums relevant to the topic."
        },
    },
    "required": ["keywords", "category", "entities", "relevant_domains"],
}

_KEYWORD_FALLBACK = {"keywords": "", "category": "general", "entities": [], "relevant_domains": []}


def _extract_search_keywords(topic: str) -> dict:
    """Use Gemini Flash to extract optimized search keywords from a user topic.

    Uses structured output (JSON schema) to guarantee consistent response format.
    Cost: ~$0.00001 per call (< 100 input tokens, < 80 output tokens on Flash).
    Falls back to using the raw topic string if the LLM call fails.

    Returns:
        dict with keys:
          - keywords: search-optimized query string
          - category: one of tech_product | person | company | social_trend | general
          - entities: list of named entities found in the topic
          - relevant_domains: list of 5-8 domains most relevant to the topic
    """
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY", "")
    if not api_key:
        return {**_KEYWORD_FALLBACK, "keywords": topic}

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        prompt = (
            f'Extract search keywords and identify relevant web sources for this topic.\n'
            f'Topic: "{topic}"\n\n'
            'For relevant_domains, think about:\n'
            '- Official website of the product/company/person mentioned\n'
            '- Documentation sites (docs.*, developer.*)\n'
            '- Major tech news outlets (techcrunch.com, theverge.com, arstechnica.com)\n'
            '- Community forums (reddit.com, news.ycombinator.com)\n'
            '- Social platforms where discussions happen (linkedin.com, x.com)\n'
            '- Industry-specific blogs and publications\n'
            'Always return at least 5 domains, ideally 6-8.\n\n'
            'Examples:\n'
            '- "Claude Code updates 2026" => relevant_domains: ["anthropic.com", "docs.anthropic.com", "github.com", "techcrunch.com", "news.ycombinator.com", "reddit.com", "x.com"]\n'
            '- "Tesla Q1 earnings" => relevant_domains: ["tesla.com", "ir.tesla.com", "bloomberg.com", "reuters.com", "cnbc.com", "seekingalpha.com", "linkedin.com"]\n'
            '- "LinkedIn growth hacks" => relevant_domains: ["linkedin.com", "x.com", "reddit.com", "medium.com", "hubspot.com", "buffer.com"]'
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=200,
                response_mime_type="application/json",
                response_schema=_KEYWORD_EXTRACTION_SCHEMA,
            ),
        )

        result = json.loads(response.text)

        # LinkedIn must always be present (core platform for this tool)
        domains = result.get("relevant_domains", [])
        if "linkedin.com" not in domains:
            domains.insert(0, "linkedin.com")

        # Ensure at least 5 domains
        if len(domains) < 5:
            _padding = ["reddit.com", "x.com", "medium.com", "news.ycombinator.com"]
            for d in _padding:
                if d not in domains:
                    domains.append(d)
                if len(domains) >= 5:
                    break
        result["relevant_domains"] = domains

        kw = result.get("keywords", topic)
        cat = result.get("category", "general")
        print(f'[Tavily] Keyword extraction: "{topic}" -> "{kw}" (category: {cat}, domains: {len(domains)})')
        return result

    except Exception as e:
        print(f"[Tavily] Keyword extraction fallback (using raw topic): {e}")
        return {**_KEYWORD_FALLBACK, "keywords": topic}


# ─── Enhancement C: Score-Based Relevance Filtering ──────────────────────────
def _filter_by_relevance(results: list, min_score: float = MIN_RELEVANCE_SCORE) -> list:
    """Filter out low-relevance results using Tavily's built-in score field."""
    if not results:
        return []
    # Strictly filter by relevance. Do not force keep garbage.
    filtered = [r for r in results if r.get("score", 0) >= min_score]
    return filtered


def search_web(query, max_results=6, deep=True, time_range="day", domains=None):
    """Search the web via Tavily for the latest content on a topic.

    Automatically rotates through available API keys on failure.

    Args:
        query: Search query string (ideally pre-processed keywords).
        max_results: Number of results to return (default 6).
        deep: If True, use advanced search depth and include raw content.
        time_range: Time filter — day, week, month, or year (default: day).
        domains: List of domains to restrict search to, or empty/None for open web.

    Returns:
        dict with 'success' bool, 'results' list, and 'answer' string.
    """
    keys = _get_tavily_keys()
    if not keys:
        print("[Tavily] FATAL: No TAVILY_API_KEY configured in .env")
        return {"success": False, "error": "No Tavily API keys configured", "results": [], "answer": ""}

    # Validate time_range
    if time_range not in VALID_TIME_RANGES:
        time_range = "day"

    search_params = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced" if deep else "basic",
        "include_answer": "advanced" if deep else True,
        "time_range": time_range,
        "country": "united states",
    }

    # Only restrict domains if a non-empty list is provided
    if domains:
        search_params["include_domains"] = domains

    # Only request raw markdown content on deep searches
    if deep:
        search_params["include_raw_content"] = "markdown"
        search_params["chunks_per_source"] = 2

    last_error = None
    for i, api_key in enumerate(keys):
        try:
            client = TavilyClient(api_key)
            response = client.search(**search_params)

            results = []
            for r in response.get("results", []):
                entry = {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0),
                }
                results.append(entry)

            print(f"[Tavily] Search succeeded with key #{i+1} (time_range={time_range}, domains={'restricted' if domains else 'open'})")
            return {
                "success": True,
                "answer": response.get("answer", ""),
                "results": results,
            }

        except Exception as e:
            last_error = str(e)
            is_auth_error = any(kw in last_error.lower() for kw in ("auth", "credit", "quota", "401", "403", "limit"))
            if is_auth_error and i < len(keys) - 1:
                print(f"[Tavily] Key #{i+1} failed (auth/credit). Rotating to key #{i+2}...")
                continue
            elif i < len(keys) - 1:
                print(f"[Tavily] Key #{i+1} error: {last_error}. Trying next key...")
                continue
            else:
                print(f"[Tavily] All {len(keys)} keys exhausted. Last error: {last_error}")

    return {"success": False, "error": last_error or "All keys failed", "results": [], "answer": ""}


def search_with_jina(topic, time_range="day"):
    """Search the web for authentic content on a topic.

    Keeps the function name 'search_with_jina' to avoid breaking orchestrator.py.
    Now powered by Tavily API with intelligent query optimization.

    Pipeline:
      1. Extract keywords + relevant domains via Gemini Flash (near-zero cost)
      2. Search Tavily with optimized query targeting LLM-suggested domains
      3. Filter results by relevance score
      4. Adaptive time_range widening if results are sparse
    """
    print(f"[Tavily] Searching for: {topic}")

    # --- Step 1: Extract search keywords + relevant domains ---
    extraction = _extract_search_keywords(topic)
    keywords = extraction.get("keywords", topic)
    category = extraction.get("category", "general")
    entities = extraction.get("entities", [])
    domains = extraction.get("relevant_domains", [])

    # Fallback: if LLM returned no domains, use social domains for social topics
    if not domains:
        if category == "social_trend":
            domains = list(SOCIAL_DOMAINS)
            print(f"[Tavily] Using fallback social domains (category: {category})")
        else:
            # Open web but still include LinkedIn (core platform)
            domains = ["linkedin.com"]
            print(f"[Tavily] Open web + LinkedIn (category: {category})")
    else:
        print(f"[Tavily] Targeting {len(domains)} LLM-selected domains: {', '.join(domains)}")

    # Build search queries — two variations for broader coverage (used in fallback)
    variations = [
        f"{keywords} latest insights and updates",
        f"{keywords} key trends and analysis",
    ]

    aggregated_content = f"# Web Research for '{topic}'\n\n"
    if entities:
        aggregated_content += f"**Key entities identified**: {', '.join(entities)}\n\n"
    total_chars = 0

    # --- Step 2: Primary search with optimized keywords + targeted domains ---
    primary_result = search_web(keywords, max_results=6, deep=True, time_range=time_range, domains=domains)

    # --- Step 3: Adaptive time_range widening ---
    if primary_result.get("success"):
        result_count = len(primary_result.get("results", []))
        if result_count < 2 and time_range in _TIME_RANGE_WIDER:
            wider = _TIME_RANGE_WIDER[time_range]
            print(f"[Tavily] Only {result_count} results with time_range={time_range}. Widening to {wider}...")
            primary_result = search_web(keywords, max_results=6, deep=True, time_range=wider, domains=domains)

    if primary_result.get("success"):
        # --- Step 4: Filter by relevance score ---
        raw_results = primary_result.get("results", [])
        filtered_results = _filter_by_relevance(raw_results)
        dropped = len(raw_results) - len(filtered_results)
        if dropped > 0:
            print(f"[Tavily] Relevance filter: dropped {dropped} low-score results (threshold: {MIN_RELEVANCE_SCORE})")
        if not filtered_results:
            print(f"[Tavily] All results filtered out due to low relevance. Triggering open web fallback...")
            primary_result["success"] = False


        # Prepend Tavily's advanced answer as a synthesis header
        answer = primary_result.get("answer", "")
        if answer:
            aggregated_content += f"## AI-Synthesized Overview\n{answer}\n\n---\n\n"
            total_chars += len(answer)

        # Extract content from each result
        aggregated_content += "## Source Posts & Articles\n\n"
        for i, result in enumerate(filtered_results):
            title = result.get("title", "No Title")
            url = result.get("url", "")
            content = result.get("content", "")
            score = result.get("score", 0)

            aggregated_content += f"### {i+1}. {title}\n"
            aggregated_content += f"URL: {url}\n"
            aggregated_content += f"Relevance: {score:.2f}\n\n"

            if content:
                aggregated_content += f"{content}\n\n"
                total_chars += len(content)

            aggregated_content += "---\n\n"

        print(f"[Tavily] Primary search: {len(filtered_results)} results (after relevance filtering)")
    else:
        error = primary_result.get("error", "Unknown error")
        print(f"[Tavily] Primary search failed or returned no relevant results: {error}")

        # Fallback: try individual query variations without domain restriction, and progressively wider time ranges
        fallback_time_ranges = [time_range]
        if time_range == "day": fallback_time_ranges.extend(["week", "month", "year"])
        elif time_range == "week": fallback_time_ranges.extend(["month", "year"])
        elif time_range == "month": fallback_time_ranges.extend(["year"])

        fallback_success = False
        for fallback_time in fallback_time_ranges:
            if fallback_success:
                break
            print(f"[Tavily] Fallback search attempting time_range: {fallback_time}")
            for query in variations:
                print(f"[Tavily] Fallback search: {query}")
                try:
                    result = search_web(query, max_results=3, deep=False, time_range=fallback_time, domains=None)
                    if result and result.get("success") and result.get("results"):
                        aggregated_content += f"## Query: {query}\n\n"
                        for i, r in enumerate(result.get("results", [])):
                            title = r.get("title", "No Title")
                            url = r.get("url", "")
                            content = r.get("content", "")

                            aggregated_content += f"### {i+1}. {title}\n"
                            aggregated_content += f"URL: {url}\n\n"
                            if content:
                                aggregated_content += f"{content}\n\n"
                                total_chars += len(content)
                            aggregated_content += "---\n\n"
                        fallback_success = True
                except Exception as e:
                    print(f"[Tavily] Fallback error for '{query}': {e}")

    # Save aggregated results
    output_path = ".tmp/source_content.md"
    os.makedirs(".tmp", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(aggregated_content)

    print(f"[Tavily] Results saved to {output_path}")
    print(f"[Tavily] Total content characters: {total_chars}")
    print(f"[Tavily] Total output file characters: {len(aggregated_content)}")

    return aggregated_content


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Search the web for topic research using Tavily."
    )
    parser.add_argument("--topic", required=True, help="Topic to search for.")
    parser.add_argument("--time_range", default="day", choices=["day", "week", "month", "year"],
                        help="Time range for results (default: day).")
    args = parser.parse_args()
    search_with_jina(args.topic, time_range=args.time_range)
