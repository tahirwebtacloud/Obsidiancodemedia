"""
Minimal web search module using DuckDuckGo.
Drop-in replacement for the missing Web-Search-tool dependency.
"""

import requests
from duckduckgo_search import DDGS


def search_web(query, max_results=3, deep=False):
    """Search the web and optionally scrape page content.
    
    Args:
        query: Search query string.
        max_results: Number of results to return.
        deep: If True, attempt to fetch and return page markdown content.
    
    Returns:
        dict with 'success' bool and 'results' list of {title, url, snippet, markdown}.
    """
    try:
        ddgs = DDGS()
        raw_results = list(ddgs.text(query, max_results=max_results))

        results = []
        for r in raw_results:
            entry = {
                "title": r.get("title", ""),
                "url": r.get("href", r.get("link", "")),
                "snippet": r.get("body", r.get("snippet", "")),
                "markdown": ""
            }

            if deep and entry["url"]:
                try:
                    resp = requests.get(entry["url"], timeout=8, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    })
                    if resp.ok:
                        # Simple text extraction — strip HTML tags roughly
                        text = resp.text
                        # Remove script/style blocks
                        import re
                        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
                        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                        text = re.sub(r'<[^>]+>', ' ', text)
                        text = re.sub(r'\s+', ' ', text).strip()
                        entry["markdown"] = text[:5000]
                except Exception:
                    pass

            results.append(entry)

        return {"success": True, "results": results}

    except Exception as e:
        return {"success": False, "error": str(e), "results": []}
