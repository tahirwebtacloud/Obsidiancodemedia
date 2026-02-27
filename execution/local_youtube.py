import os
import json
import argparse
import re
import requests
import yt_dlp

def run_local_youtube(urls):
    results = []
    
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        'no_warnings': True,
        'extract_flat': False # Need full details
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for url in urls:
            try:
                print(f">>> Processing {url} with yt-dlp...")
                info = ydl.extract_info(url, download=False)
                
                # Basic Metadata
                title = info.get('title', 'YouTube Video')
                desc = info.get('description', '')
                view_count = info.get('view_count', 0)
                like_count = info.get('like_count', 0)
                comment_count = info.get('comment_count', 0)
                sub_count = info.get('channel_follower_count', 0) # yt-dlp field for subs
                channel_name = info.get('uploader', 'Unknown')
                thumbnail = info.get('thumbnail', '')
                duration = info.get('duration_string', 'N/A')

                # Transcript Logic
                transcript = "No transcript available."
                
                # Check for manual or automatic captions
                captions = info.get('subtitles') or info.get('automatic_captions') or {}
                
                # Find English track
                en_track = None
                for lang in captions:
                    if lang.startswith('en'):
                        # Prefer vtt or json3
                        formats = captions[lang]
                        # Prefer vtt
                        vtt = next((f for f in formats if f['ext'] == 'vtt'), None)
                        if vtt:
                            en_track = vtt['url']
                            break
                        # Fallback to any url
                        if formats:
                            en_track = formats[0]['url']
                            break
                
                if en_track:
                    try:
                        # Download VTT/JSON3 content
                        res = requests.get(en_track)
                        if res.ok:
                            content = res.text
                            
                            # Check if this is an M3U8 playlist (contains VTT URL)
                            if content.startswith('#EXTM3U') or 'fmt=vtt' in content:
                                # Extract the actual VTT URL from M3U8
                                vtt_match = re.search(r'(https://[^\s]+fmt=vtt[^\s]*)', content)
                                if vtt_match:
                                    vtt_url = vtt_match.group(1)
                                    vtt_res = requests.get(vtt_url)
                                    if vtt_res.ok:
                                        content = vtt_res.text
                            
                            # Simple VTT cleaning regex
                            # Remove header
                            content = re.sub(r'WEBVTT.*', '', content)
                            # Remove timestamps
                            content = re.sub(r'(?m)^\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}.*', '', content)
                            content = re.sub(r'(?m)^\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}\.\d{3}.*', '', content)
                            # Remove tags
                            content = re.sub(r'<[^>]+>', '', content)
                            # Remove align/position parameters
                            content = re.sub(r'align:.*', '', content)
                            # Remove extra newlines
                            lines = [line.strip() for line in content.split('\n') if line.strip()]
                            # Remove duplicates (common in VTT)
                            unique_lines = []
                            last_line = ""
                            for line in lines:
                                if line != last_line:
                                    unique_lines.append(line)
                                    last_line = line
                            
                            transcript = " ".join(unique_lines)
                    except Exception as e:
                        print(f"Transcript fetch error: {e}")

                # Links from description
                links = re.findall(r'(https?://[^\s]+)', desc)

                results.append({
                    "title": title,
                    "url": url,
                    "thumbnail": thumbnail,
                    "description": desc,
                    "links": list(set(links)),
                    "transcript": transcript,
                    "viewCount": str(view_count),
                    "likes": str(like_count) if like_count else "N/A",
                    "commentsCount": str(comment_count) if comment_count else "N/A",
                    "subscribers": str(sub_count) if sub_count else "N/A",
                    "duration": duration,
                    "channelName": channel_name
                })
                
            except Exception as e:
                print(f"Error processing {url}: {e}")
                # Fallback to basic if yt-dlp fails heavily?
                results.append({
                    "title": "Error fetching video",
                    "url": url,
                    "description": str(e),
                    "transcript": "",
                    "viewCount": "0", 
                    "likes": "0", 
                    "commentsCount": "0", 
                    "subscribers": "0", 
                    "channelName": "Error"
                })

    # Save output
    os.makedirs(".tmp", exist_ok=True)
    with open(".tmp/youtube_research.json", "w") as f:
        json.dump(results, f, indent=4)
        
    # Print JSON to stdout for server.py capture (just in case)
    print(json.dumps(results))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls", required=True)
    args = parser.parse_args()
    urls = [u.strip() for u in args.urls.split(",") if u.strip()]
    run_local_youtube(urls)
