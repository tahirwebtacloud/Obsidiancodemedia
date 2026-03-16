import json
import os
import datetime

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")


def _load_enrichment_config():
    with open(os.path.join(CONFIG_DIR, "enrichment_config.json"), 'r') as f:
        return json.load(f)


def _get_api_key(env_var):
    """Load API key from environment."""
    key = os.environ.get(env_var, "")
    if not key:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            key = os.environ.get(env_var, "")
        except ImportError:
            pass
    return key


def enrich_via_clay(profiles, tier_filter=None):
    """Push top-tier profiles to Clay for enrichment.

    Requires CLAY_API_KEY in .env. If not available, exports CSV instead.
    """
    config = _load_enrichment_config().get("clay", {})

    if not config.get("enabled"):
        print("Clay enrichment is disabled. Enable in config/enrichment_config.json")
        print("Exporting Clay-ready CSV instead...")
        return _export_clay_csv(profiles, tier_filter)

    api_key = _get_api_key(config.get("api_key_env", "CLAY_API_KEY"))
    if not api_key:
        print(f"No API key found for {config.get('api_key_env')}. Exporting CSV instead...")
        return _export_clay_csv(profiles, tier_filter)

    # Filter profiles by tier
    if tier_filter is None:
        tier_filter = config.get("tier_filter", ["S", "A"])
    filtered = [p for p in profiles if p.get("tier") in tier_filter]

    max_records = config.get("max_records_per_run", 100)
    filtered = filtered[:max_records]

    print(f"Clay API enrichment for {len(filtered)} profiles (tiers: {tier_filter})...")

    # TODO: Implement actual Clay API calls when API key is provided
    # For now, export CSV that can be manually uploaded
    print("Note: Direct Clay API integration requires Clay API access.")
    print("Exporting Clay-ready CSV for manual upload...")
    return _export_clay_csv(profiles, tier_filter)


def _export_clay_csv(profiles, tier_filter=None):
    """Export profiles in Clay-importable CSV format."""
    import csv

    if tier_filter is None:
        tier_filter = ["S", "A"]
    filtered = [p for p in profiles if p.get("tier") in tier_filter]

    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "processed")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "clay_enrichment_export.csv")

    headers = [
        "First Name", "Last Name", "Title", "Company",
        "LinkedIn Profile", "Obsidian Score", "Tier", "Segment"
    ]

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for p in filtered:
            writer.writerow([
                p.get("first_name", ""),
                p.get("last_name", ""),
                p.get("position", ""),
                p.get("company", ""),
                p.get("url", ""),
                p.get("scores", {}).get("total", 0),
                p.get("tier", "D"),
                p.get("product_segment", "")
            ])

    print(f"Clay CSV exported: {output_path} ({len(filtered)} records)")
    return output_path


def research_profile(linkedin_url, profiles=None):
    """Deep-dive research on a specific LinkedIn profile.

    Uses Apify LinkedIn scraper if available, otherwise generates
    a research brief from existing data.
    """
    config = _load_enrichment_config().get("apify", {})

    # Find profile in existing data
    profile = None
    if profiles:
        for p in profiles:
            if p.get("url", "").rstrip('/') == linkedin_url.rstrip('/'):
                profile = p
                break

    if not config.get("enabled") or not _get_api_key(config.get("api_key_env", "")):
        print("Apify not configured. Generating research brief from local data...")
        return _generate_local_research_brief(profile, linkedin_url)

    api_key = _get_api_key(config.get("api_key_env", "APIFY_API_TOKEN"))

    try:
        from apify_client import ApifyClient
        client = ApifyClient(api_key)

        actor = config.get("profile_scraper_actor", "anchor/linkedin-profile-scraper")
        print(f"Running Apify actor: {actor}")

        run = client.actor(actor).call(run_input={
            "profileUrls": [linkedin_url],
            "proxy": {"useApifyProxy": True}
        })

        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if items:
            return _generate_enriched_research_brief(profile, items[0], linkedin_url)
        else:
            print("No data returned from Apify. Using local data.")
            return _generate_local_research_brief(profile, linkedin_url)

    except ImportError:
        print("apify_client not installed. Run: pip install apify-client")
        return _generate_local_research_brief(profile, linkedin_url)
    except Exception as e:
        print(f"Apify error: {e}")
        return _generate_local_research_brief(profile, linkedin_url)


