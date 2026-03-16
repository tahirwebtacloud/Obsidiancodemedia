"""
Blotato API Client
Handles all communication with the Blotato API.
"""

import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

BASE_URL = "https://backend.blotato.com/v2"


def _get_api_key():
    """Get Blotato API key from environment."""
    key = os.getenv("BLOTATO_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "BLOTATO_API_KEY not set. Add it to your .env file.\n"
            "Generate at: https://my.blotato.com/settings > API"
        )
    return key


def _request(method, endpoint, data=None):
    """Make an authenticated request to the Blotato API."""
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "blotato-api-key": _get_api_key(),
        "Content-Type": "application/json",
    }

    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            resp_data = resp.read().decode("utf-8")
            return json.loads(resp_data) if resp_data else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.read else ""
        raise RuntimeError(
            f"Blotato API error {e.code}: {error_body}\n"
            f"Endpoint: {method} {endpoint}"
        )


# ── Account Management ──────────────────────────────────────────────

def get_accounts(platform=None):
    """List connected social accounts. Optionally filter by platform."""
    endpoint = "/users/me/accounts"
    if platform:
        endpoint += f"?platform={platform}"
    response = _request("GET", endpoint)
    # API wraps accounts in {"items": [...]}
    if isinstance(response, dict) and "items" in response:
        return response["items"]
    return response


def get_subaccounts(account_id):
    """Get subaccounts (LinkedIn company pages, Facebook pages)."""
    response = _request("GET", f"/users/me/accounts/{account_id}/subaccounts")
    if isinstance(response, dict) and "items" in response:
        return response["items"]
    return response


def get_linkedin_account():
    """Get LinkedIn account ID and optional page IDs."""
    accounts = get_accounts(platform="linkedin")
    if not accounts:
        raise ValueError("No LinkedIn account connected in Blotato. Connect at https://my.blotato.com/settings")

    account = accounts[0] if isinstance(accounts, list) else accounts
    account_id = account.get("id")
    fullname = account.get("fullname", "Unknown")

    result = {
        "account_id": account_id,
        "fullname": fullname,
        "pages": []
    }

    # Check for company pages
    try:
        subs = get_subaccounts(account_id)
        if subs:
            result["pages"] = [
                {"id": s.get("id"), "name": s.get("fullname", s.get("username", "Unknown"))}
                for s in (subs if isinstance(subs, list) else [subs])
            ]
    except Exception:
        pass  # No subaccounts = personal profile only

    return result


# ── Media Upload ────────────────────────────────────────────────────

def upload_media(url_or_base64):
    """
    Upload media to Blotato's servers.

    Args:
        url_or_base64: A publicly accessible URL or base64-encoded image data.

    Returns:
        dict with 'url' key containing the Blotato-hosted media URL.
    """
    return _request("POST", "/media", {"url": url_or_base64})


# ── Publishing ──────────────────────────────────────────────────────

def publish_post(account_id, text, platform="linkedin", media_urls=None,
                 page_id=None, scheduled_time=None, use_next_free_slot=False):
    """
    Publish or schedule a post.

    Args:
        account_id: From get_accounts()
        text: Post content
        platform: 'linkedin', 'twitter', 'threads', etc.
        media_urls: List of public image/video URLs
        page_id: For LinkedIn company pages (None = personal profile)
        scheduled_time: ISO 8601 timestamp (None = immediate)
        use_next_free_slot: Use Blotato's calendar for next slot

    Returns:
        dict with postSubmissionId for polling
    """
    payload = {
        "post": {
            "accountId": str(account_id),
            "content": {
                "text": text,
                "mediaUrls": media_urls or [],
                "platform": platform,
            },
            "target": {
                "targetType": platform,
            }
        }
    }

    # LinkedIn company page
    if page_id:
        payload["post"]["target"]["pageId"] = str(page_id)

    # Scheduling
    if scheduled_time:
        payload["scheduledTime"] = scheduled_time
    elif use_next_free_slot:
        payload["useNextFreeSlot"] = True

    return _request("POST", "/posts", payload)


def get_post_status(post_submission_id):
    """Poll for post publication status."""
    return _request("GET", f"/posts/{post_submission_id}")


def wait_for_post(post_submission_id, timeout=120, interval=3):
    """
    Poll until post reaches terminal state.

    Returns:
        dict with status ('published', 'failed', or 'scheduled') and details
    """
    start = time.time()
    while time.time() - start < timeout:
        result = get_post_status(post_submission_id)
        status = result.get("status", "")

        if status in ("published", "failed", "scheduled"):
            return result

        time.sleep(interval)

    return {"status": "timeout", "message": f"Post did not complete within {timeout}s"}


# ── Source Extraction ───────────────────────────────────────────────

def extract_source(source_type, url_or_text):
    """
    Extract content from a URL or text.

    Args:
        source_type: 'article', 'youtube', 'twitter', 'tiktok', 'pdf', 'text'
        url_or_text: URL or text content

    Returns:
        dict with source resolution ID for polling
    """
    payload = {
        "source": {
            "sourceType": source_type,
        }
    }

    if source_type == "text":
        payload["source"]["text"] = url_or_text
    else:
        payload["source"]["url"] = url_or_text

    return _request("POST", "/source-resolutions-v3", payload)


def get_source_status(source_id):
    """Poll for source extraction status."""
    return _request("GET", f"/source-resolutions-v3/{source_id}")


# ── Visual Generation ───────────────────────────────────────────────

def get_templates():
    """List available video/image templates."""
    return _request("GET", "/videos/templates")


def create_visual(template_id, prompt, inputs=None):
    """
    Generate a visual from a template.

    Args:
        template_id: UUID of the template
        prompt: AI prompt for content generation
        inputs: Dict of template inputs (empty {} for AI-driven)

    Returns:
        dict with creation ID for polling
    """
    return _request("POST", "/videos/from-templates", {
        "templateId": template_id,
        "prompt": prompt,
        "inputs": inputs or {},
    })


def get_visual_status(creation_id):
    """Poll for visual generation status."""
    return _request("GET", f"/videos/creations/{creation_id}")


def wait_for_visual(creation_id, timeout=300, interval=5):
    """Poll until visual reaches terminal state."""
    start = time.time()
    while time.time() - start < timeout:
        result = get_visual_status(creation_id)
        status = result.get("status", "")

        if status == "done":
            return result
        if status == "creation-from-template-failed":
            return {"status": "failed", "error": result.get("errorMessage", "Unknown")}

        time.sleep(interval)

    return {"status": "timeout"}


if __name__ == "__main__":
    # Quick connectivity test
    print("Testing Blotato API connection...")
    try:
        accounts = get_accounts()
        print(f"Connected! Found {len(accounts) if isinstance(accounts, list) else 1} account(s)")
        for acc in (accounts if isinstance(accounts, list) else [accounts]):
            print(f"  - {acc.get('fullname', 'Unknown')} ({acc.get('platform', 'unknown')})")
    except Exception as e:
        print(f"Connection failed: {e}")
