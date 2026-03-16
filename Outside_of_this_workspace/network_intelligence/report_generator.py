import datetime
import os
import json
from collections import defaultdict

from .data_loader import REPORTS_DIR, PROCESSED_DIR


def generate_master_report(profiles, company_clusters, segment_summaries):
    """Generate the master NETWORK_INTELLIGENCE_REPORT.md.

    This is the main output - an executive-level analysis with actionable tiers.
    """
    output_path = os.path.join(REPORTS_DIR, "NETWORK_INTELLIGENCE_REPORT.md")
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Pre-compute stats
    total = len(profiles)
    tier_counts = defaultdict(int)
    seniority_counts = defaultdict(int)
    industry_counts = defaultdict(int)
    relationship_counts = defaultdict(int)

    for p in profiles:
        tier_counts[p.get("tier", "D")] += 1
        seniority_counts[p.get("seniority_tier", "OTHER")] += 1
        for ind in p.get("industry_verticals", []):
            industry_counts[ind] += 1
        relationship_counts[p.get("relationship_type", "COLD")] += 1

    # Sort profiles by score descending
    sorted_profiles = sorted(profiles, key=lambda p: p.get("scores", {}).get("total", 0), reverse=True)

    with open(output_path, 'w') as f:
        f.write("# Network Intelligence Report\n")
        f.write(f"**Generated:** {datetime.date.today()} | **Connections Analyzed:** {total}\n\n")
        f.write("---\n\n")

        # Executive Summary
        f.write("## Executive Summary\n\n")
        f.write("### Score Distribution\n")
        tier_labels = {"S": "Champion", "A": "Hot Prospect", "B": "Warm Lead", "C": "Aware", "D": "Unknown"}
        tier_emojis = {"S": "👑", "A": "🔥", "B": "☀️", "C": "💤", "D": "❄️"}
        for t in ["S", "A", "B", "C", "D"]:
            count = tier_counts.get(t, 0)
            pct = round(count / total * 100, 1) if total else 0
            f.write(f"- {tier_emojis[t]} **Tier {t} ({tier_labels[t]}):** {count} ({pct}%)\n")
        f.write("\n")

        # Seniority breakdown
        f.write("### Seniority Breakdown\n")
        for tier in ["C_SUITE", "VP", "DIRECTOR", "MANAGER", "INDIVIDUAL", "OTHER"]:
            count = seniority_counts.get(tier, 0)
            pct = round(count / total * 100, 1) if total else 0
            f.write(f"- **{tier}:** {count} ({pct}%)\n")
        f.write("\n")

        # Top industries
        f.write("### Top Industries\n")
        for ind, count in sorted(industry_counts.items(), key=lambda x: -x[1])[:8]:
            pct = round(count / total * 100, 1) if total else 0
            f.write(f"- **{ind}:** {count} ({pct}%)\n")
        f.write("\n")

        # Relationship types
        f.write("### Relationship Types\n")
        for rel in ["CHAMPION", "ADVOCATE", "ACTIVE_CONTACT", "WARM_CONTACT", "INBOUND_LEAD", "NEW_CONNECTION", "DORMANT", "COLD"]:
            count = relationship_counts.get(rel, 0)
            if count > 0:
                f.write(f"- **{rel}:** {count}\n")
        f.write("\n")

        f.write("---\n\n")

        # S-Tier Champions
        s_tier = [p for p in sorted_profiles if p.get("tier") == "S"]
        if s_tier:
            f.write(f"## 👑 S-Tier Champions ({len(s_tier)} connections)\n")
            f.write("> These are your highest-value relationships. Personal outreach, referral asks, co-creation opportunities.\n\n")
            for p in s_tier:
                _write_profile_entry(f, p, detailed=True)
            f.write("---\n\n")

        # A-Tier Hot Prospects
        a_tier = [p for p in sorted_profiles if p.get("tier") == "A"]
        if a_tier:
            f.write(f"## 🔥 A-Tier Hot Prospects ({len(a_tier)} connections)\n")
            f.write("> Priority DM targets. Phase 1 outreach. These people know you and have shown interest.\n\n")
            for p in a_tier:
                _write_profile_entry(f, p, detailed=True)
            f.write("---\n\n")

        # B-Tier Warm Leads
        b_tier = [p for p in sorted_profiles if p.get("tier") == "B"]
        if b_tier:
            f.write(f"## ☀️ B-Tier Warm Leads ({len(b_tier)} connections)\n")
            f.write("> Content targeting and Phase 2 nurture. Engage through posts before direct outreach.\n\n")
            for p in b_tier[:30]:  # Cap display at 30
                _write_profile_entry(f, p, detailed=False)
            if len(b_tier) > 30:
                f.write(f"\n*...and {len(b_tier) - 30} more B-tier connections. See network_profiles.json for full list.*\n\n")
            f.write("---\n\n")

        # ABM Company Clusters
        abm_clusters = [c for c in company_clusters if c["connection_count"] >= 3]
        if abm_clusters:
            f.write(f"## 🏢 ABM Company Clusters ({len(abm_clusters)} accounts)\n")
            f.write("> Multi-thread these accounts. Don't pitch individually - engage the cluster.\n\n")
            for cluster in abm_clusters[:15]:
                _write_cluster_entry(f, cluster)
            f.write("---\n\n")

        # Audience Segments
        if segment_summaries:
            f.write("## 🎯 Audience Segments for Content Targeting\n\n")
            f.write("| Segment | Count | Avg Score | Top Tier |\n")
            f.write("|---------|-------|-----------|----------|\n")
            for seg_name, summary in sorted(segment_summaries.items(), key=lambda x: -x[1]["count"]):
                tier_dist = summary.get("tier_distribution", {})
                top_tier_count = tier_dist.get("S", 0) + tier_dist.get("A", 0)
                f.write(f"| {seg_name} | {summary['count']} | {summary['avg_score']} | {top_tier_count} S/A |\n")
            f.write(f"\n*See `reports/audience_briefs/` for detailed per-segment content strategies.*\n\n")

        # Quick action items
        f.write("---\n\n")
        f.write("## Quick Actions\n\n")

        # Unreplied inbound leads
        unreplied = [p for p in profiles if p.get("relationship_type") == "INBOUND_LEAD" and p.get("signals", {}).get("message_count", 0) == 0]
        if unreplied:
            f.write(f"### 📬 Unreplied Inbound Messages ({len(unreplied)})\n")
            for p in unreplied[:10]:
                f.write(f"- **{p['full_name']}** ({p['position']} @ {p['company']}) - [Profile]({p['url']})\n")
            f.write("\n")

        # New connections to engage
        new_conns = [p for p in profiles if p.get("relationship_type") == "NEW_CONNECTION" and p.get("scores", {}).get("total", 0) > 100]
        if new_conns:
            new_conns.sort(key=lambda x: -x.get("scores", {}).get("total", 0))
            f.write(f"### 🆕 High-Value New Connections ({len(new_conns)})\n")
            for p in new_conns[:10]:
                score = p.get("scores", {}).get("total", 0)
                f.write(f"- **{p['full_name']}** ({p['position']}) - Score: {score} - [Profile]({p['url']})\n")
            f.write("\n")

        # Dormant advocates
        dormant_advocates = [p for p in profiles if p.get("relationship_type") == "DORMANT" and p.get("signals", {}).get("endorsed_you")]
        if dormant_advocates:
            f.write(f"### 😴 Dormant Advocates to Reactivate ({len(dormant_advocates)})\n")
            for p in dormant_advocates[:10]:
                f.write(f"- **{p['full_name']}** ({p['position']} @ {p['company']}) - Endorsed you. [Profile]({p['url']})\n")
            f.write("\n")

    print(f"Master report generated: {output_path}")
    return output_path


