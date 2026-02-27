import os
import json
import requests
import time
from dotenv import load_dotenv

load_dotenv()

TOKEN_FILE = "linkedin_tokens.json"

def get_linkedin_auth_url():
    client_id = os.getenv("LINKEDIN_CLIENT_ID")
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI")
    # Added rw_events for Phase 5 Event creation
    scope = "w_member_social openid profile email rw_events"
    
    auth_url = (
        f"https://www.linkedin.com/oauth/v2/authorization?"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"scope={scope.replace(' ', '%20')}&"
        f"state=auth_{int(time.time())}"
    )
    return auth_url

def exchange_code_for_token(code):
    client_id = os.getenv("LINKEDIN_CLIENT_ID")
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI")
    
    url = "https://www.linkedin.com/oauth/v2/accessToken"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    response = requests.post(url, data=data, headers=headers)
    if response.status_code == 200:
        token_data = response.json()
        token_data["expires_at"] = int(time.time()) + token_data.get("expires_in", 5184000)
        save_tokens(token_data)
        return token_data, None
    else:
        return None, response.text

def refresh_linkedin_token():
    tokens = load_tokens()
    if not tokens or "refresh_token" not in tokens:
        return None, "No refresh token available"
    
    client_id = os.getenv("LINKEDIN_CLIENT_ID")
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
    
    url = "https://www.linkedin.com/oauth/v2/accessToken"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": client_id,
        "client_secret": client_secret
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    response = requests.post(url, data=data, headers=headers)
    if response.status_code == 200:
        token_data = response.json()
        token_data["expires_at"] = int(time.time()) + token_data.get("expires_in", 5184000)
        # Update existing tokens with new access token
        tokens.update(token_data)
        save_tokens(tokens)
        return tokens, None
    else:
        return None, response.text

def save_tokens(token_data):
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=4)

def load_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def get_valid_token():
    tokens = load_tokens()
    if not tokens:
        return None, "Not authenticated"
    
    # Check if expired (with 5 min buffer)
    if tokens.get("expires_at", 0) < int(time.time()) + 300:
        print("Token expired or expiring soon, refreshing...")
        return refresh_linkedin_token()
    
    return tokens, None

def get_user_info():
    tokens, error = get_valid_token()
    if error:
        return None, error
    
    url = "https://api.linkedin.com/v2/userinfo"
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json(), None
    else:
        return None, response.text

def post_text(commentary, visibility="PUBLIC"):
    tokens, error = get_valid_token()
    if error:
        return None, error
    
    user_info, error = get_user_info()
    if error:
        return None, f"Failed to get user info: {error}"
    
    # OpenID Connect 'sub' is the member ID
    author_urn = f"urn:li:person:{user_info['sub']}"
    
    url = "https://api.linkedin.com/rest/posts"
    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": "202602", # Use current stable version
        "Content-Type": "application/json"
    }
    
    payload = {
        "author": author_urn,
        "commentary": commentary,
        "visibility": visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        # Post ID is in X-RestLi-Id header
        return response.headers.get("X-RestLi-Id"), None
    else:
        return None, response.text

def upload_image(file_path):
    """
    Handles the 2-step process to upload an image to LinkedIn.
    1. Initialize upload (POST /rest/images?action=initializeUpload)
    2. Upload binary (PUT to uploadUrl)
    """
    tokens, error = get_valid_token()
    if error:
        return None, error
    
    user_info, error = get_user_info()
    if error:
        return None, f"Failed to get user info: {error}"
    
    author_urn = f"urn:li:person:{user_info['sub']}"
    
    # Step 1: Initialize Upload
    init_url = "https://api.linkedin.com/rest/images?action=initializeUpload"
    init_headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": "202602",
        "Content-Type": "application/json"
    }
    init_payload = {
        "initializeUploadRequest": {
            "owner": author_urn
        }
    }
    
    print(f"Initializing image upload for {author_urn}...")
    init_response = requests.post(init_url, json=init_payload, headers=init_headers)
    if init_response.status_code != 200:
        return None, f"Init failed: {init_response.text}"
    
    init_data = init_response.json()
    upload_url = init_data["value"]["uploadUrl"]
    image_urn = init_data["value"]["image"]
    
    # Step 2: Upload Binary
    print(f"Uploading binary to {upload_url[:50]}...")
    try:
        with open(file_path, "rb") as f:
            binary_data = f.read()
            
        upload_headers = {
            "Authorization": f"Bearer {tokens['access_token']}",
            # For the binary upload, LinkedIn often expects just the binary, 
            # but sometimes needs headers. Versioned API docs specify PUT usually.
        }
        
        # Use PUT for the binary upload step as per LinkedIn versioned docs
        upload_response = requests.put(upload_url, data=binary_data, headers=upload_headers)
        
        if upload_response.status_code in [200, 201]:
            print(f"Image uploaded successfully! URN: {image_urn}")
            return image_urn, None
        else:
            return None, f"Binary upload failed: {upload_response.status_code} {upload_response.text}"
            
    except Exception as e:
        return None, f"File error: {str(e)}"

