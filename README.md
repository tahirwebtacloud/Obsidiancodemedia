# LinkedIn Post Generator - Obsidian Logic

A powerful LinkedIn content automation system with multimodal repurposing, supporting 128 distinct generation configurations.

## Overview

This system generates LinkedIn posts with full support for:

- **2 Post Types**: Text Basic, Article
- **4 Purpose Types**: Breakdown (Breakdown), Announcement (Announcement), Money Math (Money Math), ID-Challenge (ID-Challenge)
- **4 Visual Aspects**: None, Image, Video, Carousel
- **4 Aspect Ratios**: 1:1, 4:5, 16:9, 9:16

**Total: 128 distinct generation configurations**

## Features

### 1. Multimodal Repurposing

- **LinkedIn Posts**: Extract images, carousels, and video URLs from source posts
- **YouTube Videos**: Transcribe videos and analyze thumbnails
- **Mixed Media**: Combine images, videos, and text from multiple sources
- **Visual Context Analysis**: LLM analyzes hooks, content structure, key messages, typography, visual style

### 2. Research Integration

- **Viral Research**: Apify-based LinkedIn viral post analysis
- **Competitor Research**: Multi-profile LinkedIn scraping
- **YouTube Research**: Local yt-dlp scraper with transcript extraction

### 3. Content Generation

- **Gemini 3.0 LLM**: Advanced multimodal generation
- **Purpose-Specific System Prompts**: 4 directive files for different content types
- **Visual Aspect Adaptation**: Distinct prompt instructions for each visual type
- **Post Type Differentiation**: Text (150 words) vs Article (300-500 words)

### 4. Lead Intelligence & CRM

- **Post Interaction Scraping**: Parallel extraction of both reactions (likes, loves) and detailed comments using Apify.
- **Unified Lead Profiles**: Deduplicates users and merges their reactions and comment text into a single unified record based on Profile URL.
- **Engagement Categorization**: Differentiates between passive readers (reactors) and active interactors (commenters).
- **Premium CRM UI**: Embedded responsive table featuring custom scrollbars, sticky headers, high-contrast typography, and tier/activity badges using Obsidian Logic branding.
- **Minimalist Modal Footer**: Clean separation of tab actions and right-aligned action buttons without messy inline styles.

## Architecture

### Frontend (`frontend/`)

- **index.html**: Main UI with Generate tab, Competitor Hub, Repurpose Modal, Drafts, and **horizontal stepper progress tracker**
- **script.js**: Client-side logic for form handling, modal management, API calls, and **SSE progress streaming** (`generateWithSSE`, `showSimpleProgress`, `completeSimpleProgress`)
- **style.css**: Modern dark theme with glassmorphism effects and **animated stepper progress UI**

### Backend (`server.py`)

FastAPI server (port 9999) with endpoints:

- `POST /api/generate`: Main content generation endpoint (128 routing configs)
- `POST /api/generate-stream`: **SSE streaming endpoint** — real-time progress events for text/image generation stages
- `POST /api/research/viral`: Viral research initiation
- `POST /api/research/competitor`: Competitor scraping
- `POST /api/research/youtube`: YouTube video analysis (fast/deep modes)
- `POST /api/save`: Save post to Baserow via baserow_logger
- `POST /api/regenerate-image`: Regenerate image (refine via VLM+IDM or tweak via text-to-image)
- `POST /api/regenerate-caption`: Regenerate caption with custom instructions
- `POST /api/draft`: Quick in-situ drafting via Gemini LLM
- `GET /api/history`: Get generation history (max 100 entries)
- `GET /api/drafts`: List drafts
- `POST /api/drafts`: Create draft
- `PUT /api/drafts/{draft_id}`: Update draft
- `DELETE /api/drafts/{draft_id}`: Delete draft
- `POST /api/drafts/{draft_id}/publish`: Publish or schedule a draft via Blotato
- `POST /api/blotato/test`: Validate Blotato API key and fetch account info

**Server features:**

- `RequestValidationError` handler — logs and returns detailed Pydantic validation errors
- `Optional[str]` / `Optional[List[str]]` type hints in `GenerateRequest` to accept `null` from frontend
- UTF-8 subprocess encoding with `errors='replace'` fallback
- Static file mounts: `/assets` → `.tmp/`, `/` → `frontend/`
- **SSE streaming** via `StreamingResponse` + `asyncio.to_thread` for non-blocking subprocess stdout reading
- Helper functions `_build_orchestrator_command()` and `_save_history_entry()` for shared logic

