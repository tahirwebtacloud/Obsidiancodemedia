# SOP: Source Ingestion (YouTube, Blogs, News)

## Goal
Transform external content (YouTube videos, Obsidian blogs, News articles) into structured data for LinkedIn post generation.

## Inputs
- `source_url`: URL of the video, blog, or article.
- `source_type`: One of [YouTube, Blog, News].

## Steps
1. **Extraction**:
    - **YouTube**: Use Apify or a transcription library to get the video transcript and metadata (title, views).
    - **Blog**: Scrape the main content, headings, and key takeaways from the URL.
    - **News**: Extract the headline, summary, and primary facts.
2. **Summarization**: Use an LLM to condense the extracted content into a 200-word brief focusing on "Insights" and "Stats".
3. **Structured Storage**: Save the brief to `.tmp/source_brief.json`.

## Output
- `source_brief`: Structured summary and key facts.

## Execution Tool
- `execution/ingest_source.py`
