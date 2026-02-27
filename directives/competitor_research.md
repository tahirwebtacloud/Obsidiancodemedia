# SOP: Competitor Research for LinkedIn Posts

## Goal
Identify high-performing LinkedIn posts within a specific niche/topic to serve as inspiration for new content.

## Inputs
- `topic`: The subject matter (e.g., "AI in Healthcare", "SaaS Growth Secrets").
- `post_type`: (Optional) The desired format (e.g., Single Image, Video, Article).

## Steps
1. **Search**: Use web search to find recent and popular LinkedIn posts related to the `topic`.
2. **Filter**: Focus on posts with high engagement (likes, comments, shares) and from reputable creators or companies in the field.
3. **Capture**: Save the following data for each relevant post:
    - Creator name
    - Post content (text)
    - Engagement metrics
    - Visual type (Image, Video, etc.)
    - URL (if available)

## Outputs
- A list of `research_items` stored in `.tmp/research_results.json`.

## Execution Tool
- `execution/research_competitors.py`