def post_with_image(commentary, image_urn, visibility="PUBLIC"):
    tokens, error = get_valid_token()
    if error:
        return None, error
    
    user_info, error = get_user_info()
    if error:
        return None, f"Failed to get user info: {error}"
    
    author_urn = f"urn:li:person:{user_info['sub']}"
    
    url = "https://api.linkedin.com/rest/posts"
    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": "202602",
        "Content-Type": "application/json"
    }
    
    payload = {
        "author": author_urn,
        "commentary": commentary,
        "visibility": visibility,
        "content": {
            "media": {
                "id": image_urn,
                "altText": "LinkedIn Post Generator Image" # Optional but good for accessibility
            }
        },
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        return response.headers.get("X-RestLi-Id"), None
    else:
        return None, response.text

def post_article(commentary, article_url, title, description, thumbnail_urn=None, visibility="PUBLIC"):
    tokens, error = get_valid_token()
    if error:
        return None, error
    
    user_info, error = get_user_info()
    if error:
        return None, f"Failed to get user info: {error}"
    
    author_urn = f"urn:li:person:{user_info['sub']}"
    
    url = "https://api.linkedin.com/rest/posts"
    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": "202602",
        "Content-Type": "application/json"
    }
    
    payload = {
        "author": author_urn,
        "commentary": commentary,
        "visibility": visibility,
        "content": {
            "article": {
                "source": article_url,
                "title": title,
                "description": description
            }
        },
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False
    }
    
    if thumbnail_urn:
        payload["content"]["article"]["thumbnail"] = thumbnail_urn
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        return response.headers.get("X-RestLi-Id"), None
    else:
        return None, response.text

def post_poll(commentary, question, options, duration="THREE_DAYS", visibility="PUBLIC"):
    """
    options: list of strings (2-4)
    duration: ONE_DAY, THREE_DAYS, ONE_WEEK, TWO_WEEK
    """
    tokens, error = get_valid_token()
    if error:
        return None, error
    
    user_info, error = get_user_info()
    if error:
        return None, f"Failed to get user info: {error}"
    
    author_urn = f"urn:li:person:{user_info['sub']}"
    
    url = "https://api.linkedin.com/rest/posts"
    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": "202602",
        "Content-Type": "application/json"
    }
    
    poll_options = [{"text": opt} for opt in options]
    
    payload = {
        "author": author_urn,
        "commentary": commentary,
        "visibility": visibility,
        "content": {
            "poll": {
                "question": question,
                "options": poll_options,
                "settings": {
                    "duration": duration
                }
            }
        },
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        return response.headers.get("X-RestLi-Id"), None
    else:
        return None, response.text

def upload_document(file_path, title):
    """
    Handles the 2-step process to upload a document to LinkedIn.
    1. Initialize upload (POST /rest/documents?action=initializeUpload)
    2. Upload binary (PUT to uploadUrl)
    """
    tokens, error = get_valid_token()
    if error:
        return None, error
    
    user_info, error = get_user_info()
    if error:
        return None, f"Failed to get user info: {error}"
    
    author_urn = f"urn:li:person:{user_info['sub']}"
    
    # Step 1: Initialize Upload
    init_url = "https://api.linkedin.com/rest/documents?action=initializeUpload"
    init_headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": "202602",
        "Content-Type": "application/json"
    }
    init_payload = {
        "initializeUploadRequest": {
            "owner": author_urn
        }
    }
    
    print(f"Initializing document upload for {author_urn}...")
    init_response = requests.post(init_url, json=init_payload, headers=init_headers)
    if init_response.status_code != 200:
        return None, f"Init failed: {init_response.text}"
    
    init_data = init_response.json()
    upload_url = init_data["value"]["uploadUrl"]
    doc_urn = init_data["value"]["document"]
    
    # Step 2: Upload Binary
    print(f"Uploading document binary to {upload_url[:50]}...")
    try:
        with open(file_path, "rb") as f:
            binary_data = f.read()
            
        upload_headers = {
            "Authorization": f"Bearer {tokens['access_token']}"
        }
        
        upload_response = requests.put(upload_url, data=binary_data, headers=upload_headers)
        
        if upload_response.status_code in [200, 201]:
            print(f"Document uploaded successfully! URN: {doc_urn}")
            return doc_urn, None
        else:
            return None, f"Binary upload failed: {upload_response.status_code} {upload_response.text}"
            
    except Exception as e:
        return None, f"File error: {str(e)}"

def post_carousel(commentary, doc_urn, title, visibility="PUBLIC"):
    tokens, error = get_valid_token()
    if error:
        return None, error
    
    user_info, error = get_user_info()
    if error:
        return None, f"Failed to get user info: {error}"
    
    author_urn = f"urn:li:person:{user_info['sub']}"
    
    url = "https://api.linkedin.com/rest/posts"
    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": "202602",
        "Content-Type": "application/json"
    }
    
    payload = {
        "author": author_urn,
        "commentary": commentary,
        "visibility": visibility,
        "content": {
            "media": {
                "id": doc_urn,
                "title": title
            }
        },
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        return response.headers.get("X-RestLi-Id"), None
    else:
        return None, response.text

def post_event(title, description, start_time_ms, end_time_ms=None, is_online=True, event_url=None):
    """
    Creates a LinkedIn Event.
    Note: Requires rw_events scope and Event Management API access.
    """
    tokens, error = get_valid_token()
    if error:
        return None, error
    
    # Construct personal author URN
    user_info, error = get_user_info()
    if error:
        return None, f"Failed to get user info: {error}"
    
    author_urn = f"urn:li:person:{user_info['sub']}"
    
    url = "https://api.linkedin.com/rest/events"
    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": "202602",
        "Content-Type": "application/json"
    }
    
    payload = {
        "title": title,
        "description": description,
        "owner": author_urn,
        "eventCategory": "STANDARD",
        "eventType": "ONLINE" if is_online else "IN_PERSON",
        "timeRange": {
            "start": start_time_ms
        }
    }
    
    if end_time_ms:
        payload["timeRange"]["end"] = end_time_ms
    
    if event_url:
        payload["externalEventUrl"] = event_url
        
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        return response.headers.get("X-RestLi-Id"), None
    else:
        return None, response.text

if __name__ == "__main__":
    # Quick test
    # print(f"Auth URL: {get_linkedin_auth_url()}")
    pass
