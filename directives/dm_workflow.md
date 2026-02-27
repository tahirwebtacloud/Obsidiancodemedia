# SOP: Direct Message (DM) Workflow

## Goal
Automate personalized outreach on LinkedIn to foster engagement and lead generation.

## Inputs
- `target_profile`: LinkedIn profile URL or name.
- `context`: Reason for reaching out (e.g., "Mutual interest in AI", "Reply to their post").

## Steps
1. **Profile Personalization**: Scan the target profile for recent posts, achievements, or common interests.
2. **Drafting**: Use the "High-Performing Voice" (street-smart/human) to draft a message that is:
    - Short (max 50 words).
    - Curiosity-based.
    - Non-salesy.
3. **Approval/Sending**: Log the draft to Google Sheets for approval before sending via an automation tool (like a LinkedIn automation API or manual copy-paste).

## Output
- `dm_draft`: Personalized message stored in Google Sheets/`.tmp/dm_log.json`.

## Execution Tool
- `execution/dm_automation.py`
