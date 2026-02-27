# SOP: Rank and Analyze LinkedIn Posts

## Goal
Evaluate researched posts to identify the most successful structures, hooks, and themes.

## Inputs
- `research_items`: Content from `.tmp/research_results.json`.
- `user_topic`: The original topic provided by the user.

## Steps
1. **Relevance Check**: Compare each post to the `user_topic`.
2. **Engagement Analysis**: Weight the engagement metrics to score the post.
3. **Draft Synthesis**: Identify the "Hook", "Body Structure", and "Call to Action" of the top-ranked posts.
4. **Rank**: Selection of the top 3-5 posts that best align with the user's intent.

## Outputs
- `analysis_results`: A summary of structural patterns and the top-ranked post data in `.tmp/analysis.json`.

## Execution Tool
- `execution/rank_and_analyze.py`
