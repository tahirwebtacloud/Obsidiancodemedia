"""
firestore_client.py
-------------------
Thin wrapper around Firebase Admin SDK for reading/writing app settings.
Uses the project ID from .env; no service account file required when running
on a machine already authenticated via `firebase login` (ADC).
"""

import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import concurrent.futures

load_dotenv()

_db = None
_fs_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _get_db():
    """Initialize Firebase Admin SDK once and return the Firestore client."""
    global _db
    if _db is not None:
        return _db

    project_id = os.getenv("FIREBASE_PROJECT_ID", "fir-mop")
    sa_path_raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "")

    # Resolve service account path relative to project root (not CWD)
    sa_path = ""
    if sa_path_raw:
        # Try as-is first, then relative to project root
        if os.path.isabs(sa_path_raw) and os.path.exists(sa_path_raw):
            sa_path = sa_path_raw
        else:
            resolved = os.path.join(_PROJECT_ROOT, sa_path_raw)
            if os.path.exists(resolved):
                sa_path = resolved
            elif os.path.exists(sa_path_raw):
                sa_path = sa_path_raw

    # Pre-check credentials to avoid google-auth hanging on missing metadata server
    has_credentials = False
    if sa_path:
        has_credentials = True
    else:
        # Check standard default ADC paths
        if os.name == 'nt':
            adc_path = os.path.join(os.environ.get('APPDATA', ''), 'gcloud', 'application_default_credentials.json')
            if os.path.exists(adc_path):
                has_credentials = True
        else:
            adc_path = os.path.expanduser('~/.config/gcloud/application_default_credentials.json')
            if os.path.exists(adc_path):
                has_credentials = True

    if not has_credentials:
        raise Exception(
            "No Firebase credentials found. Either:\n"
            "  1. Set FIREBASE_SERVICE_ACCOUNT_PATH in .env to a service account JSON, or\n"
            "  2. Run `gcloud auth application-default login` for ADC."
        )

    # Check if already initialized (e.g., multiple imports)
    if not firebase_admin._apps:
        if sa_path:
            # Use explicit service account file (preferred — never expires)
            print(f"[Firestore] Using service account: {sa_path}")
            cred = credentials.Certificate(sa_path)
        else:
            # Fall back to Application Default Credentials (may expire)
            print("[Firestore] Using Application Default Credentials (ADC)")
            cred = credentials.ApplicationDefault()

        firebase_admin.initialize_app(cred, {"projectId": project_id})

    _db = firestore.client()
    return _db


# ─────────────────────────────────────────────────────────────
import json

# Absolute path anchored to project root so all scripts resolve to the same file
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_SETTINGS_FILE = os.path.join(_PROJECT_ROOT, ".local_settings.json")

def _read_local_settings(uid: str = "default") -> dict:
    """Read local settings for a specific user from the shared JSON file."""
    if os.path.exists(LOCAL_SETTINGS_FILE):
        try:
            with open(LOCAL_SETTINGS_FILE, "r") as f:
                all_data = json.load(f)
            # Migration: if old flat format (no nested UIDs), treat as 'default'
            if all_data and not any(isinstance(v, dict) for v in all_data.values()):
                return all_data if uid == "default" else {}
            return all_data.get(uid, {})
        except Exception:
            return {}
    return {}

def _write_local_settings(data: dict, uid: str = "default"):
    """Write local settings for a specific user into the shared JSON file."""
    all_data = {}
    if os.path.exists(LOCAL_SETTINGS_FILE):
        try:
            with open(LOCAL_SETTINGS_FILE, "r") as f:
                all_data = json.load(f)
            # Migration: if old flat format, move it under 'default'
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
# Public API
# ─────────────────────────────────────────────────────────────

FIRESTORE_TIMEOUT = 15.0  # seconds before falling back to local file


def _user_doc_ref(db, uid: str):
    """Return the Firestore DocumentReference for a specific user."""
    safe_uid = uid.strip() if uid else "default"
    return db.collection("users").document(safe_uid)


