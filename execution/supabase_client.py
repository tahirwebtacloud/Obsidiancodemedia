"""
supabase_client.py
------------------
Drop-in replacement for firestore_client.py using Supabase (PostgreSQL).
Provides the same public API: add_history_entry, get_user_history,
get_all_settings, update_settings, etc.
Falls back to local JSON files if Supabase is unreachable.
"""

import os
import json
import uuid
import threading
from dotenv import load_dotenv

load_dotenv()

_supabase = None

# ─── Per-request RLS context ─────────────────────────────────────────────────
# When an HTTP request sets a user JWT via set_request_token(), _get_client()
# returns an RLS-aware client (anon key + user JWT).  Background tasks and CLI
# scripts that never call set_request_token() get the service-role client.
_request_context = threading.local()


def set_request_token(token: str):
    """Store the current request's Supabase access token (called by middleware)."""
    _request_context.access_token = token


def clear_request_token():
    """Clear the per-request token after the response is sent."""
    _request_context.access_token = None


def _parse_json_field(value):
    """Parse a JSON string field from Supabase into a Python object."""
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


# Absolute path anchored to project root so all scripts resolve to the same file
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_SETTINGS_FILE = os.path.join(_PROJECT_ROOT, ".local_settings.json")


def _get_client():
    """Return a Supabase client.

    If a per-request user JWT is available (set via middleware), returns an
    RLS-aware client created with the anon key + user Bearer token.  Otherwise
    falls back to the cached service-role client (for background tasks, CLI
    scripts, etc.).
    """
    token = getattr(_request_context, "access_token", None)
    if token:
        return _get_user_client(token)
    return _get_service_client()


def _get_service_client():
    """Return the singleton service-role client (bypasses RLS)."""
    global _supabase
    if _supabase is not None:
        return _supabase

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        raise Exception(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env. "
            "Get these from Supabase Dashboard → Project Settings → API."
        )

    from supabase import create_client
    _supabase = create_client(url, key)
    print(f"[Supabase] Service-role client connected to {url}")
    return _supabase


_user_client_cache: dict = {}  # {token_hash: (client, expiry_ts)}
_USER_CLIENT_CACHE_TTL = 300  # 5 minutes — matches server.py auth cache TTL
_USER_CLIENT_CACHE_MAX = 50   # Max cached clients to prevent memory bloat

def _get_user_client(access_token: str):
    """Return an RLS-aware client using the user's JWT, with caching.

    Caches clients by token hash for 5 minutes to avoid creating a new
    Supabase client (~200-400ms) on every single request.
    Falls back to the service-role client when SUPABASE_ANON_KEY is not
    configured (backward-compatible).
    """
    import hashlib, time as _time

    url = os.getenv("SUPABASE_URL", "")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "")

    if not url or not anon_key:
        return _get_service_client()

    # Check cache
    token_hash = hashlib.sha256(access_token.encode()).hexdigest()[:16]
    cached = _user_client_cache.get(token_hash)
    if cached and cached[1] > _time.time():
        return cached[0]

    from supabase import create_client, ClientOptions
    options = ClientOptions(
        headers={"Authorization": f"Bearer {access_token}"}
    )
    client = create_client(url, anon_key, options)

    # Store in cache
    _user_client_cache[token_hash] = (client, _time.time() + _USER_CLIENT_CACHE_TTL)

    # Prune expired entries if cache grows too large
    if len(_user_client_cache) > _USER_CLIENT_CACHE_MAX:
        cutoff = _time.time()
        expired = [k for k, v in _user_client_cache.items() if v[1] < cutoff]
        for k in expired:
            del _user_client_cache[k]

    return client


# ─────────────────────────────────────────────────────────────
# Local file fallback helpers (same as original firestore_client)
# ─────────────────────────────────────────────────────────────

def _read_local_settings(uid: str = "default") -> dict:
    if os.path.exists(LOCAL_SETTINGS_FILE):
        try:
            with open(LOCAL_SETTINGS_FILE, "r") as f:
                all_data = json.load(f)
            if all_data and not any(isinstance(v, dict) for v in all_data.values()):
                return all_data if uid == "default" else {}
            return all_data.get(uid, {})
        except Exception:
            return {}
    return {}


def _write_local_settings(data: dict, uid: str = "default"):
    all_data = {}
    if os.path.exists(LOCAL_SETTINGS_FILE):
        try:
            with open(LOCAL_SETTINGS_FILE, "r") as f:
                all_data = json.load(f)
            if all_data and not any(isinstance(v, dict) for v in all_data.values()):
                all_data = {"default": all_data}
        except Exception:
            all_data = {}
    if uid not in all_data:
        all_data[uid] = {}
    all_data[uid].update(data)
    with open(LOCAL_SETTINGS_FILE, "w") as f:
        json.dump(all_data, f, indent=2)


