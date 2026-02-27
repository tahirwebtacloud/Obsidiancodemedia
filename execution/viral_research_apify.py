import os
import json
import re
import argparse
import requests
import html as html_parser
from datetime import datetime, timedelta
from apify_client import ApifyClient
from dotenv import load_dotenv
import urllib.parse

# Load environment variables
load_dotenv()


def _fetch_og_image(post_url):
    """Fetch the high-resolution OG image from a LinkedIn post page.
    LinkedIn embeds a properly-tokenized high-res image URL in the og:image meta tag.
    This bypasses the low-res thumbnails (shrink_20, shrink_160) returned by the Apify actor."""
    if not post_url or not post_url.startswith("http"):
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }
        resp = requests.get(post_url, headers=headers, timeout=10)
        match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', resp.text)
        if match:
            og_img = match.group(1)
            if og_img.startswith("http") and "licdn.com" in og_img:
                return og_img
    except Exception:
        pass
    return None


def extract_manifest_metadata(manifest_url):
    """
    Fetches the master manifest and extracts PDF download URL and full-res slide images.
    LinkedIn carousels/documents have a manifest JSON that contains:
    - transcribedDocumentUrl: downloadable PDF
    - perResolutions: multiple resolution variants with imageManifestUrl
    """
    if not manifest_url:
        return None, []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(manifest_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None, []
        
        data = resp.json()
        pdf_url = data.get("transcribedDocumentUrl")
        
        # Get highest resolution images from perResolutions
        slides = []
        resolutions = data.get("perResolutions", [])
        if resolutions:
            # Sort by resolution width descending and pick highest
            best_res = sorted(resolutions, key=lambda x: x.get("width", 0), reverse=True)[0]
            img_manifest = best_res.get("imageManifestUrl")
            if img_manifest:
                i_resp = requests.get(img_manifest, headers=headers, timeout=10)
                if i_resp.status_code == 200:
                    slides = i_resp.json().get("pages", [])
        
        print(f"    [manifest] pdf={'YES' if pdf_url else 'NO'} slides={len(slides)}")
        return pdf_url, slides
    except Exception as e:
        print(f"    [manifest] Error parsing manifest: {e}")
        return None, []


def sniff_manifest_from_html(url):
    """
    Fallback: Extracts manifestUrl directly from LinkedIn post HTML if Apify misses it.
    """
    if not url or not url.startswith("http"):
        return None
    print(f"    [sniff] Sniffing manifest for: {url[:80]}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        html_text = response.text
        
        # Pattern 1: manifestUrl in quoted JSON
        m = re.search(r'["\']manifestUrl["\']\s*:\s*["\']([^"\']+)["\']', html_text)
        if m:
            print(f"    [sniff] Found manifest via JSON pattern")
            return m.group(1)
        
        # Pattern 2: Inside data-native-document-config (escaped HTML)
        pattern = r'data-native-document-config\s*=\s*"([^"]+)"'
        m = re.search(pattern, html_text)
        if m:
            config_json = html_parser.unescape(m.group(1))
            try:
                config = json.loads(config_json)
                manifest = config.get("doc", {}).get("manifestUrl") or config.get("manifestUrl")
                if manifest:
                    print(f"    [sniff] Found manifest via config attribute")
                    return manifest
            except:
                pass

        print(f"    [sniff] No manifest found")
        return None
    except Exception as e:
        print(f"    [sniff] Error: {e}")
        return None


def _upgrade_linkedin_image_res(url):
    """Upgrade LinkedIn CDN profile photo URLs to a reasonable resolution.
    NOTE: feedshare image paths are NOT upgraded because LinkedIn's CDN only serves
    the exact size variants that were generated at upload time. Attempting to swap
    the path returns 403. We use the original URLs as-is."""
    if not url or "licdn.com" not in url:
        return url
    # Profile photos: always have standard sizes, safe to upgrade
    url = re.sub(r'/profile-displayphoto-(shrink|scale)_\d+_\d+/', '/profile-displayphoto-shrink_800_800/', url)
    return url


def _normalize_media_url(url):
    """Return a clean, direct media URL for preview. Strip tracking params that can cause 403 or distortion.
    LinkedIn CDN hosts (media.licdn.com, media-exp*.licdn.com) NEED their auth/token params to serve images,
    so we skip param stripping for those domains entirely."""
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if not url.startswith("http"):
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        # LinkedIn CDN URLs: upgrade resolution then return (keep auth params intact)
        if parsed.hostname and "licdn.com" in parsed.hostname:
            return _upgrade_linkedin_image_res(url)
        # For non-LinkedIn URLs, strip common tracking/query params that break image serving
        qs = urllib.parse.parse_qs(parsed.query)
        drop = {"trk", "ref", "tracking", "utm_"}
        new_qs = {k: v for k, v in qs.items() if not any(k.lower().startswith(d) for d in drop)}
        new_query = urllib.parse.urlencode(new_qs, doseq=True)
        new = parsed._replace(query=new_query)
        return urllib.parse.urlunparse(new)
    except Exception:
        return url


def _first_valid_url(*candidates):
    """Return the first non-empty, HTTP(S) URL from candidates."""
    for c in candidates:
        u = (c or "").strip()
        if u and u.startswith("http"):
            return _normalize_media_url(u)
    return ""

# Configuration
def get_apify_keys():
    """Retrieves all available Apify keys from the environment."""
    keys = [os.getenv("APIFY_API_KEY")]
    # Dynamically load APIFY_API_KEY_2 through APIFY_API_KEY_5
    for i in range(2, 6):
        key = os.getenv(f"APIFY_API_KEY_{i}")
        if key:
            keys.append(key)
    return [k for k in keys if k]

def run_viral_research(topic=None, post_type="all", urls=None):
    """
    Runs Apify LinkedIn Scraper with automatic key rotation/fallback.
    """
    keys_to_try = get_apify_keys()
    
    for api_key in keys_to_try:
        try:
            client = ApifyClient(api_key)
            TARGET_ACTOR = "supreme_coder/linkedin-post"
            
            if urls:
                print(f"Starting Competitor Research for specific URLs: {urls}")
                target_urls = urls
            else:
                print(f"Starting Viral Research for: {topic} (Type: {post_type})")
                # Construct LinkedIn Search URL for the topic
                encoded_topic = urllib.parse.quote(topic)
                # Search for Content, sorted by relevance (default)
                search_url = f"https://www.linkedin.com/search/results/content/?keywords={encoded_topic}&origin=GLOBAL_SEARCH_HEADER"
                target_urls = [search_url]

            run_input = {
                "urls": target_urls,
                "limitPerSource": 20,  # Fetch ~20 items ( harvestapi was 15)
                "deepScrape": True     # Ensure full data including media
            }

            print(f">>> Calling Apify Actor: {TARGET_ACTOR} with key: {api_key[:12]}...")
            run = client.actor(TARGET_ACTOR).call(run_input=run_input)
            
            if run['status'] == "SUCCEEDED":
                print(f">>> Apify run finished. Status: SUCCEEDED")
                items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
                
                from cost_tracker import CostTracker
                tracker = CostTracker()
                tracker.add_apify_page_cost(len(items), operation="LinkedIn Viral/Competitor Scrape")
                
                return process_items(items, urls, post_type)
            else:
                print(f"Warning: Apify run status {run['status']}. Trying next key...")
                continue

        except Exception as e:
            print(f"Error with key {api_key[:12]}: {str(e)}")
            if "Authentication" in str(e) or "credits" in str(e):
                print("Likely auth/credit issue. Attempting fallback...")
                continue
            else:
                # Other errors might be code issues, but we still try next key
                continue

    print("FATAL: All Apify keys failed.")
    return []

def _extract_url_from_val(val):
    """Safely extract a URL string from a value that may be a str, dict, or list."""
    if isinstance(val, str) and val.strip().startswith("http"):
        return val.strip()
    if isinstance(val, dict):
        return val.get("url") or val.get("src") or val.get("imageUrl") or ""
    if isinstance(val, list) and val:
        return _extract_url_from_val(val[0])
    return ""


def process_items(items, urls, post_type):
    print(f">>> Scraped {len(items)} items from LinkedIn.")
    
    # Save raw items for debugging
    os.makedirs(".tmp", exist_ok=True)
    with open(".tmp/raw_scraped.json", "w") as f:
        json.dump(items, f, indent=4)
    
    # Debug: log all top-level keys found across all items
    all_keys = set()
    for item in items:
        all_keys.update(item.keys())
    print(f">>> DEBUG all raw keys: {sorted(all_keys)}")

    filtered_items = []
    found_types = {}
    
    # Extract expected author IDs from input URLs if provided (for Competitor Research)
    expected_author_ids = set()
    if urls:
        for u in urls:
            if "/in/" in u:
                # e.g. https://www.linkedin.com/in/keithmortier/ -> keithmortier
                parts = u.rstrip("/").split("/in/")
                if len(parts) > 1:
                    expected_author_ids.add(parts[1].split('?')[0].lower())

    for item in items:
        # If we are doing competitor research (expected_author_ids populated),
        # only keep posts by the requested author(s)
        if expected_author_ids:
            author_obj = item.get("author") or {}
            public_id = (author_obj.get("publicId") or "").lower()
            if not public_id or public_id not in expected_author_ids:
                continue
        content = item.get("text") or item.get("content") or item.get("description", "")
        url = item.get("linkedinUrl") or item.get("url") or item.get("link", "")
        
        # ---- Engagement ----
        eng = item.get("engagement") or {}
        likes = (
            eng.get("likes") or 
            item.get("reactionsCount") or 
            item.get("likesCount") or 
            item.get("numLikes") or 0
        )
        comments = (
            eng.get("comments") or 
            item.get("commentsCount") or 
            item.get("numComments") or 0
        )
        shares = (
            eng.get("shares") or 
            item.get("sharesCount") or 
            item.get("numShares") or 0
        )
        total_reactions = likes + comments + shares
        
        # ---- Type Detection ----
        # PRIORITY: Use the actor's own "type" field first (supreme_coder provides this directly)
        raw_type = (item.get("type") or "").lower().strip()
        # Map actor type strings to our normalized types
        TYPE_MAP = {
            "image": "image",
            "article": "image",       # articles have largeImage — treat as image for display
            "linkedinvideo": "video",
            "video": "video",
            "document": "carousel",
            "carousel": "carousel",
            "poll": "poll",
            "text": "text",
        }
        post_type_actual = TYPE_MAP.get(raw_type, "")
        
        # Fallback: if actor didn't provide type or it's unknown, detect ourselves
        if not post_type_actual:
            article_data_check = item.get("article") or {}
            video_data_check = item.get("postVideo") or item.get("video") or item.get("linkedinVideo") or {}
            has_video = bool(
                video_data_check.get("videoUrl") or video_data_check.get("streamUrl") or
                video_data_check.get("url") or item.get("videoUrl") or
                item.get("videos") or video_data_check.get("videoPlayMetadata")
            )
            has_images = bool(item.get("postImages") or item.get("images") or item.get("image"))
            has_article_img = bool(article_data_check.get("largeImage") or article_data_check.get("image"))
            
            if has_video:
                post_type_actual = "video"
            elif item.get("document"):
                post_type_actual = "carousel"
            elif has_images or has_article_img:
                post_type_actual = "image"
            elif item.get("poll"):
                post_type_actual = "poll"
            else:
                post_type_actual = "text"

        found_types[post_type_actual] = found_types.get(post_type_actual, 0) + 1

        # 1. Format Match Check
        if not urls and post_type.lower() != "all":
            if post_type.lower() not in post_type_actual.lower():
                continue
            
        # 2. Performance Filter
        if not urls and total_reactions < 0:
            continue
        
        # ---- Article data ----
        article_data = item.get("article") or {}

        # ---- Exhaustive Image URL Extraction ----
        # Priority order matches the actual supreme_coder schema
        image_urls = []
        
        # 1) "image" — top-level direct URL string (supreme_coder primary field for image posts)
        top_img = item.get("image")
        if top_img and isinstance(top_img, str) and top_img.startswith("http"):
            image_urls.append(top_img)
        
        # 2) "images" — list of URL strings (supreme_coder)
        for img in (item.get("images") or []):
            u = _extract_url_from_val(img)
            if u and u not in image_urls:
                image_urls.append(u)
        
        # 3) "postImages" — list of dicts (harvestapi schema)
        if not image_urls:
            for img in (item.get("postImages") or []):
                u = _extract_url_from_val(img)
                if u: image_urls.append(u)

        # 4) Article images — largeImage is the primary field (supreme_coder)
        if not image_urls and article_data:
            art_large = article_data.get("largeImage") or ""
            if art_large and isinstance(art_large, str) and art_large.startswith("http"):
                image_urls.append(art_large)
            if not image_urls:
                art_img = article_data.get("image") or {}
                art_url = art_img.get("url") if isinstance(art_img, dict) else (art_img if isinstance(art_img, str) and art_img.startswith("http") else "")
                if art_url:
                    image_urls.append(art_url)
            if not image_urls:
                for k in ("imageUrl", "thumbnailUrl", "coverImage"):
                    v = article_data.get(k, "")
                    if v and isinstance(v, str) and v.startswith("http"):
                        image_urls.append(v)
                        break

        # 5) media / attachments (other actor schemas)
        if not image_urls:
            for m in (item.get("media") or []):
                u = _extract_url_from_val(m)
                if u: image_urls.append(u)
        if not image_urls:
            for a in (item.get("attachments") or []):
                u = _extract_url_from_val(a)
                if u: image_urls.append(u)
        
        # 6) Top-level fallback fields
        if not image_urls:
            for key in ("imageUrl", "previewImage", "ogImage"):
                val = item.get(key)
                if val and isinstance(val, str) and val.startswith("http"):
                    image_urls.append(val)
                    break

        # 7) sharedContent (reshared posts)
        if not image_urls and item.get("sharedContent"):
            sc = item["sharedContent"]
            for k in ("image", "imageUrl", "largeImage"):
                sc_img = sc.get(k, "")
                u = _extract_url_from_val(sc_img) if sc_img else ""
                if u:
                    image_urls.append(u)
                    break

        # 8) Fetch OG image for image-type posts with low-res URLs (shrink_20, shrink_160)
        if post_type_actual == "image" and url:
            low_res_indices = [i for i, img_u in enumerate(image_urls)
                               if re.search(r'feedshare-shrink_(20|160|100|80)\b', img_u)]
            if low_res_indices or not image_urls:
                og_img = _fetch_og_image(url)
                if og_img:
                    if low_res_indices:
                        # Replace the low-res URL(s) with the OG image
                        image_urls[low_res_indices[0]] = og_img
                        # Remove remaining low-res duplicates (reverse to preserve indices)
                        for idx in reversed(low_res_indices[1:]):
                            image_urls.pop(idx)
                    else:
                        image_urls.insert(0, og_img)
                    print(f"    [og] Upgraded low-res image via OG tag")

        # Normalize and dedupe
        image_urls = list(dict.fromkeys(_normalize_media_url(u) for u in image_urls if u))

        clean_content = content.replace("\n", " ").strip()
        title = clean_content[:60] + "..." if len(clean_content) > 60 else clean_content

        # ---- Video URL Extraction ----
        post_video = item.get("postVideo") or item.get("video") or item.get("linkedinVideo") or {}
        video_url = (
            post_video.get("videoUrl") or 
            post_video.get("streamUrl") or 
            post_video.get("url") or 
            item.get("videoUrl") or 
            ""
        )
        
        # Handle 'linkedinVideo' complex structure (videoPlayMetadata → progressiveStreams)
        if not video_url and post_video.get("videoPlayMetadata"):
            try:
                 streams = post_video["videoPlayMetadata"].get("progressiveStreams", [])
                 if streams:
                     for stream in streams:
                         locs = stream.get("streamingLocations", [])
                         if locs:
                             video_url = locs[0].get("url")
                             break
            except Exception as e:
                print(f"Error parsing linkedinVideo: {e}")

        if not video_url and item.get("videos"):
            try:
                video_url = item["videos"][0].get("url") or item["videos"][0].get("streamUrl") or ""
            except:
                pass

        video_thumbnail = _first_valid_url(
            post_video.get("thumbnailUrl"),
            post_video.get("thumbnail"),
            post_video.get("image"),
            post_video.get("thumbnailImage"),
            item.get("videoThumbnail"),
        )
        # Handle linkedinVideo thumbnail (rootUrl + artifacts)
        if not video_thumbnail and post_video.get("videoPlayMetadata"):
            try:
                thumb_meta = post_video["videoPlayMetadata"].get("thumbnail", {})
                if isinstance(thumb_meta, str):
                    video_thumbnail = _normalize_media_url(thumb_meta)
                else:
                    artifacts = (thumb_meta or {}).get("artifacts", [])
                    root_url = (thumb_meta or {}).get("rootUrl", "")
                    if artifacts and root_url:
                        seg = artifacts[0].get("fileIdentifyingUrlPathSegment", "") or artifacts[0].get("url", "")
                        video_thumbnail = _normalize_media_url(root_url + seg) if seg else ""
            except Exception:
                pass

        # ---- Document / Carousel ----
        doc_data = item.get("document") or {}
        document_url = doc_data.get("url") or doc_data.get("documentUrl") or ""
        document_title = doc_data.get("title") or doc_data.get("name") or ""
        carousel_preview_url = ""
        carousel_page_count = 0
        carousel_slide_urls = []

        if doc_data or post_type_actual == "carousel":
            # --- Manifest-based extraction (full-res slides + PDF) ---
            m_url = doc_data.get("manifestUrl") or doc_data.get("url") or doc_data.get("transcribedDocumentUrl")

            # FALLBACK: Sniff manifest from post HTML if Apify didn't provide it
            if not m_url or "manifest" not in str(m_url):
                if post_type_actual == "carousel" and url:
                    m_url = sniff_manifest_from_html(url)

            if m_url and "manifest" in str(m_url):
                print(f"    [carousel] Fetching deep manifest for: {url[:60]}")
                deep_pdf, deep_slides = extract_manifest_metadata(m_url)
                if deep_pdf:
                    document_url = deep_pdf
                if deep_slides:
                    # deep_slides are full-res image URLs from the manifest
                    carousel_slide_urls = [s for s in deep_slides if isinstance(s, str) and s.startswith("http")]

            # Fallback to coverPages if manifest didn't yield slides
            if not carousel_slide_urls:
                cover_pages = doc_data.get("coverPages") or []
                for cp in cover_pages:
                    u = _normalize_media_url(cp) if isinstance(cp, str) and cp.startswith("http") else ""
                    if u: carousel_slide_urls.append(u)

            # Fallback document URL
            if not document_url:
                document_url = (
                    doc_data.get("transcribedDocumentUrl") or
                    doc_data.get("url") or
                    doc_data.get("documentUrl") or
                    item.get("documentUrl") or
                    doc_data.get("nativeAppDocumentUrl") or
                    ""
                )

            # Preview URL: first slide or fallback
            carousel_preview_url = (
                carousel_slide_urls[0] if carousel_slide_urls else
                _first_valid_url(
                    (doc_data.get("coverPages") or [None])[0],
                    doc_data.get("coverUrl"),
                    doc_data.get("coverImage"),
                    doc_data.get("thumbnailUrl"),
                    doc_data.get("thumbnail"),
                )
            )

            carousel_page_count = (
                len(carousel_slide_urls) or
                doc_data.get("totalPageCount") or
                doc_data.get("pageCount") or
                doc_data.get("totalPages") or
                len(doc_data.get("coverPages") or []) or
                0
            )

        # ---- Author Info ----
        author_obj = item.get("author") or {}
        # Build author name from firstName+lastName if "name" isn't available
        author_first = author_obj.get("firstName", "")
        author_last = author_obj.get("lastName", "")
        author_name = (
            item.get("authorName") or
            author_obj.get("name") or
            (f"{author_first} {author_last}".strip() if (author_first or author_last) else "") or
            item.get("fullName") or
            author_obj.get("fullName") or
            "Unknown"
        )
        # Author profile picture — ONLY for avatar, NOT for card thumbnail
        author_profile_pic = _first_valid_url(
            item.get("authorProfilePicture"),
            author_obj.get("picture"),
            author_obj.get("profilePicture"),
            author_obj.get("profileImageUrl"),
            author_obj.get("image"),
            author_obj.get("logo"),
            item.get("authorProfilePic"),
            item.get("profilePicture"),
        )

        # ---- Best Preview URL (cascading priority — NO profile pic fallback) ----
        preview_image_url = ""
        if post_type_actual == "video":
            preview_image_url = video_thumbnail
        elif post_type_actual == "carousel" and carousel_preview_url:
            preview_image_url = carousel_preview_url
        elif image_urls:
            preview_image_url = image_urls[0]
        # Secondary fallbacks (but never profile pic)
        if not preview_image_url and video_thumbnail:
            preview_image_url = video_thumbnail
        if not preview_image_url and image_urls:
            preview_image_url = image_urls[0]
        if not preview_image_url and carousel_preview_url:
            preview_image_url = carousel_preview_url

        try:
            print(f"  > [{post_type_actual:8s}] images={len(image_urls)} preview={'YES' if preview_image_url else 'NO':3s} | {title[:50].encode('ascii', 'replace').decode()}")
        except Exception:
            print(f"  > [{post_type_actual:8s}] images={len(image_urls)} preview={'YES' if preview_image_url else 'NO':3s}")

        filtered_items.append({
            "url": url,
            "title": title,
            "author_name": author_name,
            "author_profile_pic": author_profile_pic,
            "text": content,
            "type": post_type_actual,
            "reactions_count": total_reactions,
            "comments_count": comments,
            "shares_count": shares,
            "image_urls": image_urls,
            "image_count": len(image_urls),
            "video_url": video_url,
            "video_thumbnail": video_thumbnail,
            "document_url": document_url,
            "document_title": document_title,
            "carousel_preview_url": carousel_preview_url,
            "carousel_slide_urls": carousel_slide_urls,
            "carousel_page_count": carousel_page_count,
            "preview_image_url": preview_image_url,
            "posted_at": item.get("postedAtISO") or (item.get("postedAt", {}).get("date") if isinstance(item.get("postedAt"), dict) else item.get("postedAt")) or "",
            "time_since_posted": item.get("timeSincePosted") or item.get("timeSince") or ""
        })
    
    print(f">>> Scraped types distribution: {found_types}")

    # Sort by performance
    filtered_items.sort(key=lambda x: x["reactions_count"], reverse=True)
    
    # Save results
    output_path = ".tmp/viral_trends.json"
    with open(output_path, "w") as f:
        json.dump(filtered_items, f, indent=4)
        
    print(f"Research Complete. Found {len(filtered_items)} relevant items.")
    return filtered_items

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Viral Research using Apify.")
    parser.add_argument("--topic", help="Research topic.")
    parser.add_argument("--type", default="all", help="Desired post format.")
    parser.add_argument("--urls", help="Comma-separated profile/post URLs.")
    
    args = parser.parse_args()
    urls_list = args.urls.split(",") if args.urls else None
    run_viral_research(args.topic, args.type, urls_list)

