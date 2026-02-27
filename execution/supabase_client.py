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
from dotenv import load_dotenv

load_dotenv()

_supabase = None

# Absolute path anchored to project root so all scripts resolve to the same file
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_SETTINGS_FILE = os.path.join(_PROJECT_ROOT, ".local_settings.json")


def _get_client():
    """Initialize Supabase client once and return it."""
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
    print(f"[Supabase] Connected to {url}")
    return _supabase


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
