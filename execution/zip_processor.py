"""
zip_processor.py
----------------
Extract and parse LinkedIn data export ZIP files for the Voice Engine + CRM rebuild.

Handles:
  - messages.csv (conversation threads)
  - Connections.csv (connection-only contacts)
  - Profile.csv (user's own profile data)

Carries forward all battle-tested fixes from the original linkedin_parser.py:
  - Header preamble detection (LinkedIn's "Notes:" rows)
  - Case normalization (.title()) for header consistency
  - Folder-agnostic file lookup (handles nested dirs like 'raw/')
  - Draft message exclusion (FOLDER == 'DRAFT')
"""

import io
import re
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# Known LinkedIn CSV header tokens for preamble detection
_KNOWN_HEADERS = {
    "first name", "last name", "company", "position", "email address",
    "connected on", "url", "from", "to", "date", "content", "direction",
    "folder", "conversation id", "title", "headline", "summary",
    "started on", "finished on", "company name", "sharecommentary",
    "profile url",
}


def _detect_header_row(raw_text: str) -> int:
    """Return the 0-based line index of the real CSV header row.

    LinkedIn sometimes prepends a 'Notes:' preamble + blank lines before
    the actual column headers. We scan forward looking for a line that
    contains at least 2 known header tokens separated by commas.
    """
    for idx, line in enumerate(raw_text.split("\n")):
        stripped = line.strip().lower()
        if not stripped:
            continue
        tokens = {t.strip().strip('"').strip("'") for t in stripped.split(",")}
        matches = tokens & _KNOWN_HEADERS
        if len(matches) >= 2:
            return idx
    return 0


def _find_file(namelist: List[str], filename: str) -> Optional[str]:
    """Find a CSV file in the ZIP namelist regardless of folder structure.

    Handles direct match, subfolder match (raw/filename), and case variations.
    """
    lower_target = filename.lower()
    # Direct match
    if filename in namelist:
        return filename
    # Folder-agnostic match
    for path in namelist:
        basename = path.split("/")[-1].split("\\")[-1]
        if basename.lower() == lower_target:
            return path
    return None


def _parse_csv_from_zip(z: zipfile.ZipFile, path: str) -> List[Dict]:
    """Parse a CSV file from inside a ZIP, with preamble detection and header normalization."""
    try:
        with z.open(path) as f:
            raw_bytes = f.read()

        raw_text = raw_bytes.decode("utf-8-sig", errors="replace")
        skip_rows = _detect_header_row(raw_text)
        if skip_rows > 0:
            print(f"[ZIP] Skipping {skip_rows} preamble row(s) in {path}")

        buf = io.BytesIO(raw_bytes)
        try:
            df = pd.read_csv(
                buf,
                encoding="utf-8-sig",
                sep=None,
                engine="python",
                on_bad_lines="skip",
                skiprows=skip_rows,
            )
        except TypeError:
            buf.seek(0)
            df = pd.read_csv(
                buf,
                encoding="utf-8-sig",
                sep=None,
                engine="python",
                error_bad_lines=False,
                warn_bad_lines=True,
                skiprows=skip_rows,
            )

        # Normalize headers to Title Case for consistency
        df.columns = [col.strip().title() for col in df.columns]
        return df.fillna("").to_dict("records")

    except Exception as e:
        print(f"[ZIP] Error parsing {path}: {e}")
        return []


def _normalize_url(url: str) -> str:
    """Normalize a LinkedIn profile URL for dedup matching."""
    return (url or "").strip().rstrip("/").lower()