# ─────────────────────────────────────────────────────────────
# Public API — History
# ─────────────────────────────────────────────────────────────

def add_history_entry(entry: dict, uid: str = "default"):
    """Write a history entry to Supabase and local cache."""
    safe_uid = uid.strip() if uid else "default"

    # Always save to local cache first (fast, reliable)
    _save_history_local(entry, safe_uid)

    if safe_uid == "default":
        return

    try:
        client = _get_client()
        row = {
            "id": entry.get("id", ""),
            "user_id": safe_uid,
            "timestamp": entry.get("timestamp", 0),
            "type": entry.get("type", "generate"),
            "status": entry.get("status", "success"),
            "input_summary": entry.get("input_summary", ""),
            "topic": entry.get("topic", ""),
            "purpose": entry.get("purpose", ""),
            "style": entry.get("style", ""),
            "params": json.dumps(entry.get("params", {})) if isinstance(entry.get("params"), dict) else "{}",
            "caption": entry.get("caption", ""),
            "full_caption": entry.get("full_caption", entry.get("caption", "")),
            "asset_url": entry.get("asset_url", ""),
            "final_image_prompt": entry.get("final_image_prompt", ""),
            "full_results": json.dumps(entry.get("full_results")) if entry.get("full_results") else None,
            "error_message": entry.get("error_message", ""),
            "costs": json.dumps(entry.get("costs", [])) if isinstance(entry.get("costs"), list) else "[]",
            "total_cost": entry.get("total_cost", 0.0),
            "duration_ms": entry.get("duration_ms", 0),
            "approved": entry.get("approved", False),
        }
        client.table("history").upsert(row).execute()
    except Exception as e:
        print(f"[Supabase] add_history_entry error uid='{safe_uid}'. Saved locally. Error: {e}")


def get_user_history(uid: str = "default") -> list:
    """Read history from Supabase. Fallback to local."""
    safe_uid = uid.strip() if uid else "default"

    if safe_uid != "default":
        try:
            client = _get_client()
            result = (
                client.table("history")
                .select("*")
                .eq("user_id", safe_uid)
                .order("timestamp", desc=True)
                .limit(100)
                .execute()
            )
            if result.data:
                # Parse JSON string fields back to dicts/lists
                history = []
                for row in result.data:
                    entry = dict(row)
                    for json_field in ("params", "costs", "full_results"):
                        if isinstance(entry.get(json_field), str):
                            try:
                                entry[json_field] = json.loads(entry[json_field])
                            except Exception:
                                pass
                    history.append(entry)
                return history
        except Exception as e:
            print(f"[Supabase] get_user_history error uid='{safe_uid}'. Falling back to local. Error: {e}")

    # Local fallback
    history_file = f".tmp/history_{safe_uid}.json" if safe_uid != "default" else "history.json"
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_history_local(entry: dict, safe_uid: str):
    """Save history entry to local JSON file."""
    os.makedirs(".tmp", exist_ok=True)
    history_file = f".tmp/history_{safe_uid}.json" if safe_uid != "default" else "history.json"
    history_data = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except Exception:
            pass
    history_data = [d for d in history_data if isinstance(d, dict) and d.get("id") != entry.get("id")]
    history_data.insert(0, entry)
    history_data = history_data[:500]
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=4, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────
# Public API — Settings
# ─────────────────────────────────────────────────────────────

def get_all_settings(uid: str = "default") -> dict:
    """Return settings for a user from Supabase."""
    safe_uid = uid.strip() if uid else "default"

    if safe_uid != "default":
        try:
            client = _get_client()
            result = client.table("user_settings").select("*").eq("user_id", safe_uid).execute()
            if result.data and len(result.data) > 0:
                row = result.data[0]
                settings = row.get("settings", {})
                if isinstance(settings, str):
                    settings = json.loads(settings)
                # Merge top-level fields
                settings["trackedProfileUrl"] = row.get("tracked_profile_url", "")
                return settings
        except Exception as e:
            print(f"[Supabase] get_all_settings error uid='{safe_uid}'. Falling back to local. Error: {e}")

    return _read_local_settings(uid=safe_uid)


def update_settings(data: dict, uid: str = "default") -> bool:
    """Upsert settings for a user into Supabase."""
    safe_uid = uid.strip() if uid else "default"
    _write_local_settings(data, uid=safe_uid)

    if safe_uid == "default":
        return True

    try:
        client = _get_client()
        row = {
            "user_id": safe_uid,
            "tracked_profile_url": data.get("trackedProfileUrl", ""),
            "settings": json.dumps(data),
        }
        client.table("user_settings").upsert(row).execute()
        return True
    except Exception as e:
        print(f"[Supabase] update_settings error uid='{safe_uid}'. Saved locally. Error: {e}")
        return True


# ─────────────────────────────────────────────────────────────
# Public API — Drafts
# ─────────────────────────────────────────────────────────────

