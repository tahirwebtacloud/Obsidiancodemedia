# SOP: Identify Viral LinkedIn Content

## Goal
Discover high-performing videos and posts on LinkedIn to identify trends and viral hooks.

## Inputs
- `niche`: Industry or topic (e.g., "Real Estate AI", "SaaS Growth").
- `content_type`: [Video, Post, Carousel].

## Steps
1. **Search & Scrape**: Use Apify or similar tools to search LinkedIn for the top posts in the last 7-30 days based on the `niche`.
2. **Metric Filtering**: Focus on content with a high "Engagement Rate" (engagement relative to follower count, if available) or raw high counts.
3. **Pattern Extraction**: Identify the "Visual Hook" (for videos) or "Text Hook" (for posts) that triggered the virality.
4. **Logging**: Save the URLs and patterns to `.tmp/viral_trends.json`.

## Output
- `viral_patterns`: A list of successful hooks and topics.

## Execution Tool
- `execution/identify_viral.py`
