---
name: Lead Generator
description: Automated skill for analyzing LinkedIn connections against Obsidian Logic products, calculating relationship 'warmth' from message history, and drafting segmented outreach.
---

# Lead Generator Skill

## Overview
This skill automates the process of identifying potential leads/partners from your LinkedIn network. It goes beyond simple title matching by analyzing your **Interaction History** (messages) to prioritize "Warm" leads over "Cold" ones.

## Prerequisites
- **Input Data**: 
    - `Linkedin Data/Connections.csv` (The network)
    - `Linkedin Data/messages.csv` (The history)
- **Script**: `skills/lead_generator/analyze_connections.py`

## Capabilities

### 1. Warmth Analysis
Matches every connection against your message history to assign a **Warmth Score**:
- **🔥 High**: Interaction within last 3 months.
- **☀️ Medium**: Interaction within last year.
- **❄️ Low**: Interaction > 1 year ago.
- **🧊 Cold**: No recorded interaction.

### 2. Solution Segmentation
Segments leads into three core Obsidian Logic buckets:
- **AI Audit Solution**: Targets CEOs, CFOs, Ops leaders. Pitch: "ROI of Automation".
- **Strategic Lead Gen**: Targets Agencies, Sales leaders. Pitch: "Automated Outbound".
- **Workflow Automation**: Targets COOs, Ops. Pitch: "Operational Efficiency".

## Usage
To generate the segmented report:
```bash
python3 skills/lead_generator/analyze_connections.py
```

## Output
- **File**: `LEAD_GEN_REPORT.md`
- **Content**: A segmented list of leads, grouped by product and then by likelihood to respond (warmth), with tailored message drafts for each.

## Updates and Configuration
To add new products or change targeting keywords, **do not edit the script**.
Instead, modify the configuration file:
`skills/lead_generator/config/products.json`

Format:
```json
"New Product Name": {
  "keywords": ["Target Title 1", "Target Title 2"],
  "negative_keywords": ["Exclude 1"],
  "value_prop": "your value proposition here",
  "pitch_hook": "Your outreach hook here",
  "resource": "Your Lead Magnet Name"
}
```