def save_draft(data: dict, uid: str = "default") -> dict:
    """Insert a new draft into Supabase and local cache. Returns the saved draft dict."""
    safe_uid = uid.strip() if uid else "default"

    draft = {
        "id": data.get("id", ""),
        "user_id": safe_uid,
        "caption": data.get("caption", ""),
        "asset_url": data.get("asset_url", ""),
        "final_image_prompt": data.get("final_image_prompt", ""),
        "type": data.get("type", "text"),
        "purpose": data.get("purpose", ""),
        "topic": data.get("topic", ""),
        "status": data.get("status", "draft"),
        "scheduled_at": data.get("scheduled_at"),
        "published_at": data.get("published_at"),
        "blotato_post_id": data.get("blotato_post_id"),
        "source_data": data.get("source_data", {}),
        "carousel_layout": data.get("carousel_layout"),
        "quality_score": data.get("quality_score", 0),
    }

    _save_draft_local(draft, safe_uid)

    if safe_uid == "default":
        return draft

    try:
        client = _get_client()
        row = dict(draft)
        if isinstance(row.get("source_data"), dict):
            row["source_data"] = json.dumps(row["source_data"])
        if isinstance(row.get("carousel_layout"), (dict, list)):
            row["carousel_layout"] = json.dumps(row["carousel_layout"])
        client.table("drafts").upsert(row).execute()
    except Exception as e:
        print(f"[Supabase] save_draft error uid='{safe_uid}'. Saved locally. Error: {e}")

    return draft


def get_user_drafts(uid: str = "default", status_filter: str = None) -> list:
    """Read drafts from Supabase. Fallback to local."""
    safe_uid = uid.strip() if uid else "default"

    if safe_uid != "default":
        try:
            client = _get_client()
            query = (
                client.table("drafts")
                .select("*")
                .eq("user_id", safe_uid)
            )
            if status_filter:
                query = query.eq("status", status_filter)
            result = query.order("created_at", desc=True).limit(200).execute()
            if result.data is not None:
                drafts = []
                for row in result.data:
                    entry = dict(row)
                    for json_field in ("source_data", "carousel_layout"):
                        if isinstance(entry.get(json_field), str):
                            try:
                                entry[json_field] = json.loads(entry[json_field])
                            except Exception:
                                pass
                    drafts.append(entry)
                return drafts
        except Exception as e:
            print(f"[Supabase] get_user_drafts error uid='{safe_uid}'. Falling back to local. Error: {e}")

    return _load_drafts_local(safe_uid, status_filter)


def update_draft(draft_id: str, data: dict, uid: str = "default") -> bool:
    """Partial update of a draft. Only provided keys are updated."""
    safe_uid = uid.strip() if uid else "default"

    _update_draft_local(draft_id, data, safe_uid)

    if safe_uid == "default":
        return True

    try:
        client = _get_client()
        row = {}
        allowed_fields = [
            "caption", "asset_url", "final_image_prompt", "type", "purpose",
            "topic", "status", "scheduled_at", "published_at",
            "blotato_post_id", "source_data", "carousel_layout", "quality_score",
        ]
        for key in allowed_fields:
            if key in data:
                val = data[key]
                if key in ("source_data", "carousel_layout") and isinstance(val, (dict, list)):
                    val = json.dumps(val)
                row[key] = val
        if row:
            client.table("drafts").update(row).eq("id", draft_id).eq("user_id", safe_uid).execute()
        return True
    except Exception as e:
        print(f"[Supabase] update_draft error uid='{safe_uid}'. Saved locally. Error: {e}")
        return True


def delete_draft(draft_id: str, uid: str = "default") -> bool:
    """Delete a draft by ID."""
    safe_uid = uid.strip() if uid else "default"

    _delete_draft_local(draft_id, safe_uid)

    if safe_uid == "default":
        return True

    try:
        client = _get_client()
        client.table("drafts").delete().eq("id", draft_id).eq("user_id", safe_uid).execute()
        return True
    except Exception as e:
        print(f"[Supabase] delete_draft error uid='{safe_uid}'. Deleted locally. Error: {e}")
        return True


# ─────────────────────────────────────────────────────────────
# Drafts — Local file fallback helpers
# ─────────────────────────────────────────────────────────────

def _drafts_file(safe_uid: str) -> str:
    os.makedirs(".tmp", exist_ok=True)
    return f".tmp/drafts_{safe_uid}.json"


def _load_all_drafts_local(safe_uid: str) -> list:
    path = _drafts_file(safe_uid)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _write_all_drafts_local(drafts: list, safe_uid: str):
    path = _drafts_file(safe_uid)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(drafts, f, indent=2, ensure_ascii=False, default=str)


def _save_draft_local(draft: dict, safe_uid: str):
    drafts = _load_all_drafts_local(safe_uid)
    drafts = [d for d in drafts if d.get("id") != draft.get("id")]
    drafts.insert(0, draft)
    _write_all_drafts_local(drafts, safe_uid)


