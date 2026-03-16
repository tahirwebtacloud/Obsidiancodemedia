---
name: Network Intelligence
description: Multi-dimensional network profiling and scoring system. Analyzes all LinkedIn data exports to classify, score, and segment your entire network for targeted content and outreach.
tags: [analysis, network, scoring, segmentation, intelligence, linkedin]
---

# Network Intelligence Skill

## Overview
This skill builds a comprehensive intelligence database of your entire LinkedIn network. It goes far beyond simple title matching by cross-referencing **12 data sources** to produce a multi-dimensional profile for every connection.

Every connection gets:
- **Obsidian Network Score** (0-1000) across 6 dimensions
- **Seniority tier** (C-Suite through Individual Contributor)
- **Industry verticals** (Cybersecurity, AI, GovCon, etc.)
- **Relationship type** (Champion, Advocate, Active, Dormant, etc.)
- **Engagement level** (Super Engaged through Passive)
- **Interaction timeline** (chronological history of all touchpoints)
- **Audience segments** for content targeting

## Scoring Model: Obsidian Network Score (0-1000)

| Dimension | Max | What It Measures |
|---|---|---|
| Role Fit | 250 | Seniority + Industry + Product segment match |
| Relationship | 250 | Message recency/frequency/direction + Tenure + Invites + Endorsement reciprocity |
| Advocacy | 200 | Recommendations + Endorsements + Skill overlap + Social debt + Follows |
| Engagement | 150 | Intent keywords + Your reactions/comments + Their reactions to you |
| Company Intel | 100 | ABM cluster size + Company followed + Search history + Enrichment |
| Timing | 50 | Connection recency + Unreplied inbound messages |

### Score Tiers
- **S (700+):** Champion - Personal outreach, referral asks
- **A (500-699):** Hot Prospect - Priority DM, Phase 1 outreach
- **B (300-499):** Warm Lead - Content targeting, Phase 2 nurture
- **C (100-299):** Aware - Stay visible via content
- **D (0-99):** Unknown - Background

## Usage

### Full Analysis (No API Required)
```bash
python3 SKILLS/network_intelligence/orchestrate.py
```

### With Clay Enrichment
```bash
python3 SKILLS/network_intelligence/orchestrate.py --enrich clay
```

### Profile Deep-Dive
```bash
python3 SKILLS/network_intelligence/orchestrate.py --research "https://linkedin.com/in/someone"
```

### Company Research
```bash
python3 SKILLS/network_intelligence/orchestrate.py --company "Acme Corp"
```

### Export Only (No Reports)
```bash
python3 SKILLS/network_intelligence/orchestrate.py --export-only
```

## Data Sources
Consumes all from `data/raw/`: Connections, Messages, Endorsements (given + received), Recommendations (given + received), Invitations, Reactions, Comments, Company Follows, Member Follows, Search Queries. Plus surveillance report data.

## Outputs

| File | Purpose |
|---|---|
| `reports/NETWORK_INTELLIGENCE_REPORT.md` | Master report with tiered recommendations |
| `reports/audience_briefs/*.md` | Per-segment content strategy guides |
| `data/processed/network_profiles.json` | Full profile database (JSON) |
| `data/processed/network_intelligence_export.csv` | Clay/CRM-ready flat export |
| `reports/research/[Name].md` | Individual deep-dive (with --research) |
| `reports/research/companies/[Company].md` | Company deep-dive (with --company) |

## Configuration
All scoring weights, classification keywords, audience segments, and API settings are configurable in `config/`.

## Relationship to Existing Skills
This skill **orchestrates on top of** existing skills. It does not replace them:
- Reuses `lead_generator/config/products.json` for product segment matching
- Extends ABM clustering from `linkedin_analyst`
- Builds on scoring concepts from `interaction_analyzer`
- Uses Apify patterns from `surveillance_officer`
