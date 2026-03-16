import pandas as pd
import hashlib
import datetime
import json
import os

from . import classifier
from . import interaction_timeline


CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")

# Load products.json from lead_generator for product segment matching
PRODUCTS_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'lead_generator', 'config', 'products.json')


def _load_product_segments():
    try:
        with open(PRODUCTS_CONFIG, 'r') as f:
            return json.load(f).get('segments', {})
    except Exception:
        return {}


PRODUCT_SEGMENTS = _load_product_segments()


def _normalize_name(first, last):
    """Create normalized lowercase name for matching."""
    first = str(first).strip() if pd.notna(first) else ""
    last = str(last).strip() if pd.notna(last) else ""
    return f"{first} {last}".strip().lower()


def _make_id(name, company):
    """Create a stable hash-based ID for a connection."""
    raw = f"{name}|{company}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _url_slug(url):
    """Extract the slug from a LinkedIn profile URL."""
    if not url or not isinstance(url, str):
        return ""
    return url.rstrip('/').split('/')[-1].lower()


def _get_product_segment(position):
    """Check if position matches any product segment keywords."""
    if not position or not isinstance(position, str):
        return None
    pos_lower = position.lower()
    for seg_name, criteria in PRODUCT_SEGMENTS.items():
        if any(neg.lower() in pos_lower for neg in criteria.get('negative_keywords', [])):
            continue
        if any(kw.lower() in pos_lower for kw in criteria.get('keywords', [])):
            return seg_name
    return None


def _count_endorsements_received(name_lower, df):
    """Count how many endorsements received from this person, and which skills."""
    if df.empty:
        return 0, []
    mask = (
        df['Endorser First Name'].fillna('').astype(str).str.strip().str.lower() + " " +
        df['Endorser Last Name'].fillna('').astype(str).str.strip().str.lower()
    ).str.contains(name_lower, regex=False)
    accepted = df[mask & (df.get('Endorsement Status', pd.Series(dtype=str)) == 'ACCEPTED')]
    skills = accepted['Skill Name'].dropna().tolist() if 'Skill Name' in accepted.columns else []
    return len(accepted), skills


def _count_endorsements_given(name_lower, df):
    """Count how many endorsements you gave to this person."""
    if df.empty:
        return 0
    mask = (
        df['Endorsee First Name'].fillna('').astype(str).str.strip().str.lower() + " " +
        df['Endorsee Last Name'].fillna('').astype(str).str.strip().str.lower()
    ).str.contains(name_lower, regex=False)
    accepted = df[mask & (df.get('Endorsement Status', pd.Series(dtype=str)) == 'ACCEPTED')]
    return len(accepted)


def _check_recommendation(name_lower, df):
    """Check if this person wrote a visible recommendation."""
    if df.empty:
        return False
    mask = (
        df['First Name'].fillna('').astype(str).str.strip().str.lower() + " " +
        df['Last Name'].fillna('').astype(str).str.strip().str.lower()
    ).str.contains(name_lower, regex=False)
    visible = df[mask & (df.get('Status', pd.Series(dtype=str)) == 'VISIBLE')]
    return len(visible) > 0


def _check_follows_you(name_lower, member_follows_df):
    """Check if this person follows you."""
    if member_follows_df.empty:
        return False
    mask = member_follows_df['FullName'].fillna('').astype(str).str.lower().str.contains(name_lower, regex=False)
    active = member_follows_df[mask & (member_follows_df.get('Status', pd.Series(dtype=str)) == 'Active')]
    return len(active) > 0


def _get_invitation_info(name_lower, profile_url, invitations_df):
    """Get invitation direction and whether it had a message."""
    if invitations_df.empty:
        return None, False

    slug = _url_slug(profile_url)

    for _, row in invitations_df.iterrows():
        from_f = str(row.get('From', '')).lower()
        to_f = str(row.get('To', '')).lower()
        inviter_url = str(row.get('inviterProfileUrl', '')).lower()
        invitee_url = str(row.get('inviteeProfileUrl', '')).lower()

        matched = False
        if name_lower and (name_lower in from_f or name_lower in to_f):
            matched = True
        if slug and (slug in inviter_url or slug in invitee_url):
            matched = True

        if matched:
            direction = str(row.get('Direction', ''))
            message = str(row.get('Message', ''))
            has_message = bool(message and message.strip() and message != 'nan')
            return direction, has_message

    return None, False