def _load_drafts_local(safe_uid: str, status_filter: str = None) -> list:
    drafts = _load_all_drafts_local(safe_uid)
    if status_filter:
        drafts = [d for d in drafts if d.get("status") == status_filter]
    return drafts


def _update_draft_local(draft_id: str, data: dict, safe_uid: str):
    drafts = _load_all_drafts_local(safe_uid)
    for d in drafts:
        if d.get("id") == draft_id:
            d.update(data)
            break
    _write_all_drafts_local(drafts, safe_uid)


def _delete_draft_local(draft_id: str, safe_uid: str):
    drafts = _load_all_drafts_local(safe_uid)
    drafts = [d for d in drafts if d.get("id") != draft_id]
    _write_all_drafts_local(drafts, safe_uid)


# ─────────────────────────────────────────────────────────────
# Public API — Brand Assets
# ─────────────────────────────────────────────────────────────

def update_user_brand(brand_assets: dict, uid: str = "default") -> bool:
    """Update brand assets for a user in Supabase."""
    safe_uid = uid.strip() if uid else "default"
    
    # Save locally first
    _write_local_brand(brand_assets, safe_uid)
    
    if safe_uid == "default":
        return True
    
    try:
        client = _get_client()
        ps = brand_assets.get("products_services", [])
        row = {
            "user_id": safe_uid,
            "brand_name": brand_assets.get("brand_name", ""),
            "primary_color": brand_assets.get("primary_color", "#F9C74F"),
            "secondary_color": brand_assets.get("secondary_color", "#0E0E0E"),
            "accent_color": brand_assets.get("accent_color", "#FCF0D5"),
            "font_family": brand_assets.get("font_family", "Inter"),
            "logo_url": brand_assets.get("logo_url", ""),
            "visual_style": brand_assets.get("visual_style", ""),
            "tone_of_voice": brand_assets.get("tone_of_voice", ""),
            "tagline": brand_assets.get("tagline", ""),
            "description": brand_assets.get("description", ""),
            "products_services": json.dumps(ps) if isinstance(ps, list) else (ps or "[]"),
            "ui_theme": json.dumps(brand_assets.get("ui_theme", {})) if isinstance(brand_assets.get("ui_theme"), dict) else (brand_assets.get("ui_theme") or "{}"),
        }
        client.table("user_brands").upsert(row).execute()
        return True
    except Exception as e:
        print(f"[Supabase] update_user_brand error uid='{safe_uid}'. Saved locally. Error: {e}")
        return True


def get_user_brand(uid: str = "default") -> dict:
    """Get brand assets for a user from Supabase. Fallback to local."""
    safe_uid = uid.strip() if uid else "default"
    
    if safe_uid != "default":
        try:
            client = _get_client()
            result = client.table("user_brands").select("*").eq("user_id", safe_uid).single().execute()
            if result.data:
                ps_raw = result.data.get("products_services", [])
                if isinstance(ps_raw, str):
                    try:
                        ps_raw = json.loads(ps_raw)
                    except Exception:
                        ps_raw = []
                return {
                    "brand_name": result.data.get("brand_name", ""),
                    "primary_color": result.data.get("primary_color", "#F9C74F"),
                    "secondary_color": result.data.get("secondary_color", "#0E0E0E"),
                    "accent_color": result.data.get("accent_color", "#FCF0D5"),
                    "font_family": result.data.get("font_family", "Inter"),
                    "logo_url": result.data.get("logo_url", ""),
                    "visual_style": result.data.get("visual_style", ""),
                    "tone_of_voice": result.data.get("tone_of_voice", ""),
                    "tagline": result.data.get("tagline", ""),
                    "description": result.data.get("description", ""),
                    "products_services": ps_raw or [],
                    "ui_theme": _parse_json_field(result.data.get("ui_theme", {})),
                }
        except Exception as e:
            err = str(e)
            if "PGRST116" in err:
                return _read_local_brand(safe_uid)
            print(f"[Supabase] get_user_brand error uid='{safe_uid}'. Falling back to local. Error: {e}")
    
    return _read_local_brand(safe_uid)


def _write_local_brand(data: dict, uid: str = "default"):
    """Write brand assets to local file."""
    all_data = {}
    brand_file = os.path.join(_PROJECT_ROOT, ".local_brands.json")
    
    if os.path.exists(brand_file):
        try:
            with open(brand_file, "r") as f:
                all_data = json.load(f)
        except Exception:
            all_data = {}
    
    all_data[uid] = data
    
    with open(brand_file, "w") as f:
        json.dump(all_data, f, indent=2)


def _read_local_brand(uid: str = "default") -> dict:
    """Read brand assets from local file."""
    brand_file = os.path.join(_PROJECT_ROOT, ".local_brands.json")
    
    if os.path.exists(brand_file):
        try:
            with open(brand_file, "r") as f:
                all_data = json.load(f)
                return all_data.get(uid, {})
        except Exception:
            pass
    
    return {}


