import os
import json
import argparse
from apify_client import ApifyClient
from dotenv import load_dotenv

# Load env from root
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path)

APIFY_API_KEY = os.getenv("APIFY_API_KEY")
ACTOR_ID = "streamers/youtube-scraper"


def _strip_srt_timestamps(srt_text: str) -> str:
    """Remove SRT timing markers and sequence numbers, keep only spoken text.
    
    Handles ALL YouTube SRT variants:
      - Standard:   00:00:01,000 --> 00:00:03,000
      - Short:      00:01,550 --> 00:05,100   (MM:SS,mmm)
      - Loose:      00:00:5,670 --> 00:00:7,510 (single-digit fields)
      - Inline:     timestamps mixed with text on same line
    
    Returns: clean spoken text with no timestamps.
    """
    import re
    if not srt_text:
        return ""
    # 1. Full HH:MM:SS,mmm --> HH:MM:SS,mmm (flexible digits)
    text = re.sub(r'\d{1,2}:\d{1,2}:\d{1,2}[.,]\d{1,3}\s*-->\s*\d{1,2}:\d{1,2}:\d{1,2}[.,]\d{1,3}', '', srt_text)
    # 2. Short MM:SS,mmm --> MM:SS,mmm
    text = re.sub(r'\d{1,2}:\d{1,2}[.,]\d{1,3}\s*-->\s*\d{1,2}:\d{1,2}[.,]\d{1,3}', '', text)
    # 3. Partial: timestamp --> (no right side) or --> timestamp (no left side)
    text = re.sub(r'\d{1,2}:\d{1,2}[.,]\d{1,3}\s*-->', '', text)
    text = re.sub(r'-->\s*\d{1,2}:\d{1,2}[.,]\d{1,3}', '', text)
    # 4. Standalone timestamps (no arrow) — HH:MM:SS,mmm or MM:SS,mmm
    text = re.sub(r'\b\d{1,2}:\d{1,2}:\d{1,2}[.,]\d{1,3}\b', '', text)
    text = re.sub(r'\b\d{1,2}:\d{1,2}[.,]\d{1,3}\b', '', text)
    # 5. Bare arrows left over
    text = re.sub(r'\s*-->\s*', ' ', text)
    # 6. Sequence numbers (standalone digits on their own line)
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
    # 7. <c> and </c> tags (common in YouTube auto-generated subtitles)
    text = re.sub(r'</?c[^>]*>', '', text)
    # 8. Other HTML-like tags
    text = re.sub(r'<[^>]+>', '', text)
    # 9. Collapse whitespace
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


def _is_shorts_url(url: str) -> bool:
    """Detect if a URL is a YouTube Shorts URL."""
    return '/shorts/' in (url or '')


def _normalize_youtube_url(url: str) -> str:
    """Normalize YouTube URLs for Apify compatibility.
    Shorts URLs may need conversion to standard watch?v= format."""
    import re
    # Extract Shorts ID and convert to watch URL for wider scraper compatibility
    shorts_match = re.search(r'/shorts/([a-zA-Z0-9_-]+)', url or '')
    if shorts_match:
        video_id = shorts_match.group(1)
        # Keep both formats — Apify's scraper handles shorts URLs directly
        return url.split('?')[0]  # Clean query params like ?feature=share
    return url