def research_company(company_name, profiles=None, company_clusters=None):
    """Deep-dive research on a company using existing data and optionally Apify."""
    # Find cluster in existing data
    cluster = None
    if company_clusters:
        for c in company_clusters:
            if c["company"].lower().strip() == company_name.lower().strip():
                cluster = c
                break

    # Find all profiles at this company
    company_profiles = []
    if profiles:
        company_profiles = [p for p in profiles if p.get("company", "").lower().strip() == company_name.lower().strip()]

    return _generate_company_research_brief(company_name, cluster, company_profiles)


def _generate_local_research_brief(profile, linkedin_url):
    """Generate a research brief from local data only."""
    research_dir = os.path.join(REPORTS_DIR, "research")
    os.makedirs(research_dir, exist_ok=True)

    if profile:
        name = profile["full_name"].replace(" ", "_")
        filepath = os.path.join(research_dir, f"{name}.md")

        with open(filepath, 'w') as f:
            f.write(f"# Research Brief: {profile['full_name']}\n")
            f.write(f"**Generated:** {datetime.date.today()} | **Source:** Local LinkedIn Export\n\n")
            f.write("---\n\n")

            f.write("## Profile\n")
            f.write(f"- **Position:** {profile['position']}\n")
            f.write(f"- **Company:** {profile['company']}\n")
            f.write(f"- **LinkedIn:** {profile['url']}\n")
            f.write(f"- **Email:** {profile.get('email', 'N/A')}\n")
            f.write(f"- **Connected:** {profile.get('connected_on', 'Unknown')}\n\n")

            f.write("## Network Intelligence\n")
            f.write(f"- **Obsidian Score:** {profile.get('scores', {}).get('total', 0)} / 1000 (Tier {profile.get('tier', 'D')})\n")
            f.write(f"- **Seniority:** {profile.get('seniority_tier', 'Unknown')}\n")
            f.write(f"- **Industries:** {', '.join(profile.get('industry_verticals', []))}\n")
            f.write(f"- **Relationship:** {profile.get('relationship_type', 'Unknown')}\n")
            f.write(f"- **Engagement:** {profile.get('engagement_level', 'Unknown')}\n\n")

            scores = profile.get("scores", {})
            f.write("## Score Breakdown\n")
            f.write(f"| Dimension | Score |\n|---|---|\n")
            for dim in ["role_fit", "relationship", "advocacy", "engagement", "company_intel", "timing"]:
                f.write(f"| {dim.replace('_', ' ').title()} | {scores.get(dim, 0)} |\n")
            f.write("\n")

            interactions = profile.get("interactions", [])
            if interactions:
                f.write("## Interaction History\n")
                for event in interactions[:10]:
                    f.write(f"- **{event.get('date', '?')}** | {event.get('type', '')} ({event.get('direction', '')}) | {event.get('snippet', '')[:100]}\n")
                f.write("\n")

            f.write("## Enrichment Needed\n")
            f.write("To get deeper intelligence, enable Apify integration or manually research:\n")
            f.write(f"- Full work history and education\n")
            f.write(f"- Recent post topics and engagement patterns\n")
            f.write(f"- Company size, revenue, and tech stack\n")
            f.write(f"- Mutual connections and shared groups\n")

        print(f"Research brief generated: {filepath}")
        return filepath
    else:
        print(f"No profile found for {linkedin_url}")
        return None


