"""
blotato_bridge.py
-----------------
Thin bridge between the web app backend (server.py) and the existing
Blotato publisher skill (.agent/skills/blotato_publisher/).

Exposes high-level functions for:
  - Publishing a draft (immediate or scheduled)
  - Scoring a post via the quality gate
  - Getting schedule info (next optimal slot, conflicts)
  - Testing API connectivity
  - Uploading media
"""

import os
import sys
from pathlib import Path

# Add the skills directory to sys.path so we can import the Blotato publisher
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SKILLS_DIR = _PROJECT_ROOT / ".agent" / "skills"
if str(_SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILLS_DIR))

from blotato_publisher import api_client
from blotato_publisher.quality_gate import score_post, format_scorecard
from blotato_publisher.schedule_ledger import (
    get_next_optimal_slot, check_conflicts, add_scheduled_post,
    get_upcoming_posts, get_recent_posts,
)
from blotato_publisher.media_handler import upload_for_publishing


def test_connection():
    """Test Blotato API connectivity. Returns account info or raises."""
    accounts = api_client.get_accounts()
    li = api_client.get_linkedin_account()
    return {
        "connected": True,
        "accounts": accounts if isinstance(accounts, list) else [accounts],
        "linkedin": li,
    }


def get_quality_score(caption, has_image=False):
    """Score a caption against the 7-dimension quality gate.
    Returns dict with scores, total, passed, feedback."""
    return score_post(caption, has_image=has_image, scheduled_optimal=True)


def get_schedule_info():
    """Get upcoming schedule + next optimal slot."""
    next_slot = get_next_optimal_slot()
    upcoming = get_upcoming_posts()
    recent = get_recent_posts(days=14)
    return {
        "next_optimal_slot": next_slot,
        "upcoming": upcoming,
        "recent": recent,
    }


def upload_media(asset_url, method="blotato"):
    """Upload a local image or URL for Blotato publishing.
    
    Args:
        asset_url: Local file path or public URL.
        method: 'blotato', 'imgbb', or 'url'
    
    Returns:
        Public URL string ready for Blotato's mediaUrls.
    """
    # If it's already a public URL (https://...), pass through
    if asset_url.startswith("http://") or asset_url.startswith("https://"):
        if method == "url":
            return asset_url
        # Upload the URL to Blotato's servers
        result = api_client.upload_media(asset_url)
        return result.get("url", asset_url)
    
    # Local file path — convert /assets/ URL to .tmp/ path if needed
    local_path = asset_url
    if "/assets/" in local_path:
        local_path = local_path.replace("/assets/", str(_PROJECT_ROOT / ".tmp") + "/")
        if "?" in local_path:
            local_path = local_path.split("?")[0]
    
    return upload_for_publishing(local_path, method=method)


def publish_draft(caption, asset_url=None, scheduled_time=None, force=False):
    """Publish a draft to LinkedIn via Blotato.
    
    Args:
        caption: Post text content.
        asset_url: Optional image/video URL (local path or public URL).
        scheduled_time: ISO 8601 timestamp for scheduling (None = immediate).
        force: If True, bypass quality gate.
    
    Returns:
        dict with status, submission_id, public_url, quality_score, etc.
    """
    has_image = bool(asset_url)
    
    # Run quality gate
    quality = score_post(caption, has_image=has_image, scheduled_optimal=bool(scheduled_time))
    
    if not quality["passed"] and not force:
        return {
            "status": "blocked",
            "reason": "quality_gate",
            "quality_score": quality["total"],
            "threshold": quality["threshold"],
            "feedback": quality["feedback"],
            "scores": quality["scores"],
        }
    
    # Check scheduling conflicts
    if scheduled_time:
        conflict = check_conflicts(scheduled_time)
        if not conflict["clear"] and not force:
            return {
                "status": "blocked",
                "reason": "schedule_conflict",
                "conflict": conflict,
            }
    
    # Upload media if provided
    media_urls = []
    if asset_url:
        try:
            public_url = upload_media(asset_url)
            media_urls.append(public_url)
        except Exception as e:
            if not force:
                return {"status": "error", "reason": f"Media upload failed: {e}"}
            print(f"[Blotato] Media upload failed (forced): {e}")
    
    # Get LinkedIn account
    li = api_client.get_linkedin_account()
    account_id = li["account_id"]
    
    # Publish
    response = api_client.publish_post(
        account_id=account_id,
        text=caption,
        platform="linkedin",
        media_urls=media_urls if media_urls else None,
        scheduled_time=scheduled_time,
    )
    
    submission_id = response.get("postSubmissionId", response.get("id", ""))
    
    # Poll for status
    result = api_client.wait_for_post(submission_id, timeout=60)
    status = result.get("status", "unknown")
    public_url = result.get("publicUrl", "")
    
    # Update schedule ledger
    if status in ("published", "scheduled"):
        title = caption.split("\n")[0][:60]
        add_scheduled_post(
            title=title,
            text=caption,
            scheduled_time=scheduled_time or "",
            media_path=asset_url,
            platform="linkedin",
            blotato_id=submission_id,
        )
    
    return {
        "status": status,
        "submission_id": submission_id,
        "public_url": public_url,
        "quality_score": quality["total"],
        "quality_passed": quality["passed"],
        "error": result.get("errorMessage", ""),
    }
