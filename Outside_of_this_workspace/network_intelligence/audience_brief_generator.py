import os
import datetime

from .data_loader import REPORTS_DIR


def generate_audience_briefs(segment_summaries):
    """Generate per-segment audience brief markdown files.

    Creates reports/audience_briefs/[SEGMENT_NAME].md for each segment.
    """
    briefs_dir = os.path.join(REPORTS_DIR, "audience_briefs")
    os.makedirs(briefs_dir, exist_ok=True)

    generated = []

    for seg_name, summary in segment_summaries.items():
        filename = seg_name.lower().replace(" ", "_").replace("&", "and").replace("/", "_") + ".md"
        filepath = os.path.join(briefs_dir, filename)

        with open(filepath, 'w') as f:
            f.write(f"# Audience Brief: {seg_name}\n")
            f.write(f"**Generated:** {datetime.date.today()}\n\n")
            f.write(f"*{summary.get('description', '')}*\n\n")
            f.write("---\n\n")

            # Overview
            f.write("## Overview\n")
            f.write(f"- **Total Members:** {summary['count']}\n")
            f.write(f"- **Average Network Score:** {summary['avg_score']} / 1000\n\n")

            # Seniority distribution
            seniority = summary.get("seniority_distribution", {})
            if seniority:
                f.write("### Seniority Distribution\n")
                for tier in ["C_SUITE", "VP", "DIRECTOR", "MANAGER", "INDIVIDUAL", "OTHER"]:
                    count = seniority.get(tier, 0)
                    if count > 0:
                        pct = round(count / summary['count'] * 100, 1)
                        f.write(f"- **{tier}:** {count} ({pct}%)\n")
                f.write("\n")

            # Tier distribution
            tier_dist = summary.get("tier_distribution", {})
            if tier_dist:
                f.write("### Score Tiers\n")
                tier_labels = {"S": "Champion", "A": "Hot", "B": "Warm", "C": "Aware", "D": "Unknown"}
                for t in ["S", "A", "B", "C", "D"]:
                    count = tier_dist.get(t, 0)
                    if count > 0:
                        f.write(f"- **Tier {t} ({tier_labels[t]}):** {count}\n")
                f.write("\n")

            # Top companies
            top_companies = summary.get("top_companies", [])
            if top_companies:
                f.write("### Top Companies\n")
                for company, count in top_companies:
                    f.write(f"- **{company}** ({count} members)\n")
                f.write("\n")

            # Your relationship with them
            f.write("---\n\n")
            f.write("## Your Relationship With This Segment\n\n")

            top_contacts = summary.get("top_contacts", [])
            if top_contacts:
                relationship_counts = {}
                for c in top_contacts:
                    rel = c.get("relationship", "COLD")
                    relationship_counts[rel] = relationship_counts.get(rel, 0) + 1

                for rel, count in sorted(relationship_counts.items(), key=lambda x: -x[1]):
                    f.write(f"- **{rel}:** {count} in top 10\n")
                f.write("\n")

            # Content strategy
            strategy = summary.get("content_strategy", {})
            if strategy:
                f.write("---\n\n")
                f.write("## Content Strategy\n\n")

                topics = strategy.get("topics", [])
                if topics:
                    f.write("### Topics That Resonate\n")
                    for topic in topics:
                        f.write(f"- {topic}\n")
                    f.write("\n")

                tone = strategy.get("tone", "")
                if tone:
                    f.write(f"### Tone\n{tone}\n\n")

                cta = strategy.get("cta_style", "")
                if cta:
                    f.write(f"### Best CTA Style\n{cta}\n\n")

                avoid = strategy.get("avoid", [])
                if avoid:
                    f.write("### Avoid\n")
                    for item in avoid:
                        f.write(f"- {item}\n")
                    f.write("\n")

            # Top contacts to nurture
            if top_contacts:
                f.write("---\n\n")
                f.write("## Top 10 Contacts to Nurture\n\n")
                f.write("| # | Name | Position | Company | Score | Tier | Relationship |\n")
                f.write("|---|------|----------|---------|-------|------|-------------|\n")
                for i, c in enumerate(top_contacts, 1):
                    f.write(f"| {i} | **{c['name']}** | {c['position']} | {c['company']} | {c['score']} | {c['tier']} | {c['relationship']} |\n")
                f.write("\n")

        generated.append(filepath)

    print(f"Generated {len(generated)} audience briefs in {briefs_dir}/")
    return generated