def _generate_enriched_research_brief(profile, apify_data, linkedin_url):
    """Generate a research brief with Apify enrichment data."""
    research_dir = os.path.join(REPORTS_DIR, "research")
    os.makedirs(research_dir, exist_ok=True)

    name = apify_data.get("fullName", "Unknown").replace(" ", "_")
    filepath = os.path.join(research_dir, f"{name}.md")

    with open(filepath, 'w') as f:
        f.write(f"# Research Brief: {apify_data.get('fullName', 'Unknown')}\n")
        f.write(f"**Generated:** {datetime.date.today()} | **Source:** LinkedIn Export + Apify\n\n")
        f.write("---\n\n")

        f.write("## Profile\n")
        f.write(f"- **Headline:** {apify_data.get('headline', 'N/A')}\n")
        f.write(f"- **Location:** {apify_data.get('location', 'N/A')}\n")
        f.write(f"- **LinkedIn:** {linkedin_url}\n")
        f.write(f"- **Connections:** {apify_data.get('connectionsCount', 'N/A')}\n\n")

        if apify_data.get("summary"):
            f.write("## About\n")
            f.write(f"{apify_data['summary'][:500]}\n\n")

        experience = apify_data.get("experience", [])
        if experience:
            f.write("## Experience\n")
            for exp in experience[:5]:
                f.write(f"- **{exp.get('title', '')}** @ {exp.get('company', '')} ({exp.get('duration', '')})\n")
            f.write("\n")

        if profile:
            f.write("## Network Intelligence\n")
            f.write(f"- **Obsidian Score:** {profile.get('scores', {}).get('total', 0)} / 1000\n")
            f.write(f"- **Tier:** {profile.get('tier', 'D')}\n")
            f.write(f"- **Relationship:** {profile.get('relationship_type', 'Unknown')}\n\n")

    print(f"Enriched research brief generated: {filepath}")
    return filepath


def _generate_company_research_brief(company_name, cluster, company_profiles):
    """Generate a company research brief."""
    research_dir = os.path.join(REPORTS_DIR, "research", "companies")
    os.makedirs(research_dir, exist_ok=True)

    filename = company_name.replace(" ", "_").replace("/", "_").replace(".", "")[:50] + ".md"
    filepath = os.path.join(research_dir, filename)

    with open(filepath, 'w') as f:
        f.write(f"# Company Research: {company_name}\n")
        f.write(f"**Generated:** {datetime.date.today()}\n\n")
        f.write("---\n\n")

        f.write("## Network Presence\n")
        f.write(f"- **Your Connections:** {len(company_profiles)}\n")

        if cluster:
            f.write(f"- **Average Score:** {cluster.get('avg_score', 0)}\n")
            f.write(f"- **Industries:** {', '.join(cluster.get('industries', []))}\n")
            f.write(f"- **You Follow This Company:** {'Yes' if cluster.get('company_followed') else 'No'}\n")
            f.write(f"- **In Your Search History:** {'Yes' if cluster.get('in_searches') else 'No'}\n\n")

            seniority = cluster.get("seniority_spread", {})
            if seniority:
                f.write("### Seniority Spread\n")
                for tier, count in sorted(seniority.items()):
                    f.write(f"- **{tier}:** {count}\n")
                f.write("\n")

        if company_profiles:
            f.write("## Your Contacts\n\n")
            f.write("| Name | Position | Score | Tier | Relationship |\n")
            f.write("|------|----------|-------|------|-------------|\n")
            for p in sorted(company_profiles, key=lambda x: -x.get("scores", {}).get("total", 0)):
                f.write(f"| **{p['full_name']}** | {p['position']} | {p.get('scores', {}).get('total', 0)} | {p.get('tier', 'D')} | {p.get('relationship_type', 'COLD')} |\n")
            f.write("\n")

        f.write("## ABM Strategy\n")
        if len(company_profiles) >= 3:
            f.write(f"You have {len(company_profiles)} connections at {company_name}. Use a multi-thread approach:\n")
            f.write(f"1. Identify the decision maker (highest seniority)\n")
            f.write(f"2. Engage the champion (highest score)\n")
            f.write(f"3. Reference mutual connections in outreach\n")
            f.write(f"4. Consider a group lunch-and-learn or company-specific webinar\n")
        else:
            f.write(f"You have {len(company_profiles)} connection(s). Build more relationships before ABM approach.\n")

    print(f"Company research brief generated: {filepath}")
    return filepath
