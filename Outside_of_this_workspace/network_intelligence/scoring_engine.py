import json
import os

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")


def _load_weights():
    with open(os.path.join(CONFIG_DIR, "scoring_weights.json"), 'r') as f:
        return json.load(f)


WEIGHTS = _load_weights()


def score_role_fit(profile):
    """Dimension 1: Role Fit (0-250 pts).
    Seniority tier (0-100) + Industry match (0-80) + Product segment match (0-70).
    """
    cfg = WEIGHTS["dimensions"]["role_fit"]["sub_signals"]

    # Seniority
    tier = profile.get("seniority_tier", "OTHER")
    seniority_pts = cfg["seniority_tier"]["values"].get(tier, 0)

    # Industry match - score based on having a non-OTHER industry
    industries = profile.get("industry_verticals", [])
    if industries and industries != ["OTHER"]:
        industry_pts = cfg["industry_match"]["primary_match"]
    else:
        industry_pts = cfg["industry_match"]["no_match"]

    # Product segment match (reuses lead_generator products.json)
    segment = profile.get("product_segment")
    if segment:
        product_pts = cfg["product_segment_match"]["full_match"]
    else:
        product_pts = cfg["product_segment_match"]["no_match"]

    return min(seniority_pts + industry_pts + product_pts, 250)


def score_relationship(profile):
    """Dimension 2: Relationship Strength (0-250 pts).
    Message recency + frequency + direction + tenure + inbound invite + endorsement reciprocity.
    """
    cfg = WEIGHTS["dimensions"]["relationship_strength"]["sub_signals"]
    signals = profile.get("signals", {})
    pts = 0

    # Message recency
    last_days = signals.get("last_message_days")
    if last_days is not None:
        for threshold, score in sorted(cfg["message_recency"]["thresholds_days"].items(), key=lambda x: int(x[0])):
            if last_days <= int(threshold):
                pts += score
                break
    else:
        pts += cfg["message_recency"]["no_messages"]

    # Message frequency (using thread count for better signal)
    thread_count = signals.get("thread_count", 0)
    freq_pts = 0
    for threshold, score in sorted(cfg["message_frequency"]["thresholds_count"].items(), key=lambda x: int(x[0]), reverse=True):
        if thread_count >= int(threshold):
            freq_pts = score
            break
    pts += freq_pts

    # Message direction
    direction = signals.get("message_direction")
    if direction:
        pts += cfg["message_direction"].get(direction, 0)
    else:
        pts += cfg["message_direction"]["no_messages"]

    # Connection tenure
    tenure = signals.get("connection_tenure_days", 0)
    for threshold, score in sorted(cfg["connection_tenure"]["thresholds_days"].items(), key=lambda x: int(x[0]), reverse=True):
        if tenure >= int(threshold):
            pts += score
            break

    # Inbound invite
    if signals.get("has_inbound_invite") and signals.get("invite_has_message"):
        pts += cfg["inbound_invite"]["inbound_with_message"]
    elif signals.get("has_inbound_invite"):
        pts += cfg["inbound_invite"]["inbound_no_message"]
    elif signals.get("invite_direction") == "OUTGOING":
        pts += cfg["inbound_invite"]["outbound"]

    # Endorsement reciprocity
    endorsed_you = signals.get("endorsed_you", False)
    you_endorsed = signals.get("you_endorsed_them", False)
    if endorsed_you and you_endorsed:
        pts += cfg["endorsement_reciprocity"]["mutual"]
    elif endorsed_you:
        pts += cfg["endorsement_reciprocity"]["they_endorsed_you"]
    elif you_endorsed:
        pts += cfg["endorsement_reciprocity"]["you_endorsed_them"]

    return min(pts, 250)


def score_advocacy(profile):
    """Dimension 3: Advocacy & Trust (0-200 pts).
    Recommendation received + endorsement + skill overlap + social debt + follows.
    """
    cfg = WEIGHTS["dimensions"]["advocacy_trust"]["sub_signals"]
    signals = profile.get("signals", {})
    pts = 0

    # Recommendation received
    if signals.get("recommended_you"):
        pts += cfg["recommendation_received"]["visible"]

    # Endorsement received
    if signals.get("endorsed_you"):
        pts += cfg["endorsement_received"]["accepted"]

    # Endorsement skill overlap (did they endorse a relevant skill?)
    endorsed_skills = signals.get("endorsed_skills", [])
    relevant_skills = WEIGHTS.get("relevant_skills", [])
    if endorsed_skills and relevant_skills:
        has_relevant = any(
            any(rel.lower() in skill.lower() for rel in relevant_skills)
            for skill in endorsed_skills
        )
        if has_relevant:
            pts += cfg["endorsement_skill_overlap"]["relevant_skill"]
        elif endorsed_skills:
            pts += cfg["endorsement_skill_overlap"]["other_skill"]

    # Social debt: you recommended them
    if signals.get("you_recommended_them"):
        pts += cfg["recommendation_given"]["given"]

    # Social debt: you endorsed them
    if signals.get("you_endorsed_them"):
        pts += cfg["endorsement_given"]["given"]

    # Follows you
    if signals.get("follows_you"):
        pts += cfg["follows_you"]["active"]

    return min(pts, 200)