# ─────────────────────────────────────────────────────────────
# Public API — User Profiles (Voice Engine / CRM context)
# ─────────────────────────────────────────────────────────────

def update_user_profile(uid: str, profile_data: dict) -> bool:
    """Update user profile/persona data.
    Persists to Supabase via a reserved '_system_profile' voice chunk (no DDL needed).
    Also writes local fallback to .local_profiles.json.
    """
    safe_uid = uid.strip() if uid else "default"
    existing_profile = _read_local_profile(safe_uid)
    merged_profile = {}
    if isinstance(existing_profile, dict):
        merged_profile.update(existing_profile)
    if isinstance(profile_data, dict):
        merged_profile.update(profile_data)

    _write_local_profile(merged_profile, safe_uid)

    if safe_uid == "default":
        return True

    try:
        client = _get_client()
        serialized = json.dumps(merged_profile, ensure_ascii=False)
        # Delete stale snapshot(s) then insert fresh one
        client.table("voice_chunks").delete().eq("user_id", safe_uid).eq("source_type", "_system_profile").execute()
        client.table("voice_chunks").insert({
            "user_id": safe_uid,
            "content": serialized,
            "source_type": "_system_profile",
            "metadata": {"type": "profile_snapshot"},
        }).execute()
        return True
    except Exception as e:
        print(f"[Supabase] update_user_profile error uid='{safe_uid}'. Saved locally. Error: {e}")
        return True


def get_user_profile(uid: str = "default") -> dict:
    """Get user profile/persona data.
    Reads from Supabase first (voice_chunks where source_type='_system_profile'),
    falls back to local .local_profiles.json.
    Auto-migrates local-only profiles to Supabase on first successful connection.
    """
    safe_uid = uid.strip() if uid else "default"

    if safe_uid != "default":
        try:
            client = _get_client()
            result = client.table("voice_chunks").select("content").eq("user_id", safe_uid).eq("source_type", "_system_profile").execute()
            if result.data:
                # Take the last snapshot (most recent insert)
                raw = result.data[-1].get("content", "{}")
                profile = json.loads(raw) if isinstance(raw, str) else {}
                if isinstance(profile, dict) and profile:
                    # Keep local file in sync
                    _write_local_profile(profile, safe_uid)
                    return profile
            else:
                # No snapshot in Supabase yet — migrate from local file if available
                local = _read_local_profile(safe_uid)
                if local and isinstance(local, dict):
                    print(f"[Supabase] Migrating local profile for uid={safe_uid} to Supabase...")
                    update_user_profile(safe_uid, local)
                    return local
        except Exception as e:
            print(f"[Supabase] get_user_profile error uid='{safe_uid}'. Falling back to local. Error: {e}")

    return _read_local_profile(safe_uid)


def _write_local_profile(data: dict, uid: str = "default"):
    """Write user profile/persona data to local file."""
    all_data = {}
    profile_file = os.path.join(_PROJECT_ROOT, ".local_profiles.json")

    if os.path.exists(profile_file):
        try:
            with open(profile_file, "r", encoding="utf-8") as f:
                all_data = json.load(f)
        except Exception:
            all_data = {}

    all_data[uid] = data

    with open(profile_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)


def _read_local_profile(uid: str = "default") -> dict:
    """Read user profile/persona data from local file."""
    profile_file = os.path.join(_PROJECT_ROOT, ".local_profiles.json")

    if os.path.exists(profile_file):
        try:
            with open(profile_file, "r", encoding="utf-8") as f:
                all_data = json.load(f)
                return all_data.get(uid, {})
        except Exception:
            pass

    return {}


# ─────────────────────────────────────────────────────────────
# Public API — CRM Contacts
# ─────────────────────────────────────────────────────────────

def _crm_contacts_file(safe_uid: str) -> str:
    os.makedirs(".tmp", exist_ok=True)
    return f".tmp/crm_contacts_{safe_uid}.json"


def _load_all_crm_contacts_local(safe_uid: str) -> list:
    path = _crm_contacts_file(safe_uid)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            pass
    return []


def _write_all_crm_contacts_local(contacts: list, safe_uid: str):
    path = _crm_contacts_file(safe_uid)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2, ensure_ascii=False, default=str)


def _crm_threads_file(safe_uid: str) -> str:
    os.makedirs(".tmp", exist_ok=True)
    return f".tmp/crm_threads_{safe_uid}.json"


def _load_all_crm_threads_local(safe_uid: str) -> dict:
    path = _crm_threads_file(safe_uid)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            pass
    return {}


def _write_all_crm_threads_local(threads: dict, safe_uid: str):
    path = _crm_threads_file(safe_uid)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(threads, f, indent=2, ensure_ascii=False, default=str)


