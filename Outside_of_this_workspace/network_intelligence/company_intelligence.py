import pandas as pd
from collections import defaultdict


def build_company_clusters(profiles, data):
    """Group profiles by company and calculate ABM cluster metrics.

    Also enriches profiles with company-level signals:
    - abm_cluster_size
    - company_followed
    - company_in_searches

    Modifies profiles in-place and returns the cluster list.
    """
    company_follows = data.get("company_follows", pd.DataFrame())
    search_queries = data.get("search_queries", pd.DataFrame())

    # Build company -> profiles index
    company_map = defaultdict(list)
    for p in profiles:
        company = p.get("company", "").strip()
        if company and company.lower() not in ("", "nan", "self-employed", "freelance", "stealth mode", "confidential"):
            company_map[company].append(p)

    # Build sets for quick lookups
    followed_companies = set()
    if not company_follows.empty and 'Organization' in company_follows.columns:
        followed_companies = set(company_follows['Organization'].dropna().str.strip().str.lower())

    searched_terms = set()
    if not search_queries.empty and 'Search Query' in search_queries.columns:
        searched_terms = set(search_queries['Search Query'].dropna().str.strip().str.lower())

    # Enrich each profile with company signals
    for company, members in company_map.items():
        cluster_size = len(members)
        company_lower = company.lower()

        # Check if company is followed
        is_followed = company_lower in followed_companies

        # Check if company appears in search queries
        in_searches = any(company_lower in term or term in company_lower for term in searched_terms)

        for p in members:
            p["signals"]["abm_cluster_size"] = cluster_size
            p["signals"]["company_followed"] = is_followed
            p["signals"]["company_in_searches"] = in_searches

    # Build cluster summaries (only for companies with 2+ connections)
    clusters = []
    for company, members in company_map.items():
        if len(members) < 2:
            continue

        # Calculate cluster metrics
        scores = [p.get("scores", {}).get("total", 0) for p in members]
        avg_score = sum(scores) / len(scores) if scores else 0

        seniority_spread = {}
        for p in members:
            tier = p.get("seniority_tier", "OTHER")
            seniority_spread[tier] = seniority_spread.get(tier, 0) + 1

        industries = set()
        for p in members:
            industries.update(p.get("industry_verticals", []))
        industries.discard("OTHER")

        cluster = {
            "company": company,
            "connection_count": len(members),
            "avg_score": round(avg_score, 1),
            "max_score": max(scores) if scores else 0,
            "seniority_spread": seniority_spread,
            "industries": list(industries),
            "company_followed": any(p["signals"].get("company_followed") for p in members),
            "in_searches": any(p["signals"].get("company_in_searches") for p in members),
            "contacts": [
                {
                    "name": p["full_name"],
                    "position": p["position"],
                    "score": p.get("scores", {}).get("total", 0),
                    "tier": p.get("tier", "D"),
                    "seniority": p.get("seniority_tier", "OTHER"),
                    "url": p.get("url", "")
                }
                for p in sorted(members, key=lambda x: x.get("scores", {}).get("total", 0), reverse=True)
            ]
        }
        clusters.append(cluster)

    # Sort by connection count then avg score
    clusters.sort(key=lambda c: (-c["connection_count"], -c["avg_score"]))

    print(f"Found {len(clusters)} company clusters (2+ connections).")
    abm_count = sum(1 for c in clusters if c["connection_count"] >= 3)
    print(f"  ABM targets (3+ connections): {abm_count}")

    return clusters


def get_cluster_for_company(clusters, company_name):
    """Look up a specific company cluster by name."""
    name_lower = company_name.lower().strip()
    for c in clusters:
        if c["company"].lower().strip() == name_lower:
            return c
    return None
