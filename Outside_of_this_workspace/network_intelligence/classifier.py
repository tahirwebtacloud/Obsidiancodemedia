import json
import os
import re

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")


def _load_taxonomy():
    with open(os.path.join(CONFIG_DIR, "taxonomy.json"), 'r') as f:
        return json.load(f)


TAXONOMY = _load_taxonomy()


def classify_seniority(position):
    """Classify a job title into a seniority tier.
    Returns tuple of (tier_name, level_int).
    Higher level = more senior. C_SUITE=6, VP=5, DIRECTOR=4, MANAGER=3, INDIVIDUAL=2, OTHER=1.
    """
    if not position or not isinstance(position, str):
        return "OTHER", 1

    pos = position.strip()
    tiers = TAXONOMY["seniority_tiers"]

    # Check tiers in order from most senior to least
    # This ensures "VP of Engineering" matches VP before INDIVIDUAL (Engineer)
    for tier_name in ["C_SUITE", "VP", "DIRECTOR", "MANAGER", "INDIVIDUAL"]:
        tier = tiers[tier_name]
        for keyword in tier["keywords"]:
            # Use word boundary-aware matching
            # "CEO" should match "CEO" and "CEO & Founder" but not "ProcessCEO"
            pattern = r'(?:^|[\s,/\-&(])' + re.escape(keyword) + r'(?:$|[\s,/\-&)])'
            if re.search(pattern, pos, re.IGNORECASE):
                return tier_name, tier["level"]

    return "OTHER", 1


def classify_industries(position, company):
    """Classify into one or more industry verticals based on position + company.
    Returns a list of matching vertical names, ordered by relevance.
    """
    if not position and not company:
        return ["OTHER"]

    text = f"{position or ''} {company or ''}".lower()
    verticals = TAXONOMY["industry_verticals"]
    matches = []

    for vertical_name, config in verticals.items():
        for keyword in config["keywords"]:
            if keyword.lower() in text:
                matches.append(vertical_name)
                break

    return matches if matches else ["OTHER"]


def classify_relationship(signals):
    """Classify the relationship type based on interaction signals.

    Args:
        signals: dict with keys:
            - endorsed_you (bool)
            - recommended_you (bool)
            - last_message_days (int or None): days since last message
            - has_inbound_invite_with_message (bool)
            - connection_tenure_days (int)
            - has_any_interaction (bool)

    Returns: relationship type string
    """
    has_advocacy = signals.get('endorsed_you', False) or signals.get('recommended_you', False)
    last_msg_days = signals.get('last_message_days')
    has_recent = last_msg_days is not None and last_msg_days < 90
    has_yearly = last_msg_days is not None and last_msg_days < 365
    has_inbound = signals.get('has_inbound_invite_with_message', False)
    tenure = signals.get('connection_tenure_days', 0)
    has_any = signals.get('has_any_interaction', False)

    # Check from most valuable to least
    if has_advocacy and has_recent:
        return "CHAMPION"
    if has_advocacy:
        return "ADVOCATE"
    if has_recent:
        return "ACTIVE_CONTACT"
    if has_yearly:
        return "WARM_CONTACT"
    if has_inbound:
        return "INBOUND_LEAD"
    if tenure < 90:
        return "NEW_CONNECTION"
    if not has_any and tenure > 365:
        return "DORMANT"
    if not has_any:
        return "COLD"

    return "COLD"


def classify_engagement(touchpoint_count):
    """Classify engagement level based on total touchpoint count.

    Touchpoints: messages exchanged, endorsements given/received,
    recommendations, reactions, comments, invitations with messages.

    Returns: engagement level string
    """
    levels = TAXONOMY["engagement_levels"]

    if touchpoint_count >= levels["SUPER_ENGAGED"]["min_touchpoints"]:
        return "SUPER_ENGAGED"
    if touchpoint_count >= levels["ENGAGED"]["min_touchpoints"]:
        return "ENGAGED"
    if touchpoint_count >= levels["LIGHT"]["min_touchpoints"]:
        return "LIGHT"
    return "PASSIVE"