### Execution Layer (`execution/`)

- **orchestrator.py**: Main pipeline orchestrator
- **generate_assets.py**: Single/post generation with multimodal support; prints `>>>STAGE:` markers to stdout for SSE progress tracking
- **generate_carousel.py**: Dedicated carousel generator (3-phase)
- **viral_research_apify.py**: LinkedIn viral post scraping
- **local_youtube.py**: YouTube video transcript extraction
- **rank_and_analyze.py**: Topic analysis and ranking

### Directive Files (`directives/`)

- `educational_caption.md`: Breakdown content system prompt
- `storytelling_caption.md`: Announcement content system prompt
- `authority_caption.md`: Money Math/Money Math system prompt
- `promotional_caption.md`: ID-Challenge content system prompt
- `image_prompt_design.md`: Visual asset generation SOP

## Routing Matrix

### Purpose Types (4)

| UI Label (Internal Value) | Directive File | Description |
|---------|--------------|-------------|
| Breakdown (`educational`) | `educational_caption.md` | The Process Breakdown framework |
| Announcement (`storytelling`) | `storytelling_caption.md` | The Personal Announcement framework |
| Money Math (`authority`) | `authority_caption.md` | The Money Math framework |
| ID-Challenge (`promotional`) | `promotional_caption.md` | The Identity Challenge framework |

### Visual Aspects (4)

| Aspect | Prompt Instructions | Behavior |
|--------|-------------------|----------|
| None | Generate standalone text post. Caption must be complete and self-contained. | No visual asset |
| Image | Generate text caption + image prompt. Caption should reference/complement the visual. | Image generated |
| Video | Generate text caption + video concept. Caption should tease the video content. | Video concept only |
| Carousel | Multi-slide concept where each slide builds on the previous one. | Routes to separate generator |

### Aspect Ratios (4)

| Ratio | Description | Use Case |
|-------|-------------|----------|
| 1:1   | Square      | Feed posts, mobile-first |
| 4:5   | Portrait    | Carousels, mobile |
| 16:9  | Landscape   | Desktop, presentations |
| 9:16  | Vertical    | Stories, reels |

## Multimodal Repurposing Flow

### Source Post Analysis

1. **URL Extraction**: Extract post URL from LinkedIn or YouTube
2. **Content Scraping**: Get post text, images, carousels, video URLs
3. **Visual Context**: Download images, transcribe videos
4. **Metadata**: Extract author, reactions, views, engagement metrics

### LLM Prompt Construction

```python
# 3-Step Mega Prompt
1. Deep Source Analysis:
   - Analyze text content
   - Extract hooks, rehooks, CTAs
   - Analyze images for typography, visual style, key messages
   - Transcribe videos for storytelling structure, memorable quotes

2. Generate Repurposed Post:
   - Adapt to Post Type (text/article)
   - Follow Purpose directive
   - Apply Visual Aspect instructions

3. Visual Asset (if applicable):
   - Generate single point (max 10 words)
   - Create detailed image prompt
   - Use target aspect ratio
```

### Visual Context Building

```python
def _build_visual_parts(visual_context_path):
    # Download images as Gemini Parts
    # Transcribe videos
    # Extract hooks, content structure, key messages
    # Build visual description for LLM
    return visual_parts, visual_desc
```

## Key Files

### Orchestrator Flow

```python
orchestrator.py:
1. Parse arguments (type, purpose, visual_aspect, aspect_ratio)
2. PRE-CLEAR: Read source_content and visual_context files
3. Clear .tmp directory
4. POST-CLEAR: Rewrite source_content and visual_context files
5. Route to generator:
   - carousel → generate_carousel.py
   - others → generate_assets.py
```

### Generate Assets Flow

```python
generate_assets.py:
1. Load purpose directive (educational/storytelling/authority/promotional)
2. Build visual parts (images, video transcriptions)
3. Construct mega prompt with:
   - Post Type adaptation (text vs article)
   - Visual Aspect adaptation (none/image/video/carousel)
   - Purpose-specific instructions
4. Call Gemini LLM with multimodal content
5. Generate image if visual_aspect == "image"
6. Return final_plan.json
```

## Environment Variables

See `.env.example` for the full list. Key variables:

```bash
GOOGLE_GEMINI_API_KEY=your_gemini_api_key
GEMINI_TEXT_MODEL=gemini-3-pro-preview
GEMINI_IMAGE_MODEL=gemini-3-pro-image-preview
APIFY_API_KEY=your_apify_api_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
BASEROW_TOKEN=your_baserow_token
JINA_API_KEY=your_jina_api_key
BLOTATO_API_KEY=your_blotato_api_key
```

## Setup

### Option A: Local Development

1. **Install Dependencies**:

```bash
pip install -r requirements.txt
```

2. **Set Environment Variables**:

```bash
cp .env.example .env
# Fill in your API keys in .env
```

3. **Run Server**:

```bash
python server.py
```

4. **Access UI**:

```text
http://localhost:9999
```

### Option B: Cloud Deployment (Modal)

The app is deployed as a full-stack serverless application on [Modal](https://modal.com).

**Live URL**: `https://tahir-70872--linkedin-post-generator-web.modal.run`

**Deployment file**: `modal_app.py` — packages the entire FastAPI backend + static frontend into a single Modal web endpoint.

1. **Install Modal CLI**:

```bash
pip install modal
```

2. **Authenticate**:

```bash
modal token new
```

3. **Create Secrets** (from your local `.env`):

```bash
modal secret create linkedin-post-generator --from-dotenv .env
```

4. **Deploy**:

```powershell
$env:PYTHONIOENCODING="utf-8"; modal deploy modal_app.py
```

5. **Dev Mode** (hot-reload with temporary URL):

```powershell
$env:PYTHONIOENCODING="utf-8"; modal serve modal_app.py
```

**Key Modal behaviors:**
- **Snapshot-based**: Local changes require re-deploy (`modal deploy`) to go live
- **Scale-to-zero**: Container idles after 5 min of no traffic (no cost when unused)
- **Cold start**: First request after idle takes ~10-15s to spin up the container
- **Concurrency**: Handles up to 10 concurrent requests per container
- **Timeout**: 600s max per request (sufficient for long generation runs)

**Important**: After deploying, add the Modal URL as an allowed redirect in your Supabase dashboard (Authentication → URL Configuration → Redirect URLs)

## Usage

### Generate Tab

1. Select Content Source (Direct Topic / News / Article)
2. Choose Format (Text Basic / Article)
3. Set Purpose (Breakdown / Announcement / Money Math / ID-Challenge)
4. Select Visual Aspect (None / Image / Video / Carousel)
5. Configure Aspect Ratio (if Image)
6. Enter Topic
7. Click Generate

### Drafts

Drafts are saved per user and can be edited, deleted, and published.

- **Save a draft**: Generate a post and click `Save Draft`
- **Browse drafts**: Open `History` then switch to the `Drafts` sub-tab
- **Edit**: Click a draft to open the Draft Edit modal
- **Publish/Schedule**: Use the publish controls in the Draft Edit modal (uses Blotato)

The Drafts view uses a 3D "book" card UI with a hover flip animation.

### Settings (Blotato)

Use the Settings icon in the top header to configure publishing:

- **Set API key**: Paste your Blotato API key and click `Save`
- **Test connection**: Click `Test Connection` to confirm account access

### Competitor Hub

1. **Viral Tab**: Research viral posts by topic
2. **Competitor Tab**: Enter LinkedIn profile URLs
3. **YouTube Tab**: Enter YouTube video URLs
4. Click repurpose button on any result
5. Configure repurpose options in modal
6. Confirm to generate

### Repurpose Modal

All repurpose actions (Viral, Competitor, YouTube) use the same modal with:

- Source content preview
- Visual context indicator (shows analyzed media)
- Full 128 routing options
- Thumbnail/image/video analysis integration

## Technical Details

### Temp File Handling

- `.tmp/source_content_*.txt`: Large source text (avoids CLI length limits)
- `.tmp/visual_context_*.json`: Visual context (images, videos, metadata)
- `.tmp/final_plan.json`: Generated content output
- `.tmp/youtube_research.json`: YouTube research results

### Critical Bug Fix 1: Orchestrator Temp File Deletion

**Problem**: `clear_temp_directory()` was deleting visual_context and source_content files before they were read.

**Solution**: PRE-CLEAR / POST-CLEAR pattern:

1. Read files into memory
2. Clear .tmp directory
3. Rewrite files from memory

### Critical Bug Fix 2: Pydantic 422 Validation Error on YouTube Repurpose

**Problem**: `GenerateRequest` model used bare `str = None` and `list = None` types. When frontend sent JSON `null` for fields like `source_video_urls`, Pydantic rejected them with 422 Unprocessable Entity. The frontend only checked `result.error` but FastAPI returns `result.detail` for validation errors, so the UI showed "Drafting failed: undefined".

**Solution** (in `server.py`):

1. Changed all nullable fields to `Optional[str]` and `Optional[List[str]]` using `from typing import Optional, List`
2. Added `RequestValidationError` exception handler that logs the exact validation error and returns both `error` and `detail` fields
3. Updated frontend (`script.js`) to check `result.error || result.detail || JSON.stringify(result)`
4. Added null safety for YouTube thumbnail: `item.thumbnail && item.thumbnail.startsWith && item.thumbnail.startsWith('http')`

### Carousel Generation

3-Phase process:

1. **Plan Structure**: Decide slide count, hook strategy, CTA
2. **Generate Content**: Write text for each slide
3. **Generate Caption**: Write LinkedIn caption after slides are ready

## Real-Time Progress Tracking (SSE)

The app uses **Server-Sent Events (SSE)** to provide real-time progress feedback during content generation.

### How It Works

1. `generate_assets.py` prints stage markers to stdout: `>>>STAGE:text_start`, `>>>STAGE:text_done`, `>>>STAGE:image_start`, `>>>STAGE:image_done`
2. `server.py` SSE endpoint (`/api/generate-stream`) runs the orchestrator via `subprocess.Popen`, reads stdout line-by-line using `asyncio.to_thread`, and emits SSE events when markers are detected
3. Frontend `generateWithSSE()` function consumes the stream via `fetch` + `ReadableStream`, calling `setStage()` to update the horizontal stepper UI in real-time
4. Non-SSE flows (regenerate caption/image) use `showSimpleProgress()` / `completeSimpleProgress()` helpers

### Horizontal Stepper UI

The progress tracker displays as a **horizontal stepper** in the Output Console:

- Two circles (Text Generation, Image Generation) connected by a horizontal line
- **Waiting**: Muted circle with subtle border
- **Active**: Brand-gold pulsing circle with animated glow, connector line breathes between 10-45% width
- **Done**: Solid green circle with checkmark SVG icon swap, fully filled green connector line
- **Error**: Red circle with red status badge
- **Skipped**: Dashed border circle at 35% opacity (for text-only posts)

### System Sounds

- `addSystemLog()` with type `'success'` triggers `playSystemSound('success')`
- Per-stage completion logs use `'info'` type (no sound) to avoid multiple dings
- Only the final "Neural generation sequence complete" log plays the sound once

## API Endpoints

### POST /api/generate

Main content generation endpoint. Supports all 128 routing configurations.

**Pydantic Model** (`GenerateRequest`):

```python
class GenerateRequest(BaseModel):
    action: str
    source: Optional[str] = None
    url: Optional[str] = None
    topic: Optional[str] = None
    type: str = "text"
    purpose: str = "educational"
    visual_aspect: Optional[str] = None
    visual_style: Optional[str] = None
    aspect_ratio: str = "16:9"
    source_content: Optional[str] = None
    source_post_type: Optional[str] = None
    source_image_urls: Optional[List[str]] = None
    source_carousel_slides: Optional[List[str]] = None
    source_video_url: Optional[str] = None
    source_video_urls: Optional[List[str]] = None
```

**Request Body**:

```json
{
  "action": "develop_post",
  "source": "topic",
  "topic": "AI Trends 2026",
  "type": "text",
  "purpose": "educational",
  "visual_aspect": "image",
  "visual_style": "minimal",
  "aspect_ratio": "4:5",
  "source_content": "...",
  "source_post_type": "image",
  "source_image_urls": ["..."],
  "source_carousel_slides": [],
  "source_video_urls": []
}
```

**Response**:

```json
{
  "caption": "...",
  "single_point": "...",
  "image_prompt": "...",
  "asset_url": "..."
}
```

### POST /api/generate-stream

**SSE streaming endpoint** for real-time progress during generation. Uses `StreamingResponse` with `text/event-stream` content type.

**SSE Events emitted:**

- `event: stage` / `data: {"stage": "text_start"}` — Text generation starting
- `event: stage` / `data: {"stage": "text_done"}` — Text generation complete
- `event: stage` / `data: {"stage": "image_start"}` — Image generation starting
- `event: stage` / `data: {"stage": "image_done"}` — Image generation complete
- `event: result` / `data: {"caption": "...", ...}` — Final result JSON (uses `ensure_ascii=False` for unicode)
- `event: error` / `data: {"error": "..."}` — Error occurred

**Implementation details:**

- Runs orchestrator subprocess via `subprocess.Popen` with `stdout=PIPE`
- Reads stdout line-by-line using `asyncio.to_thread(proc.stdout.readline)` to avoid blocking the event loop
- Detects `>>>STAGE:` markers in stdout and emits corresponding SSE events
- Reuses `_build_orchestrator_command()` and `_save_history_entry()` helper functions

### POST /api/save

Save generated post to Baserow database.

### POST /api/regenerate-image

Regenerate image with two modes:

- **refine**: VLM analyzes current image + instructions → IDM generates new image
- **tweak**: Direct text-to-image from user prompt

### POST /api/regenerate-caption

Regenerate caption with custom instructions, keeping same topic/purpose/type.

### POST /api/draft

Quick in-situ drafting via Gemini LLM (used by legacy draft flow).

**Note:** The main form and repurpose flows now use `/api/generate-stream` (SSE) instead of `/api/generate`. The original `/api/generate` endpoint is still available for non-streaming use cases.

### GET /api/history

Returns generation history (max 100 entries, most recent first).

### POST /api/research/viral

Initiate viral research for a topic via Apify.

### POST /api/research/competitor

Scrape LinkedIn profiles for competitor analysis via Apify.

### POST /api/research/youtube

Analyze YouTube videos with transcript extraction.

- **Fast mode** (default): `local_youtube.py` using yt-dlp
- **Deep mode**: `apify_youtube.py` using Apify actor

## Troubleshooting

### Server not starting

- Check if port 9999 is in use: `netstat -ano | findstr ":9999"`
- Kill existing process: `taskkill /PID <PID> /F`

### YouTube repurpose not working

- **422 Validation Error**: If you see "Drafting failed: undefined", check that `server.py` uses `Optional[str]` / `Optional[List[str]]` in `GenerateRequest` model
- Verify thumbnail URL is valid (starts with http)
- Check that visual context is being passed (`console.log` in repurpose handler)
- Ensure local_youtube.py has yt-dlp installed
- Check browser console for `Repurpose response:` log to see actual HTTP status and response body

### Carousel generation fails

- Check that visual_context is passed to generate_carousel.py
- Verify carousel routing in orchestrator.py
- Ensure 3-phase generation completes

### Image generation issues

- Verify aspect_ratio is sanitized (not "image", "video", etc.)
- Check that visual_aspect == "image" triggers image generation
- Ensure image_prompt doesn't contain colons (replaced with hyphens)

## Development

### Adding New Purpose Type

1. Create `directives/{purpose}_caption.md` with system prompt
2. Add option to HTML dropdowns
3. No code changes needed (dynamic loading)

### Adding New Visual Aspect

1. Add option to HTML dropdowns
2. Add prompt instructions in generate_assets.py STEP 2
3. Add routing logic if needed (e.g., separate generator)

### Modifying LLM Prompts

- Edit mega prompt in `generate_assets.py` (lines 373-450)
- Edit system prompts in `directives/*.md` files
- No code changes needed for prompt tuning

## Deployment Architecture

```
Local Machine                          Modal Cloud
┌──────────────┐     modal deploy     ┌──────────────────────────────────┐
│ modal_app.py │ ──────────────────►  │ Container (Debian + Python 3.11) │
│ server.py    │                      │  /app/server.py (FastAPI)        │
│ orchestrator │                      │  /app/orchestrator.py            │
│ frontend/    │                      │  /app/frontend/ (static)         │
│ execution/   │                      │  /app/execution/ (scripts)       │
│ directives/  │                      │  /app/directives/ (prompts)      │
│ .env         │                      │  Modal Secrets (env vars)        │
└──────────────┘                      └──────────────────────────────────┘
                                        ▲
                                        │ HTTPS
                                        │
                                      Users access via:
                                      tahir-70872--linkedin-post-generator-web.modal.run
```

## License

Proprietary - Obsidian Logic