def run_youtube_research(urls):
    """
    Scrapes YouTube video metadata, stats, and transcripts using Apify.
    """
    if not APIFY_API_KEY:
        print("Error: APIFY_API_KEY not found.")
        return []

    client = ApifyClient(APIFY_API_KEY)
    
    # streamers/youtube-scraper schema
    # Track which URLs are Shorts for post-processing
    shorts_flags = {u: _is_shorts_url(u) for u in urls}
    clean_urls = [_normalize_youtube_url(u) for u in urls]

    run_input = {
        "startUrls": [{"url": u} for u in clean_urls],
        "downloadSubtitles": True,
        "subtitlesFormat": "srt",
        "maxResults": 1,
        "maxSearchResults": 1
    }

    try:
        print(f">>> Calling Apify YouTube Scraper for {len(urls)} videos...")
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        print(f">>> Scraped {len(items)} items.")
        
        from cost_tracker import CostTracker
        tracker = CostTracker()
        tracker.add_apify_yt_video_cost(len(urls), operation="YouTube Scrape Deep")

        # Debug: Dump raw items
        with open(".tmp/raw_youtube_debug.json", "w") as f:
            json.dump(items, f, indent=4)

        import re
        results = []
        for item in items:
            item_type = item.get("type", "")
            # Accept both "video" and "short" types
            if item_type not in ("video", "short"):
                # Also accept items with no type if they have a title (some Shorts)
                if not item.get("title"):
                    continue

            # Extract transcript from subtitles array and strip SRT timestamps
            transcript = ""
            subtitles = item.get("subtitles") or []
            if isinstance(subtitles, list) and len(subtitles) > 0:
                raw_srt = " ".join([s.get("srt", "") for s in subtitles if isinstance(s, dict)])
                transcript = _strip_srt_timestamps(raw_srt)
            
            # Fallback: some items have 'subtitlesText' as plain text
            if not transcript:
                transcript = item.get("subtitlesText", "")
                if transcript:
                    transcript = _strip_srt_timestamps(transcript)

            description = item.get("text") or item.get("description") or ""
            links = re.findall(r'(https?://[^\s]+)', description)

            # Thumbnail: try multiple possible keys from Apify response
            thumbnail = item.get("thumbnailUrl") or item.get("thumbnail") or ""
            if not thumbnail:
                thumbs_list = item.get("thumbnails")
                if isinstance(thumbs_list, list) and len(thumbs_list) > 0:
                    thumbnail = thumbs_list[0].get("url", "")
            # Fallback: construct from video ID (handles all YT URL formats)
            if not thumbnail:
                video_url = item.get("url", "")
                vid_match = re.search(r'(?:v=|shorts/|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', video_url)
                if vid_match:
                    thumbnail = f"https://img.youtube.com/vi/{vid_match.group(1)}/hqdefault.jpg"
            # Ultimate fallback: try extracting video ID from original user-supplied URLs
            if not thumbnail:
                for orig_url in urls:
                    vid_match = re.search(r'(?:v=|shorts/|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', orig_url)
                    if vid_match:
                        thumbnail = f"https://img.youtube.com/vi/{vid_match.group(1)}/hqdefault.jpg"
                        break

            # Detect if this is a Short — match by item URL or Apify type
            item_url = item.get("url") or ""
            is_short = _is_shorts_url(item_url) or item_type == "short"
            # Also check if the original user-supplied URL for this video was a shorts URL
            if not is_short:
                vid_id_match = re.search(r'(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]+)', item_url)
                if vid_id_match:
                    vid_id = vid_id_match.group(1)
                    is_short = any(_is_shorts_url(orig) for orig in urls if vid_id in orig)

            print(f"  [{item.get('title', 'Unknown')[:40]}] type={item_type} is_short={is_short} thumb={'YES' if thumbnail else 'NONE'} url={item_url[:60]}")

            results.append({
                "title": item.get("title") or "YouTube Video",
                "url": item_url,
                "thumbnail": thumbnail,
                "viewCount": item.get("viewCount") or 0,
                "likes": item.get("likes") or 0,
                "commentsCount": item.get("commentsCount") or 0,
                "subscribers": item.get("numberOfSubscribers") or 0,
                "description": description,
                "links": list(set(links)),
                "transcript": transcript,
                "duration": item.get("duration") or "N/A",
                "channelName": item.get("channelName") or item.get("channelTitle") or "Unknown",
                "is_short": is_short,
            })


        output_path = ".tmp/youtube_research.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=4)
        
        print(f"YouTube Research saved to {output_path}")
        return results

    except Exception as e:
        print(f"Error scraping YouTube: {e}")
        return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape YouTube via Apify.")
    parser.add_argument("--urls", required=True, help="Comma-separated YouTube URLs.")
    args = parser.parse_args()
    
    urls_list = args.urls.split(",")
    run_youtube_research(urls_list)
