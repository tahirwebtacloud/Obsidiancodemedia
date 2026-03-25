"""
Minimal web search module using Tavily.
Drop-in replacement for the deprecated DuckDuckGo-based Web-Search-tool.
"""

import os
from tavily import TavilyClient


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


SOCIAL_DOMAINS = [
    "linkedin.com",
    "x.com",
    "instagram.com",
    "facebook.com",
]


def search_web(query, max_results=3, deep=False):
    """Search the web via Tavily and return results.

    Automatically rotates through available API keys on failure.

    Args:
        query: Search query string.
        max_results: Number of results to return.
        deep: If True, use advanced search depth with raw content.

    Returns:
        dict with 'success' bool and 'results' list of {title, url, snippet, markdown}.
    """
    keys = _get_tavily_keys()
    if not keys:
        return {"success": False, "error": "No Tavily API keys configured", "results": []}

    search_params = {
        "query": query,
        "max_results": max_results,
        "include_domains": SOCIAL_DOMAINS,
        "search_depth": "advanced" if deep else "basic",
        "include_answer": "advanced" if deep else True,
        "time_range": "day",
        "country": "united states",
    }

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
                    "snippet": r.get("content", ""),
                    "markdown": r.get("content", ""),
                }
                results.append(entry)

            return {"success": True, "results": results}

        except Exception as e:
            last_error = str(e)
            is_auth_error = any(kw in last_error.lower() for kw in ("auth", "credit", "quota", "401", "403", "limit"))
            if is_auth_error and i < len(keys) - 1:
                continue
            elif i < len(keys) - 1:
                continue

    return {"success": False, "error": last_error or "All keys failed", "results": []}
