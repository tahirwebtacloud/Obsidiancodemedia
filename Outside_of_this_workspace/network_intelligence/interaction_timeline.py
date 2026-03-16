import pandas as pd
import datetime


def build_timeline(full_name_lower, profile_url, data):
    """Build a chronological interaction timeline for a single connection.

    Args:
        full_name_lower: normalized "first last" in lowercase
        profile_url: LinkedIn profile URL (e.g. https://www.linkedin.com/in/someone)
        data: dict of DataFrames from data_loader.load_all()

    Returns:
        list of event dicts sorted by date (newest first), each containing:
        - type: str (message_sent, message_received, endorsement_received, etc.)
        - date: str (ISO format)
        - direction: str (inbound, outbound, mutual)
        - snippet: str (short preview)
    """
    events = []

    # 1. Messages
    events.extend(_message_events(full_name_lower, profile_url, data.get("messages", pd.DataFrame())))

    # 2. Endorsements received
    events.extend(_endorsement_received_events(full_name_lower, data.get("endorsements_received", pd.DataFrame())))

    # 3. Endorsements given
    events.extend(_endorsement_given_events(full_name_lower, data.get("endorsements_given", pd.DataFrame())))

    # 4. Recommendations received
    events.extend(_recommendation_events(full_name_lower, data.get("recommendations_received", pd.DataFrame()), direction="inbound"))

    # 5. Recommendations given
    events.extend(_recommendation_events(full_name_lower, data.get("recommendations_given", pd.DataFrame()), direction="outbound"))

    # 6. Invitations
    events.extend(_invitation_events(full_name_lower, profile_url, data.get("invitations", pd.DataFrame())))

    # Sort by date descending (newest first)
    events.sort(key=lambda e: e.get("date", ""), reverse=True)

    return events


def _message_events(name_lower, profile_url, messages_df):
    """Extract message events for a connection."""
    events = []
    if messages_df.empty:
        return events

    # Match by name in FROM/TO or by profile URL in SENDER/RECIPIENT URLs
    mask_name = (
        messages_df['FROM'].astype(str).str.lower().str.contains(name_lower, regex=False) |
        messages_df['TO'].astype(str).str.lower().str.contains(name_lower, regex=False)
    )

    mask_url = pd.Series(False, index=messages_df.index)
    if profile_url:
        url_slug = profile_url.rstrip('/').split('/')[-1].lower()
        if url_slug and len(url_slug) > 2:
            mask_url = (
                messages_df.get('SENDER PROFILE URL', pd.Series(dtype=str)).astype(str).str.lower().str.contains(url_slug, regex=False) |
                messages_df.get('RECIPIENT PROFILE URLS', pd.Series(dtype=str)).astype(str).str.lower().str.contains(url_slug, regex=False)
            )

    matched = messages_df[mask_name | mask_url]

    for _, row in matched.iterrows():
        date_val = row.get('DATE')
        date_str = _format_date(date_val)
        from_field = str(row.get('FROM', '')).lower()
        content = str(row.get('CONTENT', ''))
        if content in ('nan', 'None', ''):
            content = "(No content)"

        is_from_them = name_lower in from_field
        direction = "inbound" if is_from_them else "outbound"

        events.append({
            "type": f"message_{'received' if is_from_them else 'sent'}",
            "date": date_str,
            "direction": direction,
            "snippet": content[:120] + ("..." if len(content) > 120 else "")
        })

    return events


def _endorsement_received_events(name_lower, df):
    """Extract endorsement-received events."""
    events = []
    if df.empty:
        return events

    for _, row in df.iterrows():
        endorser_name = f"{row.get('Endorser First Name', '')} {row.get('Endorser Last Name', '')}".strip().lower()
        if name_lower and name_lower in endorser_name:
            skill = str(row.get('Skill Name', 'Unknown'))
            date_str = str(row.get('Endorsement Date', ''))[:10]
            events.append({
                "type": "endorsement_received",
                "date": date_str,
                "direction": "inbound",
                "snippet": f"Endorsed your skill: {skill}"
            })

    return events


