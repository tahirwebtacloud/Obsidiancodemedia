---
name: linkedin_analyst
description: Analyzes your broader LinkedIn network data for strategic insights.
license: MIT
---

# LinkedIn Analyst Skill

## Overview
This skill goes beyond simple "Lead Generation" to analyze the *structure* and *hidden signals* within your network. It helps you uncover opportunities that are already sitting in your data.

## Capabilities

### 1. Network Depth Analysis (`analyze_network_depth.py`)
This script performs a deep dive into your `Invitations.csv` and `Connections.csv`.

*   **The Inbound Sweeper**: Scans for pending/accepted connection requests where the person *sent you a message*. These are often ignored but represent your warmest leads.
*   **The ABM Radar**: Clusters your connections by Company. If you know >3 people at "Company X", it flags this as an Account-Based Marketing (ABM) opportunity.

#### Usage
```bash
python3 skills/linkedin_analyst/analyze_network_depth.py
```

#### Output
*   Generates **`NETWORK_DEPTH_REPORT.md`**.
*   Section 1: **Inbound Leads** (with drafted replies).
*   Section 2: **ABM Clusters** (with multi-thread outreach strategy).

---

## Requirements
*   `Linkedin Data/Invitations.csv`
*   `Linkedin Data/Connections.csv`