def score_engagement(profile):
    """Dimension 4: Engagement Signals (0-150 pts).
    Intent keywords + your reactions/comments to them + their reactions to you.
    """
    cfg = WEIGHTS["dimensions"]["engagement_signals"]["sub_signals"]
    signals = profile.get("signals", {})
    pts = 0

    # Intent keywords (highest-level match wins)
    intent_kws = signals.get("intent_keywords", [])
    if intent_kws:
        levels = [kw.get("level", "low") for kw in intent_kws]
        if "high" in levels:
            pts += cfg["intent_keywords"]["high_intent"]
        elif "medium" in levels:
            pts += cfg["intent_keywords"]["medium_intent"]
        else:
            pts += cfg["intent_keywords"]["low_intent"]

    # Your reactions to their posts
    reaction_count = signals.get("your_reactions_to_them", 0)
    for threshold, score in sorted(cfg["your_reactions_to_them"]["thresholds_count"].items(), key=lambda x: int(x[0]), reverse=True):
        if reaction_count >= int(threshold):
            pts += score
            break

    # Your comments on their posts
    comment_count = signals.get("your_comments_on_them", 0)
    for threshold, score in sorted(cfg["your_comments_on_them"]["thresholds_count"].items(), key=lambda x: int(x[0]), reverse=True):
        if comment_count >= int(threshold):
            pts += score
            break

    # They reacted to your posts
    if signals.get("they_reacted_to_you"):
        pts += cfg["they_reacted_to_you"]["reacted"]

    return min(pts, 150)


def score_company_intel(profile):
    """Dimension 5: Company Intelligence (0-100 pts).
    ABM cluster + company followed + in searches + enrichment data.
    """
    cfg = WEIGHTS["dimensions"]["company_intelligence"]["sub_signals"]
    signals = profile.get("signals", {})
    pts = 0

    # ABM cluster size
    cluster_size = signals.get("abm_cluster_size", 0)
    for threshold, score in sorted(cfg["abm_cluster_size"]["thresholds_count"].items(), key=lambda x: int(x[0]), reverse=True):
        if cluster_size >= int(threshold):
            pts += score
            break

    # Company followed by you
    if signals.get("company_followed"):
        pts += cfg["company_followed"]["followed"]

    # Company in your search history
    if signals.get("company_in_searches"):
        pts += cfg["company_in_searches"]["found"]

    # Company size/industry match from enrichment
    enrichment = profile.get("enrichment") or {}
    if enrichment.get("company_size"):
        pts += cfg["company_size_match"]["target_size"]

    return min(pts, 100)


def score_timing(profile):
    """Dimension 6: Timing & Opportunity (0-50 pts).
    Connection recency + unreplied inbound messages.
    """
    cfg = WEIGHTS["dimensions"]["timing_opportunity"]["sub_signals"]
    signals = profile.get("signals", {})
    pts = 0

    # Connection recency
    tenure = signals.get("connection_tenure_days", 99999)
    for threshold, score in sorted(cfg["connection_recency"]["thresholds_days"].items(), key=lambda x: int(x[0])):
        if tenure <= int(threshold):
            pts += score
            break

    # Unreplied inbound (they sent invite with message, check if you replied)
    if signals.get("has_inbound_invite") and signals.get("invite_has_message"):
        # If no messages exchanged after invite, it's unreplied
        if signals.get("message_count", 0) == 0:
            invite_days = signals.get("connection_tenure_days", 999)
            for threshold, score in sorted(cfg["unreplied_inbound"]["thresholds_days"].items(), key=lambda x: int(x[0])):
                if invite_days <= int(threshold):
                    pts += score
                    break

    return min(pts, 50)


def score_profile(profile):
    """Calculate all dimension scores and total for a single profile.
    Updates the profile dict in-place with scores and tier.
    """
    scores = {
        "role_fit": score_role_fit(profile),
        "relationship": score_relationship(profile),
        "advocacy": score_advocacy(profile),
        "engagement": score_engagement(profile),
        "company_intel": score_company_intel(profile),
        "timing": score_timing(profile),
    }
    scores["total"] = sum(scores.values())

    # Assign tier
    tier = "D"
    for tier_name, tier_cfg in sorted(WEIGHTS["tiers"].items(), key=lambda x: x[1]["min_score"], reverse=True):
        if scores["total"] >= tier_cfg["min_score"]:
            tier = tier_name
            break

    profile["scores"] = scores
    profile["tier"] = tier
    return profile


def score_all_profiles(profiles):
    """Score all profiles. Modifies profiles in-place."""
    print(f"Scoring {len(profiles)} profiles...")
    for p in profiles:
        score_profile(p)

    # Distribution summary
    tiers = {}
    for p in profiles:
        t = p["tier"]
        tiers[t] = tiers.get(t, 0) + 1

    print("Score distribution:")
    for t in ["S", "A", "B", "C", "D"]:
        count = tiers.get(t, 0)
        label = WEIGHTS["tiers"][t]["label"]
        print(f"  {t} ({label}): {count}")

    return profiles
