import os
import sys
import json
import argparse
import requests
import re
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

def search_with_jina(topic, regions=None):
    """
    Drop-in replacement for Jina AI web search that uses local DDG search.
    (Keeps the function name 'search_with_jina' to avoid breaking orchestrator.py)
    """
    print(f"Searching for topic: {topic}")
    
    variations = [
        f"{topic} latest news, trends and statistics",
        f"{topic} key insights, challenges and opportunities"
    ]

    aggregated_content = f"# Web Search Results for '{topic}'\n\n"
    
    for query in variations:
        print(f">>> [WEB SEARCH] Searching: {query}...")
        try:
            # PERFORMANCE: Use shallow mode (snippets only) to avoid 10-30s page scraping.
            # DDG snippets provide sufficient context for the generation LLM.
            search_results = search_web(query, max_results=3, deep=False)
            if search_results and search_results.get("success"):
                aggregated_content += f"## Query: {query}\n\n"
                for i, result in enumerate(search_results.get("results", [])):
                    title = result.get("title", "No Title")
                    url = result.get("url", "No URL")
                    markdown = result.get("markdown", "")
                    snippet = result.get("snippet", "")
                    
                    aggregated_content += f"### {i+1}. {title}\n"
                    aggregated_content += f"URL: {url}\n\n"
                    if markdown:
                        # Limit markdown size per result to avoid huge contexts
                        aggregated_content += f"{markdown[:3000]}\n\n"
                    else:
                        aggregated_content += f"{snippet}\n\n"
                aggregated_content += "---\n\n"
            else:
                print(f"Error during search for '{query}': {search_results.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"Error during search for '{query}': {str(e)}")

    # Save aggregated results
    output_path = ".tmp/source_content.md"
    os.makedirs(".tmp", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(aggregated_content)
        
    print(f"Search results saved to {output_path}")
    
    return aggregated_content

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search web content using integrated DuckDuckGo search.")
    parser.add_argument("--topic", required=True, help="Topic to search for.")
    
    args = parser.parse_args()
    search_with_jina(args.topic)