def save_crm_conversation_thread(conversation_id: str, messages: list, uid: str = "default") -> bool:
    """Persist a conversation thread locally for context-aware CRM message generation."""
    safe_uid = uid.strip() if uid else "default"
    conv_id = str(conversation_id or "").strip()
    if not conv_id:
        return False

    safe_messages = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        safe_messages.append({
            "from": str(msg.get("from", "") or ""),
            "to": str(msg.get("to", "") or ""),
            "content": str(msg.get("content", "") or ""),
            "date": str(msg.get("date", "") or ""),
            "direction": str(msg.get("direction", "") or ""),
        })

    cache = _load_all_crm_threads_local(safe_uid)
    cache[conv_id] = safe_messages

    # Keep cache bounded for very large imports.
    if len(cache) > 6000:
        keys = list(cache.keys())[-5000:]
        cache = {key: cache[key] for key in keys}

    _write_all_crm_threads_local(cache, safe_uid)
    return True


def get_crm_conversation_thread(conversation_id: str, uid: str = "default") -> list:
    """Read cached conversation messages by conversation_id."""
    safe_uid = uid.strip() if uid else "default"
    conv_id = str(conversation_id or "").strip()
    if not conv_id:
        return []

    cache = _load_all_crm_threads_local(safe_uid)
    messages = cache.get(conv_id, [])
    return messages if isinstance(messages, list) else []


def _normalize_crm_contact(raw_contact: dict, safe_uid: str) -> dict:
    raw = raw_contact if isinstance(raw_contact, dict) else {}
    metadata = raw.get("metadata", {})
    if isinstance(metadata, str):
        metadata = _parse_json_field(metadata)
    if not isinstance(metadata, dict):
        metadata = {}

    contact_id = (
        (raw.get("id") or "").strip()
        or (raw.get("conversation_id") or "").strip()
        or str(uuid.uuid4())
    )

    return {
        "id": contact_id,
        "user_id": safe_uid,
        "conversation_id": raw.get("conversation_id", ""),
        "linkedin_url": raw.get("linkedin_url", ""),
        "full_name": raw.get("full_name", "Unknown"),
        "company": raw.get("company") or metadata.get("company", ""),
        "position": raw.get("position") or raw.get("title") or metadata.get("position") or metadata.get("title", ""),
        "title_source": raw.get("title_source") or metadata.get("title_source", "unknown"),
        "title_confidence": raw.get("title_confidence") or metadata.get("title_confidence", "low"),
        "behavioral_tag": raw.get("behavioral_tag", "cold_pitch"),
        "intent_summary": raw.get("intent_summary", ""),
        "warmth_score": int(raw.get("warmth_score", 0) or 0),
        "recommended_action": raw.get("recommended_action", ""),
        "last_message_date": raw.get("last_message_date", ""),
        "message_count": int(raw.get("message_count", 0) or 0),
        # Structured classification fields from Phase 2
        "reason_summary": raw.get("reason_summary") or metadata.get("reason_summary", ""),
        "evidence": raw.get("evidence") or metadata.get("evidence", []),
        "buyer_stage": raw.get("buyer_stage") or metadata.get("buyer_stage", ""),
        "urgency_score": int(raw.get("urgency_score") or metadata.get("urgency_score", 0) or 0),
        "fit_score": int(raw.get("fit_score") or metadata.get("fit_score", 0) or 0),
        "cold_outreacher_flag": bool(raw.get("cold_outreacher_flag") or metadata.get("cold_outreacher_flag", False)),
        "confidence": raw.get("confidence") or metadata.get("confidence", "medium"),
        "draft_message": raw.get("draft_message") or raw.get("draft") or metadata.get("draft_message", ""),
        "draft_updated_at": raw.get("draft_updated_at") or metadata.get("draft_updated_at"),
        "metadata": metadata,
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
    }


def _upsert_crm_contact_local(contact: dict, safe_uid: str):
    contacts = _load_all_crm_contacts_local(safe_uid)
    contacts = [c for c in contacts if c.get("id") != contact.get("id")]
    contacts.insert(0, contact)
    _write_all_crm_contacts_local(contacts[:5000], safe_uid)


def add_crm_contact(contact_data: dict, uid: str = "default") -> dict:
    """Create or update a CRM contact for a user with local-first persistence."""
    safe_uid = uid.strip() if uid else "default"
    contact = _normalize_crm_contact(contact_data, safe_uid)

    _upsert_crm_contact_local(contact, safe_uid)

    if safe_uid == "default":
        return contact

    try:
        client = _get_client()
        row = dict(contact)
        # Store draft in metadata JSON so it's preserved on Supabase reads
        meta = row.get("metadata", {})
        if isinstance(meta, dict) and row.get("draft_message"):
            meta["draft_message"] = row["draft_message"]
            meta["draft_updated_at"] = row.get("draft_updated_at") or meta.get("draft_updated_at")
            row["metadata"] = meta
        if isinstance(row.get("metadata"), dict):
            row["metadata"] = json.dumps(row["metadata"])
        # Map to actual Supabase column names — remove non-column keys
        row["draft"] = row.pop("draft_message", "") or ""
        row.pop("draft_updated_at", None)  # stored in metadata JSON only
        client.table("crm_contacts").upsert(row).execute()
        return contact
    except Exception as e:
        err = str(e)
        if "PGRST205" in err and "crm_contacts" in err:
            return contact
        print(f"[Supabase] add_crm_contact error uid='{safe_uid}'. Saved locally. Error: {e}")
        return contact


