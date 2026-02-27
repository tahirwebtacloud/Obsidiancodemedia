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

def run_youtube_research(urls):
    """
    Scrapes YouTube video metadata, stats, and transcripts using Apify.
    """
    if not APIFY_API_KEY:
        print("Error: APIFY_API_KEY not found.")
        return []

    client = ApifyClient(APIFY_API_KEY)
    
    # streamers/youtube-scraper schema
    run_input = {
        "startUrls": [{"url": u} for u in urls],
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
            # Skip if it's not a video (sometimes actors return channel info etc)
            if item.get("type") != "video":
                continue

            # Extract transcript from subtitles array
            transcript = ""
            subtitles = item.get("subtitles") or []
            if isinstance(subtitles, list) and len(subtitles) > 0:
                 # Extract text from 'srt' field
                 transcript = " ".join([s.get("srt", "") for s in subtitles if isinstance(s, dict)])
            
            description = item.get("text") or ""
            links = re.findall(r'(https?://[^\s]+)', description)

            # Key mappings identified from raw debug
            results.append({
                "title": item.get("title") or "YouTube Video",
                "url": item.get("url"),
                "thumbnail": item.get("thumbnailUrl"),
                "viewCount": item.get("viewCount") or 0,
                "likes": item.get("likes") or 0,
                "commentsCount": item.get("commentsCount") or 0,
                "subscribers": item.get("numberOfSubscribers") or 0,
                "description": description,
                "links": list(set(links)),
                "transcript": transcript,
                "duration": item.get("duration") or "N/A",
                "channelName": item.get("channelName") or "Unknown"
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
