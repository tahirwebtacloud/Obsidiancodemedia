import json
import os
from collections import defaultdict

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")


def _load_segment_config():
    with open(os.path.join(CONFIG_DIR, "audience_segments.json"), 'r') as f:
        return json.load(f)["segments"]


SEGMENT_CONFIG = _load_segment_config()

# Seniority level mapping for comparison
SENIORITY_LEVELS = {
    "C_SUITE": 6, "VP": 5, "DIRECTOR": 4, "MANAGER": 3, "INDIVIDUAL": 2, "OTHER": 1
}


def _meets_seniority(profile, min_seniority):
    """Check if profile meets minimum seniority requirement."""
    profile_level = SENIORITY_LEVELS.get(profile.get("seniority_tier", "OTHER"), 1)
    min_level = SENIORITY_LEVELS.get(min_seniority, 1)
    return profile_level >= min_level


def _meets_industry(profile, required_industries):
    """Check if profile matches any of the required industries."""
    if "ANY" in required_industries:
        return True
    profile_industries = set(profile.get("industry_verticals", []))
    return bool(profile_industries & set(required_industries))


def _meets_title_keywords(profile, keywords):
    """Check if profile title contains any of the keywords."""
    if not keywords:
        return True
    position = profile.get("position", "").lower()
    return any(kw.lower() in position for kw in keywords)


def _meets_score(profile, min_score):
    """Check if profile meets minimum score threshold."""
    total = profile.get("scores", {}).get("total", 0)
    return total >= min_score


def assign_segments(profiles, company_clusters=None):
    """Assign each profile to matching audience segments.

    Each profile can belong to multiple segments. Updates profiles in-place
    with a 'segments' list and returns segment summary data.
    """
    print("Assigning audience segments...")

    # ABM cluster company set
    abm_companies = set()
    if company_clusters:
        for c in company_clusters:
            if c.get("connection_count", 0) >= 3:
                abm_companies.add(c["company"].lower().strip())

    segment_members = defaultdict(list)

    for p in profiles:
        matched_segments = []

        for seg_name, seg_config in SEGMENT_CONFIG.items():
            criteria = seg_config.get("criteria", {})

            # ABM segment has special criteria
            if "abm_cluster_min" in criteria:
                company = p.get("company", "").lower().strip()
                if company in abm_companies:
                    matched_segments.append(seg_name)
                continue

            # Standard criteria matching
            if not _meets_industry(p, criteria.get("industry", ["ANY"])):
                continue
            if not _meets_seniority(p, criteria.get("seniority_min", "OTHER")):
                continue
            if not _meets_title_keywords(p, criteria.get("title_keywords", [])):
                continue
            if not _meets_score(p, criteria.get("min_score", 0)):
                continue

            matched_segments.append(seg_name)

        p["segments"] = matched_segments

        for seg in matched_segments:
            segment_members[seg].append(p)

    # Build segment summaries
    summaries = {}
    for seg_name, members in segment_members.items():
        scores = [m.get("scores", {}).get("total", 0) for m in members]
        avg_score = sum(scores) / len(scores) if scores else 0

        seniority_dist = defaultdict(int)
        for m in members:
            seniority_dist[m.get("seniority_tier", "OTHER")] += 1

        tier_dist = defaultdict(int)
        for m in members:
            tier_dist[m.get("tier", "D")] += 1

        top_contacts = sorted(members, key=lambda x: x.get("scores", {}).get("total", 0), reverse=True)[:10]

        summaries[seg_name] = {
            "count": len(members),
            "avg_score": round(avg_score, 1),
            "seniority_distribution": dict(seniority_dist),
            "tier_distribution": dict(tier_dist),
            "top_companies": _top_companies(members),
            "content_strategy": SEGMENT_CONFIG[seg_name].get("content_strategy", {}),
            "description": SEGMENT_CONFIG[seg_name].get("description", ""),
            "top_contacts": [
                {
                    "name": c["full_name"],
                    "position": c["position"],
                    "company": c["company"],
                    "score": c.get("scores", {}).get("total", 0),
                    "tier": c.get("tier", "D"),
                    "relationship": c.get("relationship_type", "COLD")
                }
                for c in top_contacts
            ]
        }

    # Print summary
    print("Audience segments:")
    for seg_name in sorted(summaries.keys(), key=lambda s: summaries[s]["count"], reverse=True):
        s = summaries[seg_name]
        print(f"  {seg_name}: {s['count']} members (avg score: {s['avg_score']})")

    return summaries


def _top_companies(members, limit=5):
    """Get the most common companies in a segment."""
    company_counts = defaultdict(int)
    for m in members:
        company = m.get("company", "").strip()
        if company and company.lower() not in ("", "nan"):
            company_counts[company] += 1
    return sorted(company_counts.items(), key=lambda x: -x[1])[:limit]