def _fetch_crm_contacts_supabase(
    client,
    safe_uid: str,
    tag_filter: str = None,
    min_warmth: int = 0,
    max_total: int = 5000,
    batch_size: int = 1000,
) -> list:
    """Fetch CRM contacts in pages to avoid PostgREST row caps on a single request."""
    all_rows = []
    start = 0

    while start < max_total:
        end = min(start + batch_size - 1, max_total - 1)

        query = client.table("crm_contacts").select("*").eq("user_id", safe_uid)
        if tag_filter and tag_filter != "all":
            query = query.eq("behavioral_tag", tag_filter)
        if min_warmth > 0:
            query = query.gte("warmth_score", min_warmth)

        result = (
            query
            .order("warmth_score", desc=True)
            .order("updated_at", desc=True)
            .range(start, end)
            .execute()
        )
        batch = result.data or []
        all_rows.extend(batch)

        expected_batch = (end - start) + 1
        if len(batch) < expected_batch:
            break

        start += batch_size

    return all_rows


def get_crm_contacts(uid: str = "default", tag_filter: str = None, min_warmth: int = 0) -> list:
    """Get CRM contacts for user with optional tag and warmth filters."""
    safe_uid = uid.strip() if uid else "default"
    min_warmth = int(min_warmth or 0)
    local_contacts = _load_all_crm_contacts_local(safe_uid)

    if safe_uid != "default":
        try:
            client = _get_client()
            rows = _fetch_crm_contacts_supabase(
                client=client,
                safe_uid=safe_uid,
                tag_filter=tag_filter,
                min_warmth=min_warmth,
                max_total=5000,
                batch_size=1000,
            )
            if rows is not None:
                supabase_contacts = [_normalize_crm_contact(row, safe_uid) for row in rows]

                # If Supabase returns no rows but local cache has contacts, prefer local fallback.
                if supabase_contacts or not local_contacts:
                    # Merge local draft data — Supabase may lack draft column or have stale drafts
                    if supabase_contacts and local_contacts:
                        local_by_id = {c.get("id"): c for c in local_contacts}
                        for sc in supabase_contacts:
                            local = local_by_id.get(sc.get("id"))
                            if not local:
                                continue
                            local_draft = local.get("draft_message") or (
                                local.get("metadata", {}).get("draft_message", "")
                                if isinstance(local.get("metadata"), dict) else ""
                            )
                            if local_draft and local_draft != sc.get("draft_message", ""):
                                sc["draft_message"] = local_draft
                                sc["draft_updated_at"] = (
                                    local.get("draft_updated_at")
                                    or (local.get("metadata", {}).get("draft_updated_at")
                                        if isinstance(local.get("metadata"), dict) else None)
                                )
                    return supabase_contacts
        except Exception as e:
            err = str(e)
            if not ("PGRST205" in err and "crm_contacts" in err):
                print(f"[Supabase] get_crm_contacts error uid='{safe_uid}'. Falling back to local. Error: {e}")

    filtered = [_normalize_crm_contact(c, safe_uid) for c in local_contacts]
    if tag_filter and tag_filter != "all":
        filtered = [c for c in filtered if c.get("behavioral_tag") == tag_filter]
    if min_warmth > 0:
        filtered = [c for c in filtered if int(c.get("warmth_score", 0) or 0) >= min_warmth]
    filtered.sort(key=lambda c: int(c.get("warmth_score", 0) or 0), reverse=True)
    return filtered


def get_crm_contact(contact_id: str, uid: str = "default") -> dict:
    """Get a single CRM contact by ID for a user."""
    safe_uid = uid.strip() if uid else "default"
    cid = (contact_id or "").strip()
    if not cid:
        return {}

    if safe_uid != "default":
        try:
            client = _get_client()
            result = (
                client.table("crm_contacts")
                .select("*")
                .eq("id", cid)
                .eq("user_id", safe_uid)
                .limit(1)
                .execute()
            )
            if result.data and len(result.data) > 0:
                return _normalize_crm_contact(result.data[0], safe_uid)
        except Exception as e:
            err = str(e)
            if not ("PGRST205" in err and "crm_contacts" in err):
                print(f"[Supabase] get_crm_contact error uid='{safe_uid}'. Falling back to local. Error: {e}")

    for contact in _load_all_crm_contacts_local(safe_uid):
        if contact.get("id") == cid:
            return _normalize_crm_contact(contact, safe_uid)
    return {}


