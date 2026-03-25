"""
LinkedIn Parser Module
Handles extraction and parsing of LinkedIn data export ZIP files.
Supports folder-agnostic parsing (handles nested folders like 'raw/').
"""

import zipfile
import io
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import re
from datetime import datetime


@dataclass
class LinkedInProfile:
    """Parsed LinkedIn profile data."""
    first_name: str = ""
    last_name: str = ""
    headline: str = ""
    summary: str = ""
    industry: str = ""
    location: str = ""
    profile_url: str = ""
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class LinkedInPosition:
    """Parsed LinkedIn position/job data."""
    title: str = ""
    company: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    location: str = ""
    is_current: bool = False


@dataclass
class LinkedInConnection:
    """Parsed LinkedIn connection data."""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    company: str = ""
    position: str = ""
    connected_on: str = ""
    profile_url: str = ""
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class LinkedInMessage:
    """Parsed LinkedIn message data."""
    from_name: str = ""
    to_name: str = ""
    date: str = ""
    subject: str = ""
    content: str = ""
    direction: str = ""  # 'SENT' or 'INBOX'
    conversation_id: str = ""


@dataclass
class LinkedInShare:
    """Parsed LinkedIn share/post data."""
    date: str = ""
    content: str = ""
    share_link: str = ""
    media_type: str = ""
    engagement_count: int = 0


