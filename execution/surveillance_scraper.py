import os
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
from apify_client import ApifyClient
from dotenv import load_dotenv

# Ensure sibling modules are importable when run as subprocess
sys.path.insert(0, os.path.dirname(__file__))

from viral_research_apify import process_items, get_apify_keys

load_dotenv()

def run_surveillance(days=30, uid="default"):
    # Prefer Supabase-stored URL so UI edits are respected; fall back to .env
    profile_url = None
    try:
        from supabase_client import get_all_settings
        settings = get_all_settings(uid=uid)
        profile_url = settings.get("trackedProfileUrl")
    except Exception:
        pass

    # Final fallback: .env
    if not profile_url:
        profile_url = os.getenv("LINKEDIN_PROFILE_URL")

    if not profile_url:
        print("Error: No tracked profile URL found in settings or .env")
        return None

    keys_to_try = get_apify_keys()
    os.makedirs(".tmp", exist_ok=True)
    output_path = f".tmp/surveillance_data_{uid}.json"
    
    for api_key in keys_to_try:
        try:
            client = ApifyClient(api_key)
            TARGET_ACTOR = "supreme_coder/linkedin-post"
            
            run_input = {
                "urls": [profile_url],
                "limitPerSource": 30, # enough to cover 7 days usually
                "deepScrape": True
            }
            print(f">>> Running Surveillance Scraper on {profile_url} with key {api_key[:8]}...")
            run = client.actor(TARGET_ACTOR).call(run_input=run_input)
            
            if run['status'] == "SUCCEEDED":
                items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
                
                # Filter to only keep posts authored by the target profile
                profile_username = profile_url.rstrip('/').split('?')[-1]
                if '/' in profile_username:
                    profile_username = profile_username.split('/')[-1]
                profile_username = profile_username.lower()

                my_items = []
                for item in items:
                    auth_id = (item.get("authorProfileId") or "").lower()
                    auth_url = (item.get("authorProfileUrl") or "").lower()
                    
                    if profile_username in auth_id or profile_username in auth_url:
                        my_items.append(item)
                    else:
                        print(f"Skipping post by other author: {auth_id} / {auth_url}")
                
                # Reuse process_items from viral_research_apify
                processed_items = process_items(my_items, urls=[profile_url], post_type="all")
                
                now = datetime.now(timezone.utc)
                cutoff_date = now - timedelta(days=days)
                print(f">>> Filtering posts from the last {days} days (cutoff: {cutoff_date.strftime('%Y-%m-%d')})")
                
                recent_posts = []
                for p in processed_items:
                    posted_str = p.get("posted_at", "")
                    time_since = p.get("time_since_posted", "").lower()
                    
                    if posted_str:
                        try:
                            if posted_str.endswith('Z'):
                                posted_str = posted_str[:-1] + '+00:00'
                            posted_dt = datetime.fromisoformat(posted_str)
                            if posted_dt.tzinfo is None:
                                posted_dt = posted_dt.replace(tzinfo=timezone.utc)
                            
                            if posted_dt >= cutoff_date:
                                recent_posts.append(p)
                            else:
                                print(f"Strict: Skipping older post > 7 days: {posted_str}")
                        except Exception as e:
                            print(f"Error parsing date {posted_str}: {e}")
                            # Fallback if unparseable
                            if not time_since or any(x in time_since for x in ["mo", "yr", "2w", "3w", "4w", "month", "year"]):
                                print(f"Strict: Skipping invalid date post (time_since='{time_since}')")
                            else:
                                print(f"Strict: Allowing based on time_since='{time_since}'")
                                recent_posts.append(p)
                    elif time_since:
                        if any(x in time_since for x in ["mo", "yr", "2w", "3w", "4w", "month", "year"]):
                            print(f"Strict: Skipping post based on time_since='{time_since}'")
                        elif any(x in time_since for x in ["h", "d", "m", "s", "1w", "week"]):
                            print(f"Strict: Allowing based on time_since='{time_since}'")
                            recent_posts.append(p)
                        else:
                            print(f"Strict: Skipping post with unknown time_since='{time_since}'")
                    else:
                        print(f"Strict: Skipping post with NO DATE and NO time_since string.")
                
                if not recent_posts:
                    print("No posts found in the last 7 days.")
                    data = {"summary": {"total_posts": 0}, "posts": []}
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(data, f)
                    return data
                
                # Rank by engagement (reactions_count built in viral_research_apify is likes+comments+shares)
                for p in recent_posts:
                    p['engagement_score'] = p.get("reactions_count", 0)
                    
                recent_posts.sort(key=lambda x: x['engagement_score'], reverse=True)
                
                total_posts = len(recent_posts)
                total_engagements = sum(p['engagement_score'] for p in recent_posts)
                avg_engagement = round(total_engagements / total_posts, 2) if total_posts > 0 else 0
                
                best_post = recent_posts[0] if recent_posts else None
                
                # Calculate Tiers
                for i, p in enumerate(recent_posts):
                    percentile = i / total_posts if total_posts > 1 else 0
                    if percentile <= 0.20:
                        p['tier'] = 'A'
                    elif percentile <= 0.70:
                        p['tier'] = 'B'
                    else:
                        p['tier'] = 'C'
                
                summary = {
                    "total_posts": total_posts,
                    "total_engagements": total_engagements,
                    "avg_engagement": avg_engagement,
                    "best_post_title": best_post['title'] if best_post else "N/A"
                }
                
                final_data = {
                    "summary": summary,
                    "posts": recent_posts
                }
                
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(final_data, f, indent=4)
                    
                print(f"Surveillance complete. Saved {total_posts} recent posts.")
                return final_data
            
            else:
                print(f"Apify run failed using {api_key[:8]}")
        except Exception as e:
            print(f"Error with key {api_key[:8]}: {e}")
            if "Authentication" in str(e) or "credits" in str(e):
                continue
    
    print("FATAL: All Apify keys failed for surveillance.")
    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Surveillance Scraper")
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back (default: 30)")
    parser.add_argument("--uid", type=str, default="default", help="User ID for per-user data isolation")
    args = parser.parse_args()
    run_surveillance(days=args.days, uid=args.uid)