def _analyze_messages(name_lower, profile_url, messages_df, now):
    """Analyze message history with a connection.

    Returns dict with:
        - count: total message count
        - last_date: most recent message date
        - last_days: days since last message
        - direction: 'they_initiated', 'you_initiated', 'mutual', or None
        - intent_keywords: list of found intent keywords
    """
    result = {
        "count": 0, "last_date": None, "last_days": None,
        "direction": None, "intent_keywords": [],
        "thread_count": 0
    }

    if messages_df.empty:
        return result

    slug = _url_slug(profile_url)

    mask_name = (
        messages_df['FROM'].astype(str).str.lower().str.contains(name_lower, regex=False) |
        messages_df['TO'].astype(str).str.lower().str.contains(name_lower, regex=False)
    )

    mask_url = pd.Series(False, index=messages_df.index)
    if slug and len(slug) > 2:
        sender_col = messages_df.get('SENDER PROFILE URL', pd.Series(dtype=str)).astype(str).str.lower()
        recipient_col = messages_df.get('RECIPIENT PROFILE URLS', pd.Series(dtype=str)).astype(str).str.lower()
        mask_url = sender_col.str.contains(slug, regex=False) | recipient_col.str.contains(slug, regex=False)

    matched = messages_df[mask_name | mask_url]

    if matched.empty:
        return result

    result["count"] = len(matched)

    # Thread count (unique conversations)
    if 'CONVERSATION ID' in matched.columns:
        result["thread_count"] = matched['CONVERSATION ID'].nunique()
    else:
        result["thread_count"] = 1

    # Recency
    dates = matched['DATE'].dropna()
    if not dates.empty:
        latest = dates.max()
        if pd.notna(latest):
            result["last_date"] = latest.strftime('%Y-%m-%d') if hasattr(latest, 'strftime') else str(latest)[:10]
            try:
                result["last_days"] = (now - latest).days
            except Exception:
                result["last_days"] = None

    # Direction analysis
    from_them = matched[matched['FROM'].astype(str).str.lower().str.contains(name_lower, regex=False)]
    from_you = matched[~matched['FROM'].astype(str).str.lower().str.contains(name_lower, regex=False)]

    if len(from_them) > 0 and len(from_you) > 0:
        # Check who sent first
        first_from_them = from_them['DATE'].min() if not from_them['DATE'].dropna().empty else pd.NaT
        first_from_you = from_you['DATE'].min() if not from_you['DATE'].dropna().empty else pd.NaT
        if pd.notna(first_from_them) and pd.notna(first_from_you):
            result["direction"] = "they_initiated" if first_from_them < first_from_you else "mutual"
        else:
            result["direction"] = "mutual"
    elif len(from_them) > 0:
        result["direction"] = "they_initiated"
    elif len(from_you) > 0:
        result["direction"] = "you_initiated"

    # Intent keyword scan
    all_content = " ".join(matched['CONTENT'].fillna('').astype(str).tolist()).lower()

    # Load intent keywords from scoring config
    try:
        with open(os.path.join(CONFIG_DIR, "scoring_weights.json"), 'r') as f:
            sw = json.load(f)
        intent_config = sw.get("intent_keywords", {})
    except Exception:
        intent_config = {}

    for level in ["high", "medium", "low"]:
        for kw in intent_config.get(level, []):
            if kw in all_content:
                result["intent_keywords"].append({"keyword": kw, "level": level})

    return result