class LinkedInParser:
    """Parse LinkedIn data export ZIP files."""
    
    def __init__(self):
        self.required_files = ['Profile.csv', 'Connections.csv']
        self.optional_files = [
            'messages.csv', 'Invitations.csv', 'Endorsement_Received_Info.csv',
            'Recommendations_Received.csv', 'Positions.csv', 'Shares.csv',
            'SearchQueries.csv', 'Skills.csv', 'Education.csv'
        ]
    
    def validate_and_parse_zip(self, zip_file_bytes: bytes) -> Dict:
        """
        Validate ZIP and extract available CSVs gracefully.
        Handles nested folder structures (e.g., 'raw/Profile.csv').
        
        Returns:
            Dict with status, message, extracted data, and diagnostics
        """
        extracted_data = {}
        missing_required = []
        missing_optional = []
        files_found = []          # CSV filenames actually matched
        rows_per_file = {}        # {filename: row_count}
        skipped_reasons = []      # human-readable skip notes
        all_zip_entries = []      # raw namelist for diagnostics
        
        try:
            with zipfile.ZipFile(io.BytesIO(zip_file_bytes)) as z:
                namelist = z.namelist()
                all_zip_entries = list(namelist)
                
                # Check for required files (folder-agnostic)
                for req in self.required_files:
                    matched_path = self._find_file(namelist, req)
                    if not matched_path:
                        missing_required.append(req)
                    else:
                        files_found.append(req)
                        rows = self._parse_csv(z, matched_path)
                        key = req.replace('.csv', '').lower()
                        extracted_data[key] = rows
                        rows_per_file[req] = len(rows)
                
                # Extract optional files (folder-agnostic)
                for opt in self.optional_files:
                    matched_path = self._find_file(namelist, opt)
                    if matched_path:
                        files_found.append(opt)
                        rows = self._parse_csv(z, matched_path)
                        key = opt.replace('.csv', '').lower()
                        extracted_data[key] = rows
                        rows_per_file[opt] = len(rows)
                    else:
                        missing_optional.append(opt)
                        
        except zipfile.BadZipFile:
            return {
                "status": "error",
                "message": "Invalid ZIP file",
                "proceed": False,
                "data": {},
                "diagnostics": {"error": "Invalid ZIP file"}
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"ZIP parsing error: {str(e)}",
                "proceed": False,
                "data": {},
                "diagnostics": {"error": str(e)}
            }
        
        # Build skip reasons for user guidance
        if missing_required:
            for f in missing_required:
                skipped_reasons.append(f"{f} not found in ZIP — this file is important for full analysis.")
        if missing_optional:
            for f in missing_optional:
                skipped_reasons.append(f"{f} not found (optional — won't block import).")
        
        status = "partial" if missing_required else "complete"
        message = f"Missing required files: {missing_required}" if missing_required else "All files present"
        
        diagnostics = {
            "files_found": files_found,
            "rows_per_file": rows_per_file,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "skipped_reasons": skipped_reasons,
            "zip_entry_count": len(all_zip_entries),
        }
        
        return {
            "status": status,
            "message": message,
            "proceed": True,
            "data": extracted_data,
            "diagnostics": diagnostics
        }
    
    def _find_file(self, namelist: List[str], filename: str) -> Optional[str]:
        """Find file in namelist regardless of folder structure."""
        # Direct match
        if filename in namelist:
            return filename
        
        # Check for file in any folder
        for path in namelist:
            if path.endswith('/' + filename) or path.endswith('\\' + filename):
                return path
        
        return None
    
    # Known LinkedIn CSV header tokens used to detect the real header row
    # when a preamble (e.g. "Notes:" + description) precedes the actual data.
    _KNOWN_HEADERS = {
        "first name", "last name", "company", "position", "email address",
        "connected on", "url", "from", "to", "date", "content", "direction",
        "folder", "conversation id", "title", "headline", "summary",
        "started on", "finished on", "company name", "sharecommentary",
    }

    def _detect_header_row(self, raw_text: str) -> int:
        """Return the 0-based line index of the real CSV header row.

        LinkedIn sometimes prepends a "Notes:" preamble + blank lines before
        the actual column headers.  We scan forward looking for a line that
        contains at least 2 known header tokens separated by commas.
        """
        for idx, line in enumerate(raw_text.split("\n")):
            stripped = line.strip().lower()
            if not stripped:
                continue
            tokens = {t.strip().strip('"').strip("'") for t in stripped.split(",")}
            matches = tokens & self._KNOWN_HEADERS
            if len(matches) >= 2:
                return idx
        return 0  # fallback – treat first line as header

    def _parse_csv(self, zip_file: zipfile.ZipFile, path: str) -> List[Dict]:
        """Parse CSV file from ZIP."""
        try:
            with zip_file.open(path) as f:
                raw_bytes = f.read()

            raw_text = raw_bytes.decode("utf-8-sig", errors="replace")
            skip_rows = self._detect_header_row(raw_text)
            if skip_rows > 0:
                print(f"[LinkedInParser] Skipping {skip_rows} preamble row(s) in {path}")

            buf = io.BytesIO(raw_bytes)
            # LinkedIn exports can vary delimiters/quoting across locales.
            # Use python engine + delimiter auto-detection and skip malformed rows.
            try:
                df = pd.read_csv(
                    buf,
                    encoding='utf-8-sig',
                    sep=None,
                    engine='python',
                    on_bad_lines='skip',
                    skiprows=skip_rows,
                )
            except TypeError:
                # Compatibility for older pandas versions without on_bad_lines.
                buf.seek(0)
                df = pd.read_csv(
                    buf,
                    encoding='utf-8-sig',
                    sep=None,
                    engine='python',
                    error_bad_lines=False,
                    warn_bad_lines=True,
                    skiprows=skip_rows,
                )

            # Normalize column headers to Title Case so downstream parsers
            # work regardless of LinkedIn export casing (UPPERCASE / lowercase / Title Case).
            df.columns = [col.strip().title() for col in df.columns]
            return df.fillna('').to_dict('records')
        except Exception as e:
            print(f"[LinkedInParser] Error parsing {path}: {e}")
            return []
    
    def parse_profile(self, profile_data: List[Dict]) -> LinkedInProfile:
        """Parse Profile.csv data."""
        if not profile_data:
            return LinkedInProfile()
        
        data = profile_data[0]  # Profile.csv has one row
        return LinkedInProfile(
            first_name=data.get('First Name', ''),
            last_name=data.get('Last Name', ''),
            headline=data.get('Headline', ''),
            summary=data.get('Summary', ''),
            industry=data.get('Industry', ''),
            location=data.get('Location', ''),
            profile_url=data.get('Profile Url', '')
        )
    
    def parse_positions(self, positions_data: List[Dict]) -> List[LinkedInPosition]:
        """Parse Positions.csv data."""
        positions = []
        for data in positions_data:
            pos = LinkedInPosition(
                title=data.get('Title', ''),
                company=data.get('Company Name', ''),
                start_date=data.get('Started On', ''),
                end_date=data.get('Finished On', ''),
                description=data.get('Description', ''),
                location=data.get('Location', ''),
                is_current=pd.isna(data.get('Finished On')) or data.get('Finished On', '') == ''
            )
            positions.append(pos)
        return positions
    
    def parse_connections(self, connections_data: List[Dict]) -> List[LinkedInConnection]:
        """Parse Connections.csv data."""
        connections = []
        for data in connections_data:
            conn = LinkedInConnection(
                first_name=data.get('First Name', ''),
                last_name=data.get('Last Name', ''),
                email=data.get('Email Address', ''),
                company=data.get('Company', ''),
                position=data.get('Position', ''),
                connected_on=data.get('Connected On', ''),
                profile_url=data.get('Url', '')
            )
            connections.append(conn)
        return connections
    
    def parse_messages(self, messages_data: List[Dict], user_name: str = "") -> List[LinkedInMessage]:
        """
        Parse messages.csv data.
        Groups messages by conversation and tags direction.
        """
        messages = []
        for data in messages_data:
            # Headers are normalized to Title Case by _parse_csv
            from_name = data.get('From', '')
            to_name = data.get('To', '')
            direction_val = str(data.get('Direction') or data.get('Folder', '')).upper()
            
            msg = LinkedInMessage(
                from_name=from_name,
                to_name=to_name,
                date=data.get('Date', ''),
                subject=data.get('Subject', ''),
                content=data.get('Content', ''),
                direction='SENT' if direction_val in ('OUTGOING', 'SENT') else 'INBOX',
                conversation_id=self._generate_conversation_id(data)
            )
            if msg.content:
                messages.append(msg)
        return messages

    def parse_shares(self, shares_data: List[Dict]) -> List[LinkedInShare]:
        """Parse Shares.csv (posts) data."""
        shares = []
        for data in shares_data:
            share = LinkedInShare(
                date=data.get('Date', ''),
                content=data.get('ShareCommentary', ''),
                share_link=data.get('ShareLink', ''),
                media_type=data.get('MediaType', ''),
                engagement_count=self._extract_engagement_count(data.get('Engagement', ''))
            )
            shares.append(share)
        return shares
    
    def _generate_conversation_id(self, message_data: Dict) -> str:
        """Generate conversation ID from message participants."""
        # Use existing conversation ID if available (new format)
        conv_id = message_data.get('Conversation Id')
        if conv_id:
            return str(conv_id)
            
        from_name = message_data.get('From', '')
        to_name = message_data.get('To', '')
        # Create consistent ID based on sorted names
        names = sorted([from_name, to_name])
        return f"conv_{names[0]}_{names[1]}".replace(' ', '_').lower()
    
    def _extract_engagement_count(self, engagement_str: str) -> int:
        """Extract engagement count from engagement string."""
        if not engagement_str:
            return 0
        # Look for numbers in the string
        numbers = re.findall(r'\d+', str(engagement_str))
        return sum(int(n) for n in numbers) if numbers else 0
    
    def group_messages_by_thread(self, messages: List[LinkedInMessage]) -> Dict[str, List[LinkedInMessage]]:
        """Group messages by conversation thread."""
        threads = {}
        for msg in messages:
            if msg.conversation_id not in threads:
                threads[msg.conversation_id] = []
            threads[msg.conversation_id].append(msg)
        
        # Sort each thread by date
        for thread_id in threads:
            threads[thread_id].sort(key=lambda x: x.date)
        
        return threads
    
    def extract_career_summary(self, positions: List[LinkedInPosition]) -> str:
        """Generate career summary from positions."""
        if not positions:
            return ""
        
        current = [p for p in positions if p.is_current]
        past = [p for p in positions if not p.is_current]
        
        summary_parts = []
        
        if current:
            roles = ", ".join([f"{p.title} at {p.company}" for p in current[:2]])
            summary_parts.append(f"Currently: {roles}")
        
        if past:
            past_roles = ", ".join([f"{p.title} at {p.company}" for p in past[:3]])
            summary_parts.append(f"Previously: {past_roles}")
        
        total_years = self._calculate_total_years(positions)
        if total_years > 0:
            summary_parts.append(f"{total_years}+ years experience")
        
        return " | ".join(summary_parts)
    
    def _calculate_total_years(self, positions: List[LinkedInPosition]) -> int:
        """Calculate total years of experience from positions."""
        total_days = 0
        for pos in positions:
            try:
                if pos.start_date:
                    start = pd.to_datetime(pos.start_date)
                    if pos.is_current or not pos.end_date:
                        end = datetime.now()
                    else:
                        end = pd.to_datetime(pos.end_date)
                    total_days += (end - start).days
            except:
                pass
        return max(0, total_days // 365)


# Convenience functions for direct usage
def parse_linkedin_zip(zip_bytes: bytes, user_name: str = "") -> Dict:
    """
    Convenience function to parse LinkedIn export ZIP.
    
    Args:
        zip_bytes: ZIP file bytes
        user_name: Name of the user (for message direction tagging)
        
    Returns:
        Dict with parsed profile, positions, connections, messages, shares, diagnostics
    """
    parser = LinkedInParser()
    
    # Validate and parse ZIP
    result = parser.validate_and_parse_zip(zip_bytes)
    
    if not result["proceed"]:
        return result
    
    data = result["data"]
    
    # Parse individual components
    parsed = {
        "status": result["status"],
        "message": result["message"],
        "profile": parser.parse_profile(data.get('profile', [])),
        "positions": parser.parse_positions(data.get('positions', [])),
        "connections": parser.parse_connections(data.get('connections', [])),
        "messages": parser.parse_messages(data.get('messages', []), user_name),
        "shares": parser.parse_shares(data.get('shares', [])),
        "raw_data": data,
        "diagnostics": result.get("diagnostics", {}),
    }
    
    # Add derived data
    if parsed["positions"]:
        parsed["career_summary"] = parser.extract_career_summary(parsed["positions"])
    
    if parsed["messages"]:
        parsed["message_threads"] = parser.group_messages_by_thread(parsed["messages"])
    
    return parsed


def parse_multiple_zips(zip_bytes_list: List[bytes], user_name: str = "") -> Dict:
    """
    Parse multiple LinkedIn export ZIPs and merge their data safely.

    Deduplication strategy:
    - Connections: dedupe by profile_url, then by normalized full_name
    - Messages/threads: dedupe by conversation_id (union of messages per thread)
    - Positions: dedupe by (company, title) tuple
    - Shares: dedupe by (date, content[:80]) tuple
    - Profile: use the most complete profile (most non-empty fields)

    Args:
        zip_bytes_list: List of ZIP file byte contents
        user_name: Name of the user (for message direction tagging)

    Returns:
        Merged Dict matching parse_linkedin_zip output, plus aggregate diagnostics
    """
    if not zip_bytes_list:
        return {"status": "error", "message": "No ZIP files provided", "proceed": False, "data": {}, "diagnostics": {"error": "No files"}}

    if len(zip_bytes_list) == 1:
        return parse_linkedin_zip(zip_bytes_list[0], user_name)

    all_parsed = []
    per_zip_diagnostics = []

    for i, zb in enumerate(zip_bytes_list):
        parsed = parse_linkedin_zip(zb, user_name)
        per_zip_diagnostics.append({
            "zip_index": i,
            "status": parsed.get("status", "error"),
            "diagnostics": parsed.get("diagnostics", {}),
        })
        if parsed.get("proceed") is False and parsed.get("status") == "error":
            print(f"[LinkedInParser] ZIP #{i} failed: {parsed.get('message')}")
            continue
        all_parsed.append(parsed)

    if not all_parsed:
        return {
            "status": "error",
            "message": "All ZIP files failed to parse",
            "proceed": False,
            "data": {},
            "diagnostics": {"per_zip": per_zip_diagnostics, "error": "All ZIPs failed"},
        }

    # ── Merge profile: pick the one with the most non-empty fields ──
    def _profile_score(p):
        if not p:
            return 0
        fields = [p.first_name, p.last_name, p.headline, p.summary, p.industry, p.location, p.profile_url]
        return sum(1 for f in fields if f)

    best_profile = max((p.get("profile") for p in all_parsed), key=_profile_score, default=LinkedInProfile())

    # ── Merge connections: dedupe by profile_url then normalized name ──
    seen_conn_urls = set()
    seen_conn_names = set()
    merged_connections = []
    for p in all_parsed:
        for conn in (p.get("connections") or []):
            url = (conn.profile_url or "").strip().rstrip("/").lower()
            if url and url in seen_conn_urls:
                continue
            norm_name = f"{conn.first_name} {conn.last_name}".strip().lower()
            if not url and norm_name in seen_conn_names:
                continue
            if url:
                seen_conn_urls.add(url)
            if norm_name:
                seen_conn_names.add(norm_name)
            merged_connections.append(conn)

    # ── Merge messages & threads: dedupe by conversation_id ──
    merged_threads: Dict[str, List[LinkedInMessage]] = {}
    seen_msg_keys = set()  # (conversation_id, date, content[:60])
    for p in all_parsed:
        for msg in (p.get("messages") or []):
            msg_key = (msg.conversation_id, msg.date, (msg.content or "")[:60])
            if msg_key in seen_msg_keys:
                continue
            seen_msg_keys.add(msg_key)
            if msg.conversation_id not in merged_threads:
                merged_threads[msg.conversation_id] = []
            merged_threads[msg.conversation_id].append(msg)

    # Sort each thread by date
    for tid in merged_threads:
        merged_threads[tid].sort(key=lambda x: x.date)

    merged_messages = []
    for msgs in merged_threads.values():
        merged_messages.extend(msgs)

    # ── Merge positions: dedupe by (company, title) ──
    seen_positions = set()
    merged_positions = []
    for p in all_parsed:
        for pos in (p.get("positions") or []):
            key = (pos.company.strip().lower(), pos.title.strip().lower())
            if key in seen_positions:
                continue
            seen_positions.add(key)
            merged_positions.append(pos)

    # ── Merge shares: dedupe by (date, content prefix) ──
    seen_shares = set()
    merged_shares = []
    for p in all_parsed:
        for share in (p.get("shares") or []):
            key = (share.date, (share.content or "")[:80])
            if key in seen_shares:
                continue
            seen_shares.add(key)
            merged_shares.append(share)

    # ── Aggregate diagnostics ──
    agg_files = set()
    agg_rows = {}
    agg_missing_req = set()
    agg_missing_opt = set()
    agg_skipped = []
    for p in all_parsed:
        diag = p.get("diagnostics") or {}
        for f in diag.get("files_found", []):
            agg_files.add(f)
        for fname, cnt in diag.get("rows_per_file", {}).items():
            agg_rows[fname] = agg_rows.get(fname, 0) + cnt
        for f in diag.get("missing_required", []):
            agg_missing_req.add(f)
        for f in diag.get("missing_optional", []):
            agg_missing_opt.add(f)
        agg_skipped.extend(diag.get("skipped_reasons", []))

    # Files found in ANY zip are no longer missing
    agg_missing_req -= agg_files
    agg_missing_opt -= agg_files

    career_summary = ""
    if merged_positions:
        parser = LinkedInParser()
        career_summary = parser.extract_career_summary(merged_positions)

    merged_diagnostics = {
        "zip_count": len(zip_bytes_list),
        "zips_parsed_ok": len(all_parsed),
        "files_found": sorted(agg_files),
        "rows_per_file": agg_rows,
        "missing_required": sorted(agg_missing_req),
        "missing_optional": sorted(agg_missing_opt),
        "skipped_reasons": agg_skipped,
        "dedup_stats": {
            "connections_total": sum(len(p.get("connections") or []) for p in all_parsed),
            "connections_after_dedup": len(merged_connections),
            "messages_total": sum(len(p.get("messages") or []) for p in all_parsed),
            "messages_after_dedup": len(merged_messages),
            "threads_after_dedup": len(merged_threads),
        },
        "per_zip": per_zip_diagnostics,
    }

    status = "partial" if agg_missing_req else "complete"

    print(f"[LinkedInParser] Merged {len(zip_bytes_list)} ZIPs: "
          f"{len(merged_connections)} connections, {len(merged_threads)} threads, "
          f"{len(merged_positions)} positions, {len(merged_shares)} shares")

    return {
        "status": status,
        "message": f"Merged {len(all_parsed)}/{len(zip_bytes_list)} ZIPs successfully",
        "proceed": True,
        "profile": best_profile,
        "positions": merged_positions,
        "connections": merged_connections,
        "messages": merged_messages,
        "shares": merged_shares,
        "message_threads": merged_threads,
        "career_summary": career_summary,
        "diagnostics": merged_diagnostics,
        "raw_data": {},  # Not meaningful for merged output
    }


if __name__ == "__main__":
    # Test with sample data
    print("[LinkedInParser] Module loaded successfully")
    print("[LinkedInParser] Test parse_linkedin_zip function with a LinkedIn export ZIP file")
