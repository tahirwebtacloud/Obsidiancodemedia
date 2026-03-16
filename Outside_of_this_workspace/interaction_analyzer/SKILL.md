---
name: Interaction Analyzer
description: Advanced lead qualification that scores leads based on role fit, interaction recency, advocacy (endorsements), and contextual intent patterns in messages.
tags: [analysis, lead-gen, linkedin, scoring]
---

# Interaction Analyzer Skill

> **Note:** For comprehensive network analysis, see `SKILLS/network_intelligence/` which supersedes this skill with a 0-1000 scoring model across 6 dimensions (vs the 0-100 / 5-signal model below). This skill remains useful for quick intent-only scoring.

This skill implements the **"Obsidian Intent Score"**, a proprietary scoring model to identify high-potential leads hidden in your network. It goes beyond simple job title matching by analyzing *behavioral* signals in your exported LinkedIn data.

## Scoring Model

The skill calculates a verified Intent Score (0-100) for every connection:

| Signal | Source | Weight | Meaning |
| :--- | :--- | :--- | :--- |
| **Role Fit** | `config/products.json` | **50 pts** | Matches your Ideal Customer Profile (ICP). |
| **Advocate** | `Endorsement_Received_Info.csv` | **+20 pts** | Has explicitly endorsed your skills. |
| **Super Fan** | `Recommendations_Received.csv` | **+30 pts** | Has written a public recommendation for you. |
| **Warmth** | `messages.csv` | **+15 pts** | Interacted within the last 90 days. |
| **Intent** | `messages.csv` Content | **+15 pts** | Mentioned keywords like "price", "help", "strategy". |

## How to Use

1.  **Ensure Data Exists:**
    *   `Linkedin Data/Connections.csv`
    *   `Linkedin Data/messages.csv`
    *   `Linkedin Data/Endorsement_Received_Info.csv`
    *   `Linkedin Data/Recommendations_Received.csv`
    *   *(Note: These are standard files in a full LinkedIn Data Export)*

2.  **Configure Products:**
    *   Edit `skills/lead_generator/config/products.json` to define your Target Roles (Keywords) and Pitch Hooks. This skill reuses the same configuration!

3.  **Run the Analysis:**
    ```bash
    python3 skills/interaction_analyzer/analyze_intent.py
    ```

4.  **Review Report:**
    *   Open `ADVANCED_LEAD_REPORT.md` at the root of your project.
    *   Look for the **`🏆 Endorser`** or **`💬 Intent`** badges to find your "Hidden Gems".

## Output Example

```markdown
### 🟢 85 pts | **Jane Doe** `🏆 Endorser` `🔥 Recent`
*CEO @ TechCorp*
> **Draft:** "Hey Jane, thanks again for believing in my work (saw the endorsement!). We just launched..."
```
