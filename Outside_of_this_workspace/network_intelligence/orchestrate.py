#!/usr/bin/env python3
"""Network Intelligence - Obsidian Network Score

Main orchestrator for the network intelligence skill.
Processes all LinkedIn data exports to build multi-dimensional profiles,
score connections on a 0-1000 scale, and generate actionable intelligence.

Usage:
    python3 SKILLS/network_intelligence/orchestrate.py
    python3 SKILLS/network_intelligence/orchestrate.py --enrich clay
    python3 SKILLS/network_intelligence/orchestrate.py --research "https://linkedin.com/in/someone"
    python3 SKILLS/network_intelligence/orchestrate.py --company "Acme Corp"
    python3 SKILLS/network_intelligence/orchestrate.py --export-only
"""

import argparse
import sys
import os
import time

# Add parent directories to path so imports work when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Use direct imports since we may be run as a script
from network_intelligence import data_loader
from network_intelligence import profile_builder
from network_intelligence import scoring_engine
from network_intelligence import company_intelligence
from network_intelligence import audience_segmenter
from network_intelligence import report_generator
from network_intelligence import audience_brief_generator
from network_intelligence import enrichment


def run_full_analysis():
    """Execute the complete network intelligence pipeline."""
    start = time.time()

    print("=" * 60)
    print("  NETWORK INTELLIGENCE - Obsidian Network Score")
    print("=" * 60)
    print()

    # Phase 1: Load all data
    data = data_loader.load_all()

    connections = data.get("connections")
    if connections is None or connections.empty:
        print("ERROR: No connections data found. Ensure data/raw/Connections.csv exists.")
        return None, None, None

    print()

    # Phase 2: Build profiles (cross-reference all data sources)
    profiles = profile_builder.build_all_profiles(data)
    if not profiles:
        print("ERROR: No profiles built.")
        return None, None, None

    print()

    # Phase 3: Company intelligence (enriches profiles with ABM signals)
    clusters = company_intelligence.build_company_clusters(profiles, data)

    print()

    # Phase 4: Score all profiles (must come after company_intelligence enrichment)
    scoring_engine.score_all_profiles(profiles)

    print()

    # Phase 5: Audience segmentation
    segment_summaries = audience_segmenter.assign_segments(profiles, clusters)

    print()

    # Phase 6: Generate outputs
    print("Generating outputs...")
    report_generator.generate_master_report(profiles, clusters, segment_summaries)
    audience_brief_generator.generate_audience_briefs(segment_summaries)
    report_generator.export_json_database(profiles, clusters)
    report_generator.export_csv(profiles)

    elapsed = round(time.time() - start, 1)
    print()
    print("=" * 60)
    print(f"  COMPLETE ({elapsed}s)")
    print(f"  Profiles: {len(profiles)}")
    print(f"  Company Clusters: {len(clusters)}")
    print(f"  Audience Segments: {len(segment_summaries)}")
    print()
    print("  Outputs:")
    print("    reports/NETWORK_INTELLIGENCE_REPORT.md")
    print("    reports/audience_briefs/*.md")
    print("    data/processed/network_profiles.json")
    print("    data/processed/network_intelligence_export.csv")
    print("=" * 60)

    return profiles, clusters, segment_summaries


def run_enrichment(profiles, mode="clay"):
    """Run external enrichment on top-tier profiles."""
    if mode == "clay":
        enrichment.enrich_via_clay(profiles)
    else:
        print(f"Unknown enrichment mode: {mode}")


def run_research(profiles, clusters, url):
    """Deep-dive research on a specific profile."""
    enrichment.research_profile(url, profiles)


def run_company_research(profiles, clusters, company_name):
    """Deep-dive research on a company."""
    enrichment.research_company(company_name, profiles, clusters)


def run_export_only():
    """Quick run that only exports data without generating reports."""
    data = data_loader.load_all()
    profiles = profile_builder.build_all_profiles(data)
    clusters = company_intelligence.build_company_clusters(profiles, data)
    scoring_engine.score_all_profiles(profiles)

    report_generator.export_json_database(profiles, clusters)
    report_generator.export_csv(profiles)
    print("Export complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Network Intelligence - Obsidian Network Score",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Full analysis:     python3 orchestrate.py
  Clay enrichment:   python3 orchestrate.py --enrich clay
  Profile research:  python3 orchestrate.py --research "https://linkedin.com/in/someone"
  Company research:  python3 orchestrate.py --company "Acme Corp"
  Export only:       python3 orchestrate.py --export-only
        """
    )

    parser.add_argument('--enrich', type=str, choices=['clay'],
                        help='Run external enrichment (clay)')
    parser.add_argument('--research', type=str,
                        help='Deep-dive on a LinkedIn profile URL')
    parser.add_argument('--company', type=str,
                        help='Deep-dive on a company name')
    parser.add_argument('--export-only', action='store_true',
                        help='Only export JSON/CSV, skip report generation')

    args = parser.parse_args()

    # Export-only mode
    if args.export_only:
        run_export_only()
        return

    # Always run full analysis first
    profiles, clusters, segments = run_full_analysis()

    if profiles is None:
        sys.exit(1)

    # Optional: enrichment
    if args.enrich:
        print()
        run_enrichment(profiles, args.enrich)

    # Optional: profile research
    if args.research:
        print()
        run_research(profiles, clusters, args.research)

    # Optional: company research
    if args.company:
        print()
        run_company_research(profiles, clusters, args.company)


if __name__ == "__main__":
    main()
