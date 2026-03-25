"""
crm_db.py
---------
Supabase CRUD for the rebuilt Voice Engine + CRM Hub tables:
  - linkedin_profiles
  - conversations
  - crm_contacts

All functions use the service-role client for background tasks.
Structured logging with [CRM_DB] prefix throughout.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

_supabase = None


def _get_client():
    """Return cached Supabase client (service-role for background ops)."""
    global _supabase
    if _supabase is not None:
        return _supabase
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if url and key:
            _supabase = create_client(url, key)
            return _supabase
    except Exception as e:
        print(f"[CRM_DB] Failed to create Supabase client: {e}")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# linkedin_profiles CRUD
# ═══════════════════════════════════════════════════════════════════════════════

def upsert_profile(
    user_id: str,
    linkedin_url: str,
    raw_json: Dict = None,
    summary: Dict = None,
    is_owner: bool = False,
    **extra_fields,
) -> Optional[Dict]:
    """Insert or update a LinkedIn profile.

    Uses ON CONFLICT (user_id, linkedin_url) to upsert.
    Returns the upserted record or None on failure.
    """
    sb = _get_client()
    if not sb:
        print("[CRM_DB] No Supabase client — cannot upsert profile")
        return None

    data = {
        "user_id": user_id,
        "linkedin_url": (linkedin_url or "").strip().rstrip("/").lower(),
        "is_owner": is_owner,
    }
    if raw_json:
        data["raw_json"] = raw_json
        # Extract identity fields from raw Apify data
        data["first_name"] = str(raw_json.get("firstName") or raw_json.get("first_name") or "").strip()
        data["last_name"] = str(raw_json.get("lastName") or raw_json.get("last_name") or "").strip()
        data["title"] = str(
            raw_json.get("headline") or raw_json.get("jobTitle") or raw_json.get("title") or ""
        ).strip()
        data["company"] = str(
            raw_json.get("currentCompany") or raw_json.get("company") or ""
        ).strip()
        data["industry"] = str(raw_json.get("industry") or "").strip()
        data["location"] = str(
            raw_json.get("location") or raw_json.get("addressLocality") or ""
        ).strip()
        data["headline"] = str(raw_json.get("headline") or "").strip()
        data["profile_pic_url"] = str(raw_json.get("profilePicture") or raw_json.get("photo") or "").strip()
        # Years of experience
        experiences = raw_json.get("experiences") or raw_json.get("positions") or []
        data["years_of_experience"] = len(experiences) if isinstance(experiences, list) else 0
    if summary:
        data["summary"] = summary

    # Merge any extra fields (first_name, last_name overrides from connections)
    for k, v in extra_fields.items():
        if k in ("first_name", "last_name", "title", "company", "industry", "location",
                  "headline", "profile_pic_url", "years_of_experience"):
            if v:
                data[k] = v

    try:
        res = sb.table("linkedin_profiles").upsert(
            data,
            on_conflict="user_id,linkedin_url",
        ).execute()
        rows = res.data if hasattr(res, "data") else []
        if rows:
            print(f"[CRM_DB] Upserted profile: {data.get('linkedin_url', '?')[:60]}")
            return rows[0]
        return None
    except Exception as e:
        print(f"[CRM_DB] upsert_profile error: {e}")
        return None


def get_profile_by_url(user_id: str, linkedin_url: str) -> Optional[Dict]:
    """Fetch a profile by user_id + linkedin_url (dedup check)."""
    sb = _get_client()
    if not sb:
        return None
    normalized = (linkedin_url or "").strip().rstrip("/").lower()
    if not normalized:
        return None
    try:
        res = sb.table("linkedin_profiles").select("*").eq(
            "user_id", user_id
        ).eq("linkedin_url", normalized).limit(1).execute()
        rows = res.data if hasattr(res, "data") else []
        return rows[0] if rows else None
    except Exception as e:
        print(f"[CRM_DB] get_profile_by_url error: {e}")
        return None


def get_owner_profile(user_id: str) -> Optional[Dict]:
    """Fetch the user's own profile (is_owner=True), preferring the one with richest data."""
    sb = _get_client()
    if not sb:
        return None
    try:
        res = sb.table("linkedin_profiles").select("*").eq(
            "user_id", user_id
        ).eq("is_owner", True).order("updated_at", desc=True).limit(5).execute()
        rows = res.data if hasattr(res, "data") else []
        if not rows:
            return None
        # Prefer the profile with actual raw data over empty stubs
        for row in rows:
            raw = row.get("raw_json")
            if raw and isinstance(raw, dict) and len(raw) > 2:
                return row
        return rows[0]
    except Exception as e:
        print(f"[CRM_DB] get_owner_profile error: {e}")
        return None


def get_profile_by_id(profile_id: str) -> Optional[Dict]:
    """Fetch a profile by its UUID."""
    sb = _get_client()
    if not sb:
        return None
    try:
        res = sb.table("linkedin_profiles").select("*").eq("id", profile_id).limit(1).execute()
        rows = res.data if hasattr(res, "data") else []
        return rows[0] if rows else None
    except Exception as e:
        print(f"[CRM_DB] get_profile_by_id error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# conversations CRUD
# ═══════════════════════════════════════════════════════════════════════════════

def upsert_conversation(
    user_id: str,
    conversation_id: str,
    contact_profile_id: Optional[str] = None,
    thread: List[Dict] = None,
) -> Optional[Dict]:
    """Insert or update a conversation thread.

    Uses ON CONFLICT (user_id, conversation_id) to upsert.
    Computes message_count, first_message_date, last_message_date from thread.
    """
    sb = _get_client()
    if not sb:
        return None

    thread = thread or []
    # Compute stats
    dates = []
    for msg in thread:
        d = msg.get("date")
        if d:
            dates.append(d)
    dates.sort()

    data = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "thread": thread,
        "message_count": len(thread),
        "first_message_date": dates[0] if dates else None,
        "last_message_date": dates[-1] if dates else None,
    }
    if contact_profile_id:
        data["contact_profile_id"] = contact_profile_id

    try:
        res = sb.table("conversations").upsert(
            data,
            on_conflict="user_id,conversation_id",
        ).execute()
        rows = res.data if hasattr(res, "data") else []
        if rows:
            return rows[0]
        return None
    except Exception as e:
        print(f"[CRM_DB] upsert_conversation error: {e}")
        return None


def get_conversation(user_id: str, conversation_id: str) -> Optional[Dict]:
    """Fetch a conversation by its LinkedIn Conversation ID."""
    sb = _get_client()
    if not sb:
        return None
    try:
        res = sb.table("conversations").select("*").eq(
            "user_id", user_id
        ).eq("conversation_id", conversation_id).limit(1).execute()
        rows = res.data if hasattr(res, "data") else []
        return rows[0] if rows else None
    except Exception as e:
        print(f"[CRM_DB] get_conversation error: {e}")
        return None


def get_conversation_by_id(conv_uuid: str) -> Optional[Dict]:
    """Fetch a conversation by its UUID (for Full View)."""
    sb = _get_client()
    if not sb:
        return None
    try:
        res = sb.table("conversations").select("*").eq("id", conv_uuid).limit(1).execute()
        rows = res.data if hasattr(res, "data") else []
        return rows[0] if rows else None
    except Exception as e:
        print(f"[CRM_DB] get_conversation_by_id error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# crm_contacts CRUD
# ═══════════════════════════════════════════════════════════════════════════════

def upsert_crm_contact(
    user_id: str,
    profile_id: str,
    conversation_id: Optional[str] = None,
    analysis: Dict = None,
    source: str = "message",
    linkedin_url: str = "",
    linkedin_conversation_id: str = "",
    connected_on: str = "",
) -> Optional[Dict]:
    """Insert or update a CRM contact.

    Uses ON CONFLICT (user_id, profile_id) to upsert.
    analysis dict should match the LLM output schema.
    """
    sb = _get_client()
    if not sb:
        return None

    a = analysis or {}
    data = {
        "user_id": user_id,
        "profile_id": profile_id,
        "first_name": str(a.get("first_name", "")).strip(),
        "last_name": str(a.get("last_name", "")).strip(),
        "title": str(a.get("title", "")).strip(),
        "company": str(a.get("company", "")).strip(),
        "industry": str(a.get("industry", "")).strip(),
        "years_of_experience": int(a.get("years_of_experience", 0)),
        "intent_points": a.get("intent_points", []),
        "score": max(0, min(100, int(a.get("score", 0)))),
        "tag": a.get("tag", "prospect"),
        "source": source,
        "linkedin_url": linkedin_url,
        "linkedin_conversation_id": linkedin_conversation_id,
        "connected_on": connected_on,
    }
    if conversation_id:
        data["conversation_id"] = conversation_id

    try:
        res = sb.table("crm_contacts").upsert(
            data,
            on_conflict="user_id,profile_id",
        ).execute()
        rows = res.data if hasattr(res, "data") else []
        return rows[0] if rows else None
    except Exception as e:
        print(f"[CRM_DB] upsert_crm_contact error: {e}")
        return None


def get_crm_contacts(
    user_id: str,
    tag_filter: Optional[str] = None,
    min_score: int = 0,
    max_total: int = 5000,
) -> List[Dict]:
    """Fetch CRM contacts with optional filters. Paginated internally."""
    sb = _get_client()
    if not sb:
        return []

    PAGE_SIZE = 500
    all_rows = []
    offset = 0

    try:
        while len(all_rows) < max_total:
            q = sb.table("crm_contacts").select("*").eq("user_id", user_id)
            if tag_filter:
                q = q.eq("tag", tag_filter)
            if min_score > 0:
                q = q.gte("score", min_score)
            q = q.order("score", desc=True).range(offset, offset + PAGE_SIZE - 1)

            res = q.execute()
            rows = res.data if hasattr(res, "data") else []
            all_rows.extend(rows)

            if len(rows) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

        return all_rows[:max_total]
    except Exception as e:
        print(f"[CRM_DB] get_crm_contacts error: {e}")
        return []


def get_crm_contact_count(user_id: str) -> int:
    """Fast count of CRM contacts for a user."""
    sb = _get_client()
    if not sb:
        return 0
    try:
        res = sb.table("crm_contacts").select("id", count="exact").eq("user_id", user_id).execute()
        return res.count if hasattr(res, "count") and res.count else 0
    except Exception as e:
        print(f"[CRM_DB] get_crm_contact_count error: {e}")
        return 0


def get_crm_contact_full(contact_id: str) -> Optional[Dict]:
    """Fetch a single CRM contact with its profile + conversation data joined."""
    sb = _get_client()
    if not sb:
        return None
    try:
        # Get the contact
        res = sb.table("crm_contacts").select("*").eq("id", contact_id).limit(1).execute()
        rows = res.data if hasattr(res, "data") else []
        if not rows:
            return None
        contact = rows[0]

        # Join profile
        if contact.get("profile_id"):
            profile = get_profile_by_id(contact["profile_id"])
            contact["profile"] = profile or {}
        else:
            contact["profile"] = {}

        # Join conversation
        if contact.get("conversation_id"):
            conv = get_conversation_by_id(contact["conversation_id"])
            contact["conversation"] = conv or {}
        else:
            contact["conversation"] = {}

        return contact
    except Exception as e:
        print(f"[CRM_DB] get_crm_contact_full error: {e}")
        return None


def save_draft_message(contact_id: str, message: str) -> bool:
    """Save a draft message for a CRM contact."""
    sb = _get_client()
    if not sb:
        return False
    try:
        sb.table("crm_contacts").update({
            "draft_message": message,
            "draft_is_sent": False,
        }).eq("id", contact_id).execute()
        return True
    except Exception as e:
        print(f"[CRM_DB] save_draft_message error: {e}")
        return False


def mark_draft_sent(contact_id: str) -> bool:
    """Mark a draft as sent (excluded from future analysis)."""
    sb = _get_client()
    if not sb:
        return False
    try:
        sb.table("crm_contacts").update({
            "draft_is_sent": True,
        }).eq("id", contact_id).execute()
        return True
    except Exception as e:
        print(f"[CRM_DB] mark_draft_sent error: {e}")
        return False


def delete_crm_contact(contact_id: str) -> bool:
    """Delete a CRM contact by ID."""
    sb = _get_client()
    if not sb:
        return False
    try:
        sb.table("crm_contacts").delete().eq("id", contact_id).execute()
        return True
    except Exception as e:
        print(f"[CRM_DB] delete_crm_contact error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Bulk operations
# ═══════════════════════════════════════════════════════════════════════════════

def wipe_user_crm_data(user_id: str) -> Dict[str, int]:
    """Wipe all CRM data for a user (fresh rebuild on re-upload).

    Deletes from: crm_contacts, conversations, linkedin_profiles (non-owner).
    Preserves the user's own profile (is_owner=True).

    Returns counts of deleted rows per table.
    """
    sb = _get_client()
    if not sb:
        return {"crm_contacts": 0, "conversations": 0, "linkedin_profiles": 0}

    counts = {}
    try:
        # 1. Delete CRM contacts
        res = sb.table("crm_contacts").delete().eq("user_id", user_id).execute()
        counts["crm_contacts"] = len(res.data) if hasattr(res, "data") else 0
    except Exception as e:
        print(f"[CRM_DB] wipe crm_contacts error: {e}")
        counts["crm_contacts"] = 0

    try:
        # 2. Delete conversations
        res = sb.table("conversations").delete().eq("user_id", user_id).execute()
        counts["conversations"] = len(res.data) if hasattr(res, "data") else 0
    except Exception as e:
        print(f"[CRM_DB] wipe conversations error: {e}")
        counts["conversations"] = 0

    try:
        # 3. Delete non-owner profiles (keep the user's own profile)
        res = sb.table("linkedin_profiles").delete().eq(
            "user_id", user_id
        ).eq("is_owner", False).execute()
        counts["linkedin_profiles"] = len(res.data) if hasattr(res, "data") else 0
    except Exception as e:
        print(f"[CRM_DB] wipe linkedin_profiles error: {e}")
        counts["linkedin_profiles"] = 0

    print(f"[CRM_DB] Wiped user {user_id[:8]}... data: {counts}")
    return counts


def update_processing_status(user_id: str, status: str, crm_count: int = 0, phase: str = "") -> bool:
    """Update processing status in user_profiles table (for frontend polling)."""
    sb = _get_client()
    if not sb:
        return False
    try:
        # Try to get existing profile_data
        res = sb.table("user_profiles").select("profile_data").eq("user_id", user_id).limit(1).execute()
        rows = res.data if hasattr(res, "data") else []
        profile_data = rows[0].get("profile_data", {}) if rows else {}
        if isinstance(profile_data, str):
            try:
                profile_data = json.loads(profile_data)
            except:
                profile_data = {}

        profile_data["linkedin_processing_status"] = status
        profile_data["crm_contacts_count"] = crm_count
        if phase:
            profile_data["processing_phase"] = phase
        if status == "completed":
            profile_data["linkedin_imported"] = True

        if rows:
            sb.table("user_profiles").update({"profile_data": profile_data}).eq("user_id", user_id).execute()
        else:
            sb.table("user_profiles").insert({"user_id": user_id, "profile_data": profile_data}).execute()

        return True
    except Exception as e:
        print(f"[CRM_DB] update_processing_status error: {e}")
        return False