def build_all_profiles(data):
    """Build unified profiles for all connections.

    Args:
        data: dict from data_loader.load_all()

    Returns:
        list of profile dicts
    """
    connections = data["connections"]
    if connections.empty:
        print("No connections found!")
        return []

    now = pd.Timestamp.now(tz='UTC')
    profiles = []
    total = len(connections)

    print(f"Building profiles for {total} connections...")

    for i, row in connections.iterrows():
        if (i + 1) % 200 == 0:
            print(f"  Processing {i + 1}/{total}...")

        first = str(row.get('First Name', '')).strip() if pd.notna(row.get('First Name')) else ''
        last = str(row.get('Last Name', '')).strip() if pd.notna(row.get('Last Name')) else ''
        full_name = f"{first} {last}".strip()
        name_lower = _normalize_name(first, last)
        url = str(row.get('URL', '')) if pd.notna(row.get('URL')) else ''
        position = str(row.get('Position', '')) if pd.notna(row.get('Position')) else ''
        company = str(row.get('Company', '')) if pd.notna(row.get('Company')) else ''
        email = str(row.get('Email Address', '')) if pd.notna(row.get('Email Address')) else ''

        # Connection date
        connected_on = row.get('Connected On')
        connected_date = None
        tenure_days = 0
        if pd.notna(connected_on):
            try:
                if isinstance(connected_on, pd.Timestamp):
                    connected_date = connected_on.strftime('%Y-%m-%d')
                    tenure_days = (now - connected_on.tz_localize('UTC') if connected_on.tzinfo is None else now - connected_on).days
                else:
                    connected_date = str(connected_on)[:10]
            except Exception:
                connected_date = str(connected_on)[:10]

        if not name_lower or name_lower.strip() == '':
            continue

        # Classifications
        seniority_tier, seniority_level = classifier.classify_seniority(position)
        industries = classifier.classify_industries(position, company)
        product_segment = _get_product_segment(position)

        # Cross-reference all data sources
        endorse_received_count, endorsed_skills = _count_endorsements_received(name_lower, data["endorsements_received"])
        endorse_given_count = _count_endorsements_given(name_lower, data["endorsements_given"])
        recommended_you = _check_recommendation(name_lower, data["recommendations_received"])
        you_recommended = _check_recommendation(name_lower, data["recommendations_given"])
        follows_you = _check_follows_you(name_lower, data["member_follows"])
        invite_direction, invite_has_message = _get_invitation_info(name_lower, url, data["invitations"])
        msg_analysis = _analyze_messages(name_lower, url, data["messages"], now)

        # Check if they reacted to your posts (from surveillance data)
        they_reacted = False
        if url and data.get("surveillance_urls"):
            slug = _url_slug(url)
            they_reacted = any(slug in s_url.lower() for s_url in data["surveillance_urls"]) if slug else False

        # Build interaction timeline
        timeline = interaction_timeline.build_timeline(name_lower, url, data)
        timeline_stats = interaction_timeline.compute_timeline_stats(timeline)

        # Count touchpoints for engagement classification
        touchpoints = 0
        if msg_analysis["count"] > 0:
            touchpoints += 1
        if endorse_received_count > 0:
            touchpoints += 1
        if endorse_given_count > 0:
            touchpoints += 1
        if recommended_you:
            touchpoints += 1
        if you_recommended:
            touchpoints += 1
        if they_reacted:
            touchpoints += 1
        if invite_has_message:
            touchpoints += 1

        # Classify relationship and engagement
        rel_signals = {
            "endorsed_you": endorse_received_count > 0,
            "recommended_you": recommended_you,
            "last_message_days": msg_analysis["last_days"],
            "has_inbound_invite_with_message": invite_direction == "INCOMING" and invite_has_message,
            "connection_tenure_days": tenure_days,
            "has_any_interaction": touchpoints > 0
        }
        relationship_type = classifier.classify_relationship(rel_signals)
        engagement_level = classifier.classify_engagement(touchpoints)

        # Signals dict (raw data for scoring engine)
        signals = {
            "endorsed_you": endorse_received_count > 0,
            "endorsement_received_count": endorse_received_count,
            "endorsed_skills": endorsed_skills,
            "you_endorsed_them": endorse_given_count > 0,
            "endorsement_given_count": endorse_given_count,
            "recommended_you": recommended_you,
            "you_recommended_them": you_recommended,
            "follows_you": follows_you,
            "they_reacted_to_you": they_reacted,
            "has_inbound_invite": invite_direction == "INCOMING",
            "invite_has_message": invite_has_message,
            "invite_direction": invite_direction,
            "message_count": msg_analysis["count"],
            "thread_count": msg_analysis["thread_count"],
            "last_message_date": msg_analysis["last_date"],
            "last_message_days": msg_analysis["last_days"],
            "message_direction": msg_analysis["direction"],
            "intent_keywords": msg_analysis["intent_keywords"],
            "your_reactions_to_them": 0,  # Populated by company_intelligence cross-ref
            "your_comments_on_them": 0,   # Populated by company_intelligence cross-ref
            "abm_cluster_size": 0,         # Populated by company_intelligence
            "connection_tenure_days": tenure_days,
            "touchpoint_count": touchpoints
        }

        profile = {
            "id": _make_id(full_name, company),
            "first_name": first,
            "last_name": last,
            "full_name": full_name,
            "url": url,
            "email": email,
            "position": position,
            "company": company,
            "connected_on": connected_date,
            "seniority_tier": seniority_tier,
            "seniority_level": seniority_level,
            "industry_verticals": industries,
            "product_segment": product_segment,
            "relationship_type": relationship_type,
            "engagement_level": engagement_level,
            "scores": {},  # Populated by scoring_engine
            "tier": "",    # Populated by scoring_engine
            "interactions": timeline[:20],  # Cap at 20 most recent
            "timeline_stats": timeline_stats,
            "signals": signals,
            "enrichment": None
        }

        profiles.append(profile)

    print(f"Built {len(profiles)} profiles.")
    return profiles