def delete_crm_contact(contact_id: str, uid: str = "default") -> bool:
    """Delete a CRM contact by ID for a user."""
    safe_uid = uid.strip() if uid else "default"
    cid = (contact_id or "").strip()
    if not cid:
        return False

    contacts = _load_all_crm_contacts_local(safe_uid)
    contacts = [c for c in contacts if c.get("id") != cid]
    _write_all_crm_contacts_local(contacts, safe_uid)

    if safe_uid == "default":
        return True

    try:
        client = _get_client()
        client.table("crm_contacts").delete().eq("id", cid).eq("user_id", safe_uid).execute()
        return True
    except Exception as e:
        err = str(e)
        if "PGRST205" in err and "crm_contacts" in err:
            return True
        print(f"[Supabase] delete_crm_contact error uid='{safe_uid}'. Deleted locally. Error: {e}")
        return True


# ─────────────────────────────────────────────────────────────
# Public API — Supabase Storage (Generated Assets)
# ─────────────────────────────────────────────────────────────

_STORAGE_BUCKET = "generated-assets"
_bucket_verified = False


def _ensure_storage_bucket():
    """Create the storage bucket if it doesn't exist (idempotent)."""
    global _bucket_verified
    if _bucket_verified:
        return
    try:
        client = _get_client()
        # list_buckets is cheap; check if ours exists
        buckets = client.storage.list_buckets()
        bucket_ids = [b.id for b in buckets] if buckets else []
        print(f"[Storage] Existing buckets: {bucket_ids}")
        if _STORAGE_BUCKET not in bucket_ids:
            client.storage.create_bucket(
                _STORAGE_BUCKET,
                options={"public": True, "file_size_limit": 10485760},  # 10 MB
            )
            print(f"[Storage] Created bucket '{_STORAGE_BUCKET}'")
        else:
            print(f"[Storage] Bucket '{_STORAGE_BUCKET}' already exists ✓")
        _bucket_verified = True
    except Exception as e:
        err_str = str(e).lower()
        # If bucket already exists, mark as verified
        if "already exists" in err_str or "duplicate" in err_str or "409" in err_str:
            _bucket_verified = True
            print(f"[Storage] Bucket '{_STORAGE_BUCKET}' confirmed (exists)")
        else:
            print(f"[Storage] ✗ Bucket check/create FAILED: {type(e).__name__}: {e}")
            print(f"[Storage] ✗ Ensure 'generated-assets' bucket exists in Supabase Dashboard → Storage")
            print(f"[Storage] ✗ Or run the storage section from supabase_setup.sql in SQL Editor")


def upload_asset(local_path: str, uid: str = "default") -> str:
    """Upload a local file to Supabase Storage and return its public URL.

    The file is stored under ``{uid}/{filename}`` in the ``generated-assets``
    bucket.  Returns the public URL on success, or an empty string on failure
    (caller should fall back to the local ``/assets/`` URL).

    Retries up to 3 times with exponential backoff for transient failures.
    """
    import time as _t

    if not os.path.isfile(local_path):
        print(f"[Storage] File not found: {local_path}")
        return ""

    safe_uid = (uid or "default").strip()
    filename = os.path.basename(local_path)
    storage_path = f"{safe_uid}/{filename}"

    with open(local_path, "rb") as f:
        file_data = f.read()

    # Determine content type
    ext = os.path.splitext(filename)[1].lower()
    content_types = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".pdf": "application/pdf",
    }
    content_type = content_types.get(ext, "application/octet-stream")

    max_retries = 3
    backoff_delays = [2, 5, 10]
    last_error = None

    for attempt in range(max_retries):
        try:
            _ensure_storage_bucket()
            client = _get_client()
            bucket = client.storage.from_(_STORAGE_BUCKET)

            bucket.upload(
                storage_path,
                file_data,
                file_options={"content-type": content_type, "upsert": "true"},
            )

            public_url = bucket.get_public_url(storage_path)
            print(f"[Storage] Uploaded {filename} -> {public_url} (attempt {attempt + 1})")
            return public_url
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = backoff_delays[attempt]
                print(f"[Storage] Upload attempt {attempt + 1} failed: {e} — retrying in {delay}s...")
                _t.sleep(delay)
            else:
                print(f"[Storage] Upload FAILED after {max_retries} attempts for {local_path}: {e}")

    return ""


def get_asset_public_url(storage_path: str) -> str:
    """Return the public URL for an existing storage object."""
    try:
        client = _get_client()
        return client.storage.from_(_STORAGE_BUCKET).get_public_url(storage_path)
    except Exception as e:
        print(f"[Storage] URL lookup failed: {e}")
        return ""