def process_zip(zip_bytes: bytes) -> Dict[str, Any]:
    """Process a LinkedIn data export ZIP file.

    Returns:
        {
            "status": "complete" | "partial" | "error",
            "message": str,
            "profile": {...} or None,         # Profile.csv first row
            "connections": [...],              # Connections.csv rows
            "conversations": {conv_id: [msgs]},  # messages.csv grouped by conversation
            "diagnostics": {...}
        }
    """
    result = {
        "status": "error",
        "message": "",
        "profile": None,
        "connections": [],
        "conversations": {},
        "diagnostics": {},
    }

    try:
        z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        result["message"] = "Invalid ZIP file"
        return result
    except Exception as e:
        result["message"] = f"ZIP open error: {e}"
        return result

    namelist = z.namelist()
    files_found = []
    rows_per_file = {}

    # ── Profile.csv ────────────────────────────────────────────────────────
    profile_path = _find_file(namelist, "Profile.csv")
    if profile_path:
        files_found.append("Profile.csv")
        profile_rows = _parse_csv_from_zip(z, profile_path)
        rows_per_file["Profile.csv"] = len(profile_rows)
        if profile_rows:
            p = profile_rows[0]
            result["profile"] = {
                "first_name": str(p.get("First Name", "")).strip(),
                "last_name": str(p.get("Last Name", "")).strip(),
                "headline": str(p.get("Headline", "")).strip(),
                "summary": str(p.get("Summary", "")).strip(),
                "industry": str(p.get("Industry", "")).strip(),
                "location": str(p.get("Location") or p.get("Geo Location", "")).strip(),
                "profile_url": _normalize_url(p.get("Profile Url", "") or p.get("Url", "")),
            }

    # ── Connections.csv ────────────────────────────────────────────────────
    conn_path = _find_file(namelist, "Connections.csv")
    if conn_path:
        files_found.append("Connections.csv")
        conn_rows = _parse_csv_from_zip(z, conn_path)
        rows_per_file["Connections.csv"] = len(conn_rows)

        connections = []
        for row in conn_rows:
            first = str(row.get("First Name", "")).strip()
            last = str(row.get("Last Name", "")).strip()
            if not first and not last:
                continue
            connections.append({
                "first_name": first,
                "last_name": last,
                "full_name": f"{first} {last}".strip(),
                "company": str(row.get("Company", "")).strip(),
                "position": str(row.get("Position", "")).strip(),
                "email": str(row.get("Email Address", "")).strip(),
                "connected_on": str(row.get("Connected On", "")).strip(),
                "linkedin_url": _normalize_url(
                    row.get("Url", "") or row.get("Profile Url", "")
                ),
            })
        result["connections"] = connections

    # ── messages.csv ───────────────────────────────────────────────────────
    msg_path = _find_file(namelist, "messages.csv")
    if msg_path:
        files_found.append("messages.csv")
        msg_rows = _parse_csv_from_zip(z, msg_path)
        rows_per_file["messages.csv"] = len(msg_rows)

        conversations: Dict[str, List[Dict]] = {}
        draft_count = 0

        for row in msg_rows:
            # Skip drafts
            folder = str(row.get("Folder", "")).strip().upper()
            if folder == "DRAFT":
                draft_count += 1
                continue

            conv_id = str(
                row.get("Conversation Id", "") or row.get("Conversation Title", "")
            ).strip()
            if not conv_id:
                continue

            msg = {
                "from": str(row.get("From", "")).strip(),
                "to": str(row.get("To", "")).strip(),
                "date": str(row.get("Date", "")).strip(),
                "content": str(row.get("Content", "")).strip(),
                "direction": str(row.get("Direction", "")).strip().upper(),
                "folder": folder,
            }

            if conv_id not in conversations:
                conversations[conv_id] = []
            conversations[conv_id].append(msg)

        # Sort each conversation by date
        for conv_id in conversations:
            conversations[conv_id].sort(key=lambda m: m.get("date", ""))

        result["conversations"] = conversations
        if draft_count:
            print(f"[ZIP] Excluded {draft_count} draft messages")

    z.close()

    # ── Status ─────────────────────────────────────────────────────────────
    has_messages = bool(result["conversations"])
    has_connections = bool(result["connections"])

    if has_messages or has_connections:
        result["status"] = "complete" if has_messages and has_connections else "partial"
        result["message"] = (
            f"Found {len(result['conversations'])} conversations, "
            f"{len(result['connections'])} connections"
        )
    else:
        result["status"] = "error"
        result["message"] = "No messages or connections found in ZIP"

    result["diagnostics"] = {
        "files_found": files_found,
        "rows_per_file": rows_per_file,
        "conversation_count": len(result["conversations"]),
        "connection_count": len(result["connections"]),
        "zip_entries": len(namelist),
    }

    print(f"[ZIP] Processed: {result['diagnostics']}")
    return result


def derive_contact_name(messages: List[Dict], user_name: str) -> str:
    """Extract the OTHER person's name from a conversation thread.

    Filters out the user's own name and common LinkedIn placeholders.
    """
    _PLACEHOLDERS = {
        "linkedin member", "unknown", "you", "me", "myself", "",
    }

    names = []
    for msg in messages:
        for field in ("from", "to"):
            name = str(msg.get(field, "")).strip()
            if name:
                names.append(name)

    if not names:
        return "Unknown Contact"

    user_norm = (user_name or "").strip().lower()
    excluded = _PLACEHOLDERS | {user_norm}

    filtered = [n for n in names if n.strip().lower() not in excluded]
    if not filtered:
        filtered = names

    # Most common name wins
    from collections import Counter
    counter = Counter([n.strip() for n in filtered if n.strip()])
    if not counter:
        return "Unknown Contact"

    best = counter.most_common(1)[0][0]
    if best.lower() in _PLACEHOLDERS:
        return "Unknown Contact"
    return best


def derive_contact_url(messages: List[Dict], user_url: str) -> str:
    """Try to extract the other person's LinkedIn URL from message metadata.

    LinkedIn messages.csv doesn't always include profile URLs,
    so this is best-effort. Returns '' if not found.
    """
    # Messages don't typically have profile URLs — this would need
    # cross-referencing with Connections.csv which is done in server.py
    return ""