def _write_profile_entry(f, profile, detailed=False):
    """Write a single profile entry to the report."""
    scores = profile.get("scores", {})
    total = scores.get("total", 0)
    signals = profile.get("signals", {})

    # Build badges
    badges = []
    if signals.get("recommended_you"):
        badges.append("❤️ Super Fan")
    if signals.get("endorsed_you"):
        badges.append("🏆 Endorser")
    if signals.get("follows_you"):
        badges.append("👁️ Follower")
    if signals.get("they_reacted_to_you"):
        badges.append("⚡ Reactor")
    if signals.get("intent_keywords"):
        badges.append("💬 Intent")
    last_days = signals.get("last_message_days")
    if last_days is not None and last_days < 90:
        badges.append("🔥 Recent")

    badge_str = " ".join(f"`{b}`" for b in badges) if badges else ""

    f.write(f"### {total} pts | **{profile['full_name']}** {badge_str}\n")
    f.write(f"*{profile['position']} @ {profile['company']}*")
    if profile.get("url"):
        f.write(f" | [Profile]({profile['url']})")
    f.write("\n")

    if detailed:
        # Score breakdown
        f.write(f"> Role: {scores.get('role_fit', 0)} | Relationship: {scores.get('relationship', 0)} | Advocacy: {scores.get('advocacy', 0)} | Engagement: {scores.get('engagement', 0)} | Company: {scores.get('company_intel', 0)} | Timing: {scores.get('timing', 0)}\n")

        # Classification
        tags = []
        tags.append(profile.get("seniority_tier", ""))
        tags.extend(profile.get("industry_verticals", []))
        tags.append(profile.get("relationship_type", ""))
        tags.append(profile.get("engagement_level", ""))
        f.write(f"> Tags: {' / '.join(t for t in tags if t and t != 'OTHER')}\n")

        # Recent interactions
        interactions = profile.get("interactions", [])
        if interactions:
            f.write("> Recent:\n")
            for event in interactions[:3]:
                f.write(f">   - {event.get('date', '?')} | {event.get('type', '')} | {event.get('snippet', '')[:80]}\n")

        # Recommended action
        rel_type = profile.get("relationship_type", "COLD")
        action = _suggest_action(profile, rel_type)
        f.write(f"> **Action:** {action}\n")

    f.write("\n")