def _endorsement_given_events(name_lower, df):
    """Extract endorsement-given events."""
    events = []
    if df.empty:
        return events

    for _, row in df.iterrows():
        endorsee_name = f"{row.get('Endorsee First Name', '')} {row.get('Endorsee Last Name', '')}".strip().lower()
        if name_lower and name_lower in endorsee_name:
            skill = str(row.get('Skill Name', 'Unknown'))
            date_str = str(row.get('Endorsement Date', ''))[:10]
            events.append({
                "type": "endorsement_given",
                "date": date_str,
                "direction": "outbound",
                "snippet": f"You endorsed their skill: {skill}"
            })

    return events


def _recommendation_events(name_lower, df, direction="inbound"):
    """Extract recommendation events."""
    events = []
    if df.empty:
        return events

    for _, row in df.iterrows():
        rec_name = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip().lower()
        if name_lower and name_lower in rec_name:
            status = str(row.get('Status', ''))
            event_type = "recommendation_received" if direction == "inbound" else "recommendation_given"
            events.append({
                "type": event_type,
                "date": "",  # Recommendations CSV doesn't always have dates
                "direction": direction,
                "snippet": f"Recommendation ({status})"
            })

    return events


def _invitation_events(name_lower, profile_url, df):
    """Extract invitation events."""
    events = []
    if df.empty:
        return events

    for _, row in df.iterrows():
        from_field = str(row.get('From', '')).lower()
        to_field = str(row.get('To', '')).lower()
        inviter_url = str(row.get('inviterProfileUrl', ''))
        invitee_url = str(row.get('inviteeProfileUrl', ''))

        # Match by name or URL
        matched = False
        if name_lower and (name_lower in from_field or name_lower in to_field):
            matched = True
        if profile_url:
            url_slug = profile_url.rstrip('/').split('/')[-1].lower()
            if url_slug and (url_slug in inviter_url.lower() or url_slug in invitee_url.lower()):
                matched = True

        if not matched:
            continue

        direction_field = str(row.get('Direction', ''))
        is_inbound = direction_field == 'INCOMING'
        message = str(row.get('Message', ''))
        date_val = row.get('Sent At')
        date_str = _format_date(date_val)

        events.append({
            "type": "invitation",
            "date": date_str,
            "direction": "inbound" if is_inbound else "outbound",
            "snippet": message[:120] if message and message not in ('nan', 'None', '') else "(No message)"
        })

    return events


def _format_date(date_val):
    """Convert various date formats to ISO string."""
    if pd.isna(date_val) if not isinstance(date_val, str) else not date_val:
        return ""
    if isinstance(date_val, (pd.Timestamp, datetime.datetime)):
        return date_val.strftime('%Y-%m-%d')
    return str(date_val)[:10]


def compute_timeline_stats(timeline):
    """Compute summary statistics from a timeline.

    Returns dict with:
        - total_events: int
        - first_interaction: str (date)
        - last_interaction: str (date)
        - inbound_count: int
        - outbound_count: int
        - message_count: int
    """
    if not timeline:
        return {
            "total_events": 0,
            "first_interaction": None,
            "last_interaction": None,
            "inbound_count": 0,
            "outbound_count": 0,
            "message_count": 0
        }

    dates = [e["date"] for e in timeline if e.get("date")]
    messages = [e for e in timeline if "message" in e.get("type", "")]

    return {
        "total_events": len(timeline),
        "first_interaction": min(dates) if dates else None,
        "last_interaction": max(dates) if dates else None,
        "inbound_count": sum(1 for e in timeline if e.get("direction") == "inbound"),
        "outbound_count": sum(1 for e in timeline if e.get("direction") == "outbound"),
        "message_count": len(messages)
    }
