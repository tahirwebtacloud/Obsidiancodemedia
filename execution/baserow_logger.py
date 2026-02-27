import os
import json
import argparse
import sys
import requests
from dotenv import load_dotenv

# Explicitly load .env from the project root
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    load_dotenv() # Fallback

def upload_file_to_baserow(file_path):
    """
    Uploads a file to Baserow and returns the public URL.
    """
    if not os.path.exists(file_path):
        return None
        
    base_url = os.getenv("BASEROW_URL", "https://api.baserow.io")
    token = os.getenv("BASEROW_TOKEN")
    
    url = f"{base_url}/api/user-files/upload-file/"
    headers = {
        "Authorization": f"Token {token}"
    }
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, headers=headers, files=files)
            
        if response.status_code == 200:
            data = response.json()
            # Baserow returns: {"url": "https://...", "thumbnails": {...}, "name": "..."}
            return data.get("url")
        else:
            print(f"File upload failed: {response.text}")
            return None
    except Exception as e:
        print(f"Exception uploading file: {e}")
        return None

def log_to_baserow(data_type, data_path, table_id=None):
    """
    Logs data to a Baserow table.
    """
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found.")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    base_url = os.getenv("BASEROW_URL", "https://api.baserow.io")
    token = os.getenv("BASEROW_TOKEN")
    
    if not token:
        print("Error: BASEROW_TOKEN not found in environment.")
        return

    if not table_id:
        if data_type == "trends":
            table_id = os.getenv("BASEROW_TABLE_ID_COMPETITOR_POSTS")
        elif data_type == "posts":
            table_id = os.getenv("BASEROW_TABLE_ID_GENERATED_CONTENT")
    
    if not table_id:
        print(f"Error: Table ID for {data_type} not provided and not found in environment.")
        return

    url = f"{base_url}/api/database/rows/table/{table_id}/?user_field_names=true"
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json"
    }

    # Prepare rows to add
    rows_to_add = []
    if data_type == "trends":
        for item in data:
            # Table (811989) fields: Creator, Content, Likes, Comments, Shares, Impressions, Post URL, Type, Rewritten Content, Date Posted, Post IMG URL, Post Video URL
            post_type = item.get("type", "text").capitalize()
            if not post_type:
                post_type = "Text"

            rows_to_add.append({
                "Creator": item.get("author_name", "Unknown"),
                "Content": item.get("text", ""),
                "Likes": str(item.get("reactions_count", 0)),
                "Comments": str(item.get("comments_count", 0)),
                "Shares": str(item.get("shares_count", 0)),
                "Post URL": item.get("url", ""),
                "Type": post_type,
                "Date Posted": item.get("posted_at", "")
            })
    elif data_type == "posts":
        # Table (811989) mapping for generated content
        
        # Data Mappings based on Verified Baserow API Metadata (2026-01-25)
        # Type (Text Basic, Article)
        type_map = {
            "text": "Text Basic",
            "article": "Article"
        }
        
        # Content Source (Direct Topic, News Article, Competitor, Obsidian Blog, YT Vid)
        source_map = {
            "topic": "Direct Topic",
            "news": "News Article",
            "competitor": "Competitor",
            "blog": "Obsidian Blog",
            "youtube": "YT Vid"
        }

        # Purpose (How-to, Story, Authority, Promo)
        purpose_map = {
            "educational": "How-to",
            "storytelling": "Story",
            "authority": "Authority",
            "promotional": "Promo"
        }

        # Visual Aspect (None, Single Image, Short Video, Carousel)
        aspect_map = {
            "image": "Single Image",
            "video": "Short Video",
            "carousel": "Carousel",
            "none": "None",
            "": "None",  # Handle empty string
            None: "None"
        }
        
        raw_source = data.get("source", "topic")
        baserow_source = source_map.get(raw_source, "Direct Topic")

        raw_type = data.get("type", "text")
        valid_type = type_map.get(raw_type, "Text Basic") # Fallback

        raw_purpose = data.get("purpose", "educational")
        baserow_purpose = purpose_map.get(raw_purpose, "How-to")

        # Visual Aspect logic
        # In script.js, we send visual_aspect as type if not none.
        # But we also need to know the aspect for the Visual Aspect column.
        # Check original form data if available or infer
        # If type is 'image'/'video'/'carousel', that's the aspect.
        # If type is 'text'/'article', aspect is 'none' or we check another field.
        # data usually has: caption, source, type, etc.
        # If visual_aspect was passed, use it.
        raw_aspect = data.get("visual_aspect", "")
        # If empty or none, explicitly set to "none" for logic checks
        if not raw_aspect or raw_aspect == "null" or raw_aspect == "undefined": 
             raw_aspect = "none"

        # If type is strictly text/article, strip aspect if not explicit
        if raw_type in ["text", "article"] and raw_aspect == "image": # legacy default
             # If asset_url exists, it's Img
             if data.get("asset_url"):
                 raw_aspect = "image"
             else:
                 raw_aspect = "none"
        
        baserow_aspect = aspect_map.get(raw_aspect, "None") # Default to None if unknown
        print(f"DEBUG BASEROW: Raw Aspect: '{data.get('visual_aspect')}' -> Processed: '{raw_aspect}' -> Baserow: '{baserow_aspect}'")


        # Prepare Image URL: Upload to Baserow if it's a local file
        raw_img_url = data.get("asset_url", "")
        final_img_url = raw_img_url
        
        if raw_img_url and raw_img_url.startswith("/"):
            # It's a local path (relative to root, e.g. /assets/generated_image.png)
            # Remove leading slash and construct full fs path
            # Assuming server root is CWD and .tmp is mounted
            # raw_img_url is like /assets/generated_image.png which maps to .tmp/generated_image.png
            # But the file is physically at .tmp/generated_image.png
            
            # Extract filename
            filename = os.path.basename(raw_img_url)
            local_path = f".tmp/{filename}"
            
            print(f"Uploading local image {local_path} to Baserow...")
            uploaded_url = upload_file_to_baserow(local_path)
            
            if uploaded_url:
                print(f"Upload success: {uploaded_url}")
                final_img_url = uploaded_url
            else:
                print("Upload failed, falling back to localhost URL")
                final_img_url = f"http://localhost:8000{raw_img_url}"

        rows_to_add.append({
            "Content": data.get("caption", ""),
            "Type": valid_type,
            "Content Source": baserow_source,
            "Purpose": baserow_purpose,
            "Visual Aspect": baserow_aspect,
            "IMG URL": final_img_url,
            "Vid URL": data.get("video_url", "")
        })

    # Baserow adding rows
    for row in rows_to_add:
        try:
            response = requests.post(url, headers=headers, json=row)
            if response.status_code in [200, 201]:
                print(f"Successfully added row to Baserow table {table_id}")
                
                # --- SYNC WITH LOCAL HISTORY ---
                if data_type == "posts":
                    history_file = "history.json"
                    if os.path.exists(history_file):
                        try:
                            with open(history_file, "r", encoding="utf-8") as hf:
                                history_data = json.load(hf)
                            
                            updated = False
                            for entry in history_data:
                                # Match by caption (highest fidelity match available)
                                if entry.get("caption") == data.get("caption"):
                                    entry["approved"] = True
                                    updated = True
                                    break
                            
                            if updated:
                                with open(history_file, "w", encoding="utf-8") as hf:
                                    json.dump(history_data, hf, indent=4, ensure_ascii=False)
                                print("Marked post as Approved in local history.")
                        except Exception as he:
                            print(f"Error updating local history: {he}")
                # ------------------------------
            else:
                print(f"Failed to add row to Baserow. Status: {response.status_code}, Error: {response.text}", file=sys.stderr)
                sys.exit(1) # Ensure process fails
        except Exception as e:
            print(f"Exception while logging to Baserow: {str(e)}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Log results to Baserow.")
    parser.add_argument("--type", required=True, help="Data type (posts, trends).")
    parser.add_argument("--path", required=True, help="Path to the JSON data.")
    parser.add_argument("--table_id", help="Target Baserow Table ID.")
    
    args = parser.parse_args()
    log_to_baserow(args.type, args.path, args.table_id)