def _write_cluster_entry(f, cluster):
    """Write a company cluster entry."""
    f.write(f"### 🏰 {cluster['company']} ({cluster['connection_count']} connections)\n")
    f.write(f"**Avg Score:** {cluster['avg_score']} | **Industries:** {', '.join(cluster.get('industries', []))}\n")

    if cluster.get("company_followed"):
        f.write("*You follow this company*\n")

    for contact in cluster.get("contacts", [])[:5]:
        tier_emoji = {"S": "👑", "A": "🔥", "B": "☀️", "C": "💤", "D": "❄️"}.get(contact.get("tier", "D"), "")
        f.write(f"- {tier_emoji} **{contact['name']}** - {contact['position']} (Score: {contact['score']})\n")

    if len(cluster.get("contacts", [])) > 5:
        f.write(f"- *...and {len(cluster['contacts']) - 5} more*\n")

    f.write("\n")


def _suggest_action(profile, relationship_type):
    """Generate a recommended action based on profile data."""
    first = profile.get("first_name", "")
    company = profile.get("company", "")

    if relationship_type == "CHAMPION":
        return f"Ask {first} for a referral or co-creation opportunity. They've publicly endorsed you."
    elif relationship_type == "ADVOCATE":
        return f"Re-engage {first} with a personal update. Reference their endorsement/recommendation."
    elif relationship_type == "ACTIVE_CONTACT":
        return f"Deepen the relationship with {first}. Suggest a call or share exclusive content."
    elif relationship_type == "WARM_CONTACT":
        return f"Warm up {first} with a value-add message. Share relevant content they'd care about."
    elif relationship_type == "INBOUND_LEAD":
        return f"Respond to {first}'s inbound message immediately. They showed intent."
    elif relationship_type == "NEW_CONNECTION":
        return f"Send {first} a welcome message. Set the tone for the relationship."
    elif relationship_type == "DORMANT":
        return f"Reactivate with the 'Memory Lane' approach. Reference how you originally connected."
    else:
        return f"Nurture through content. Post material that would resonate with someone at {company}."


def export_json_database(profiles, company_clusters):
    """Export the full profile database as JSON."""
    output_path = os.path.join(PROCESSED_DIR, "network_profiles.json")
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    export_data = {
        "generated": str(datetime.date.today()),
        "total_profiles": len(profiles),
        "profiles": profiles,
        "company_clusters": company_clusters
    }

    with open(output_path, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)

    print(f"JSON database exported: {output_path}")
    return output_path


def export_csv(profiles):
    """Export flat CSV for Clay/CRM integration."""
    import csv

    output_path = os.path.join(PROCESSED_DIR, "network_intelligence_export.csv")
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    headers = [
        "First Name", "Last Name", "Title", "Company", "LinkedIn URL", "Email",
        "Score", "Tier", "Seniority", "Industries", "Relationship Type",
        "Engagement Level", "Segments", "Product Segment", "Last Interaction",
        "Recommended Action"
    ]

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for p in sorted(profiles, key=lambda x: -x.get("scores", {}).get("total", 0)):
            action = _suggest_action(p, p.get("relationship_type", "COLD"))
            writer.writerow([
                p.get("first_name", ""),
                p.get("last_name", ""),
                p.get("position", ""),
                p.get("company", ""),
                p.get("url", ""),
                p.get("email", ""),
                p.get("scores", {}).get("total", 0),
                p.get("tier", "D"),
                p.get("seniority_tier", "OTHER"),
                "; ".join(p.get("industry_verticals", [])),
                p.get("relationship_type", "COLD"),
                p.get("engagement_level", "PASSIVE"),
                "; ".join(p.get("segments", [])),
                p.get("product_segment", ""),
                p.get("signals", {}).get("last_message_date", ""),
                action
            ])

    print(f"CSV export generated: {output_path}")
    return output_path