def get_setting(key: str, default=None, uid: str = "default"):
    """Read a single setting value from Firestore for a specific user."""
    def _fetch():
        db = _get_db()
        doc = _user_doc_ref(db, uid).get(timeout=FIRESTORE_TIMEOUT)
        return doc.to_dict().get(key, default) if doc.exists else default

    try:
        future = _fs_executor.submit(_fetch)
        return future.result(timeout=8.0)
    except concurrent.futures.TimeoutError:
        print(f"[Firestore] get_setting '{key}' timed out. Falling back to local.")
    except Exception as e:
        print(f"[Firestore] get_setting error for key '{key}' uid='{uid}'. Falling back to local. Error: {e}")
        
    return _read_local_settings(uid=uid).get(key, default)


def set_setting(key: str, value, uid: str = "default") -> bool:
    """Write / update a single setting key in Firestore for a specific user."""
    try:
        db = _get_db()
        _user_doc_ref(db, uid).set({key: value}, merge=True, timeout=FIRESTORE_TIMEOUT)
        _write_local_settings({key: value}, uid=uid)
        return True
    except Exception as e:
        print(f"[Firestore] set_setting timeout/error for key '{key}' uid='{uid}'. Saving locally. Error: {e}")
        _write_local_settings({key: value}, uid=uid)
        return True


def get_all_settings(uid: str = "default") -> dict:
    """Return the entire settings document for a specific user."""
    def _fetch():
        db = _get_db()
        doc = _user_doc_ref(db, uid).get(timeout=FIRESTORE_TIMEOUT)
        return doc.to_dict() or {} if doc.exists else {}

    try:
        future = _fs_executor.submit(_fetch)
        return future.result(timeout=8.0)
    except concurrent.futures.TimeoutError:
        print(f"[Firestore] get_all_settings timed out. Falling back to local.")
    except Exception as e:
        print(f"[Firestore] get_all_settings error uid='{uid}'. Falling back to local. Error: {e}")
        
    return _read_local_settings(uid=uid)


def update_settings(data: dict, uid: str = "default") -> bool:
    """Merge multiple key/value pairs into the settings document for a specific user."""
    try:
        db = _get_db()
        _user_doc_ref(db, uid).set(data, merge=True, timeout=FIRESTORE_TIMEOUT)
        _write_local_settings(data, uid=uid)
        return True
    except Exception as e:
        print(f"[Firestore] update_settings timeout/error uid='{uid}'. Saving locally. Error: {e}")
        _write_local_settings(data, uid=uid)
        return True

def add_history_entry(entry: dict, uid: str = "default"):
    """Write a history entry to Firestore and local cache."""
    safe_uid = uid.strip() if uid else "default"
    
    # Local cache (fallback)
    os.makedirs(".tmp", exist_ok=True)
    history_file = f".tmp/history_{safe_uid}.json" if safe_uid != "default" else "history.json"
    history_data = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except:
            pass
    history_data = [d for d in history_data if isinstance(d, dict) and d.get("id") != entry.get("id")]
    history_data.insert(0, entry)
    history_data = history_data[:500]
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=4, ensure_ascii=False)
        
    # Firestore
    if safe_uid == "default":
        return
        
    try:
        db = _get_db()
        entry_id = entry.get("id")
        if not entry_id:
            import uuid
            entry_id = str(uuid.uuid4())
            entry["id"] = entry_id
        _user_doc_ref(db, safe_uid).collection("history").document(entry_id).set(entry, merge=True, timeout=FIRESTORE_TIMEOUT)
    except Exception as e:
        print(f"[Firestore] add_history_entry error uid='{safe_uid}'. Saved locally. Error: {e}")

def get_user_history(uid: str = "default") -> list:
    """Read full history from Firestore. Fallback to local."""
    safe_uid = uid.strip() if uid else "default"
    
    if safe_uid != "default":
        def _fetch():
            db = _get_db()
            docs = _user_doc_ref(db, safe_uid).collection("history").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(100).get(timeout=FIRESTORE_TIMEOUT)
            return [doc.to_dict() for doc in docs]

        try:
            future = _fs_executor.submit(_fetch)
            history = future.result(timeout=8.0)
            if history:
                return history
        except concurrent.futures.TimeoutError:
            print(f"[Firestore] get_user_history timed out. Falling back to local.")
        except Exception as e:
            print(f"[Firestore] get_user_history error uid='{safe_uid}'. Falling back to local. Error: {e}")
        
    history_file = f".tmp/history_{safe_uid}.json" if safe_uid != "default" else "history.json"
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []
