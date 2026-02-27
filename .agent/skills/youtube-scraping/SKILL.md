---
name: youtube-scraping
description: Scrapes YouTube video metadata, transcripts, and performs advanced language detection. Use this skill when the user wants to extract data from YouTube search results or channels.
---

# YouTube Scraping Skill

## When to use this skill
- When the user needs to get data (titles, views, likes) from YouTube videos.
- When the user wants full transcripts/captions from videos.
- When the user needs to analyze the language of a video (including code-switching/mixed language detection).
- When the user wants to extract resource links from video descriptions.

## Workflow
1.  **Check Dependencies**: Ensure python dependencies are installed.
2.  **Run Scraper**: Execute the python script with the target query or URL.
3.  **Process Output**: Parse the JSON output for downstream tasks.

## Instructions

### 1. Installation
The script requires Python and specific libraries. The requirements file is located in `scripts/requirements.txt`.

```bash
pip install -r scripts/requirements.txt
```

### 2. Running the Scraper
The core logic is in `scripts/scraper.py`. It accepts a single argument: a search query OR a generic URL (video, channel, playlist).

**Syntax:**
```bash
python scripts/scraper.py "<query_or_url>"
```

**Examples:**
- Search: `python scripts/scraper.py "AI automation tutorial"`
- Channel: `python scripts/scraper.py "https://www.youtube.com/@n8n-io"`
- Specific Video: `python scripts/scraper.py "https://www.youtube.com/watch?v=12345"`

### 3. Output Format
The script prints a JSON array to `stdout`.
Each object contains:
- `title`, `description`, `thumbnail`, `url`
- `full_transcription`: String containing the full text. `""` if not available.
- `detected_language`: ISO-639-1 code (e.g., "en", "es").
- `language_confidence`: Float percentage (0-100).
- `is_mixed_language`: Boolean, true if significant secondary language detected.
- `secondary_languages`: List of other detected languages with confidence.
- `resources_mentioned`: List of URLs found in the description.
- `stats`: Object with `views`, `likes`, `upload_date`, `duration_seconds`.

### 4. Error Handling
- If `scraper.py` fails (e.g., network issue, strict YouTube rate limiting), it will print errors to `stderr`.
- If no transcript is found, `full_transcription` will be empty string `""`.
- Ensure you handle `json.loads()` failures if the output is contaminated (though the script configures stdout for UTF-8 JSON).

## Resources
- [scraper.py](scripts/scraper.py)
- [requirements.txt](scripts/requirements.txt)
