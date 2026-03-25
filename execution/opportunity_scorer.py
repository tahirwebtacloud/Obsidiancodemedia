"""
Opportunity Scorer Module
Scores LinkedIn connections (without existing DM threads) by ICP fit,
role seniority, niche relevance, and recency to surface untapped prospects.

Rule-based scoring — no LLM calls, fast enough for 3000+ connections.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class OpportunityResult:
    """Scored opportunity for a non-DM connection."""
    full_name: str
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    position: str = ""
    profile_url: str = ""
    connected_on: str = ""
    opportunity_score: int = 0     # 0-100
    reason: str = ""
    seniority_tier: str = ""       # c_level, vp, director, manager, ic, unknown
    recommended_opener: str = ""
    scoring_breakdown: Dict = field(default_factory=dict)


# ── Seniority keywords (ordered by rank) ─────────────────────────────
_SENIORITY_MAP = {
    "c_level": {
        "keywords": [
            r"\bceo\b", r"\bcto\b", r"\bcfo\b", r"\bcmo\b", r"\bcoo\b", r"\bcio\b",
            r"\bcpo\b", r"\bcro\b", r"\bchief\b",
            r"\bfounder\b", r"\bco-founder\b", r"\bcofounder\b",
            r"\bowner\b", r"\bpartner\b", r"\bmanaging director\b",
        ],
        "score": 30,
    },
    "vp": {
        "keywords": [
            r"\bvp\b", r"\bvice president\b", r"\bsvp\b", r"\bevp\b",
            r"\bhead of\b", r"\bgm\b", r"\bgeneral manager\b",
        ],
        "score": 25,
    },
    "director": {
        "keywords": [
            r"\bdirector\b", r"\bsenior director\b", r"\bgroup director\b",
            r"\bassociate director\b",
        ],
        "score": 20,
    },
    "manager": {
        "keywords": [
            r"\bmanager\b", r"\bteam lead\b", r"\blead\b", r"\bprincipal\b",
            r"\bsenior manager\b",
        ],
        "score": 12,
    },
    "ic": {
        "keywords": [
            r"\bengineer\b", r"\banalyst\b", r"\bconsultant\b", r"\bspecialist\b",
            r"\bdesigner\b", r"\bdeveloper\b", r"\bcoordinator\b", r"\bassociate\b",
        ],
        "score": 5,
    },
}


def _detect_seniority(title: str) -> tuple:
    """Return (tier, score) based on title keywords."""
    title_lower = title.lower()
    for tier, cfg in _SENIORITY_MAP.items():
        for pattern in cfg["keywords"]:
            if re.search(pattern, title_lower):
                return tier, cfg["score"]
    return "unknown", 2


def _score_icp_fit(position: str, company: str, icp_keywords: List[str]) -> int:
    """Score 0-25 based on how well title/company match ICP keywords."""
    if not icp_keywords:
        return 5  # default mild score when no ICP defined
    combined = f"{position} {company}".lower()
    matches = sum(1 for kw in icp_keywords if kw.lower() in combined)
    return min(25, matches * 8)


def _score_recency(connected_on: str) -> int:
    """Score 0-15 based on how recently the person connected."""
    if not connected_on:
        return 3
    try:
        # LinkedIn format varies: "01 Jan 2024", "2024-01-01", etc.
        for fmt in ("%d %b %Y", "%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y"):
            try:
                dt = datetime.strptime(connected_on.strip(), fmt)
                break
            except ValueError:
                continue
        else:
            return 3
        days_ago = (datetime.now() - dt).days
        if days_ago <= 30:
            return 15
        if days_ago <= 90:
            return 12
        if days_ago <= 180:
            return 8
        if days_ago <= 365:
            return 5
        return 2
    except Exception:
        return 3


def _score_niche_relevance(position: str, company: str, niche_keywords: List[str]) -> int:
    """Score 0-20 based on niche/industry relevance."""
    if not niche_keywords:
        return 5
    combined = f"{position} {company}".lower()
    matches = sum(1 for kw in niche_keywords if kw.lower() in combined)
    return min(20, matches * 7)


def _generate_opener(first_name: str, position: str, company: str, seniority_tier: str, reason: str) -> str:
    """Generate a recommended first-touch opener based on scoring context."""
    name = first_name or "there"

    if seniority_tier == "c_level":
        if company:
            return f"Hi {name}, I noticed you're leading {company}. I've been following the space closely and had a quick thought on [specific value angle] — worth a 5-min chat?"
        return f"Hi {name}, as a fellow founder/executive, I wanted to share a quick observation about [relevant trend]. Would love your take on it."

    if seniority_tier == "vp":
        return f"Hi {name}, your work as {position or 'a leader'}{' at ' + company if company else ''} caught my eye. I had a specific idea around [outcome they care about] — open to a quick exchange?"

    if seniority_tier == "director":
        return f"Hi {name}, we're connected but haven't chatted yet. Given your role{' at ' + company if company else ''}, I think there's a relevant overlap — mind if I share a quick thought?"

    if seniority_tier == "manager":
        return f"Hi {name}, noticed your background in {position or 'your field'} and thought there might be a natural connection point. Quick question for you — [specific question]?"

    return f"Hi {name}, we've been connected for a while but never chatted. I came across something relevant to {company or 'your work'} and wanted to share — open to it?"


def score_connections(
    connections: List[Any],
    existing_thread_names: set,
    user_context: Dict = None,
    top_n: int = 100,
) -> List[OpportunityResult]:
    """
    Score all connections that DON'T have an existing message thread.

    Args:
        connections: List of LinkedInConnection dataclass instances
        existing_thread_names: Set of normalized names that already have CRM contacts/threads
        user_context: Dict with 'persona' and 'products_services' for ICP matching
        top_n: Number of top opportunities to return

    Returns:
        Sorted list of OpportunityResult (highest score first)
    """
    user_context = user_context or {}
    persona = user_context.get("persona") or {}
    if not isinstance(persona, dict):
        persona = {}

    # Build ICP and niche keyword lists from persona
    icp_raw = str(persona.get("target_icp", "") or "")
    expertise_areas = persona.get("expertise_areas", []) or []
    core_skills = persona.get("core_skills", []) or []
    industry = str(persona.get("industry", "") or "")

    # Tokenize ICP into keywords
    icp_keywords = [w.strip() for w in re.split(r"[,;|/]", icp_raw) if len(w.strip()) > 2]
    niche_keywords = list(set(
        [w.strip().lower() for w in expertise_areas if w.strip()] +
        [w.strip().lower() for w in core_skills if w.strip()] +
        ([industry.lower()] if industry else [])
    ))

    # Products/services keywords
    products = user_context.get("products_services") or []
    for p in products:
        if isinstance(p, dict):
            name = str(p.get("name", "") or "").strip()
            if name and len(name) > 2:
                icp_keywords.append(name.lower())

    results = []

    for conn in connections:
        first = str(getattr(conn, "first_name", "") or "").strip()
        last = str(getattr(conn, "last_name", "") or "").strip()
        full_name = f"{first} {last}".strip()
        position = str(getattr(conn, "position", "") or "").strip()
        company = str(getattr(conn, "company", "") or "").strip()
        profile_url = str(getattr(conn, "profile_url", "") or "").strip()
        connected_on = str(getattr(conn, "connected_on", "") or "").strip()

        # Skip if already has a thread/CRM contact
        name_norm = full_name.lower()
        if name_norm in existing_thread_names:
            continue

        # Skip empty or placeholder names
        if not full_name or full_name.lower() in {"linkedin member", "unknown", ""}:
            continue

        # Skip connections without title (very low value for scoring)
        if not position:
            continue

        # Score components
        seniority_tier, seniority_score = _detect_seniority(position)
        icp_score = _score_icp_fit(position, company, icp_keywords)
        recency_score = _score_recency(connected_on)
        niche_score = _score_niche_relevance(position, company, niche_keywords)

        # Activity bonus: connections with both title AND company are more complete profiles
        completeness_bonus = 5 if (position and company) else 0

        total = min(100, seniority_score + icp_score + recency_score + niche_score + completeness_bonus)

        # Build reason
        reason_parts = []
        if seniority_tier in ("c_level", "vp", "director"):
            reason_parts.append(f"{seniority_tier.replace('_', '-').upper()} seniority")
        if icp_score >= 8:
            reason_parts.append("matches ICP profile")
        if niche_score >= 7:
            reason_parts.append("relevant niche/industry")
        if recency_score >= 12:
            reason_parts.append("recently connected")
        if completeness_bonus:
            reason_parts.append("complete profile")

        reason = f"{position}{' at ' + company if company else ''}"
        if reason_parts:
            reason += f" — {', '.join(reason_parts)}"

        opener = _generate_opener(first, position, company, seniority_tier, reason)

        results.append(OpportunityResult(
            full_name=full_name,
            first_name=first,
            last_name=last,
            company=company,
            position=position,
            profile_url=profile_url,
            connected_on=connected_on,
            opportunity_score=total,
            reason=reason,
            seniority_tier=seniority_tier,
            recommended_opener=opener,
            scoring_breakdown={
                "seniority": seniority_score,
                "icp_fit": icp_score,
                "recency": recency_score,
                "niche": niche_score,
                "completeness": completeness_bonus,
            },
        ))

    # Sort by score descending, take top_n
    results.sort(key=lambda x: x.opportunity_score, reverse=True)
    results = results[:top_n]

    print(f"[OpportunityScorer] Scored {len(results)} opportunities from "
          f"{len(connections)} connections (skipped {len(connections) - len(results)} with threads/no title)")

    return results
