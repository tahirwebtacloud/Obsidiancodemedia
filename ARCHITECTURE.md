# Architecture Documentation

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Browser)                      │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │  Generate   │  │  Competitor  │  │   Repurpose Modal       │ │
│  │     Tab      │  │     Hub      │  │  (Shared by all tabs)   │ │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬──────────────┘ │
│         │                │                     │                │
│         └────────────────┴─────────────────────┘                │
│                            │                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Horizontal Stepper Progress Tracker (Output Console)   │   │
│  │  [○ Text Gen] ────────── [○ Image Gen]                  │   │
│  │  States: waiting → active (pulse) → done (✓) / error    │   │
│  │  SSE: generateWithSSE() consumes /api/generate-stream   │   │
│  │  Non-SSE: showSimpleProgress() / completeSimpleProgress()│   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                     │
└────────────────────────────┼─────────────────────────────────────┘
                             │ HTTP POST (SSE stream or REST)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (server.py)                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  FastAPI Server on :9999                                │   │
│  │  - /api/generate (main generation - REST)                │   │
│  │  - /api/generate-stream (SSE streaming + progress)       │   │
│  │  - /api/regenerate-caption (REST)                        │   │
│  │  - /api/regenerate-image (REST, tweak/refine modes)      │   │
│  │  - /api/research/viral                                  │   │
│  │  - /api/research/competitor                              │   │
│  │  - /api/research/youtube                                │   │
│  └────────────────────────┬────────────────────────────────┘   │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR (orchestrator.py)                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  1. Parse Arguments                                      │   │
│  │  2. PRE-CLEAR: Read source_content, visual_context      │   │
│  │  3. Clear .tmp directory                                │   │
│  │  4. POST-CLEAR: Rewrite source_content, visual_context  │   │
│  │  5. Route to Generator:                                 │   │
│  │     - carousel → generate_carousel.py                   │   │
│  │     - others → generate_assets.py                       │   │
│  └────────────────────────┬────────────────────────────────┘   │
└───────────────────────────┼─────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌──────────────────────┐      ┌──────────────────────────┐
│  generate_assets.py  │      │   generate_carousel.py    │
│                      │      │                          │
│  1. Load Directive   │      │  Phase 1: Plan Structure │
│  2. Build Visual     │      │  Phase 2: Generate Slides │
│     Parts            │      │  Phase 3: Generate Caption│
│  3. Mega Prompt      │      │                          │
│  4. Call Gemini LLM  │      │  3-Phase Carousel Gen    │
│  5. Generate Image   │      │                          │
│     (if needed)      │      └──────────┬───────────────┘
│  6. Return Plan      │                 │
└──────────┬───────────┘                 │
           │                             ▼
           ▼                    ┌─────────────────┐
┌──────────────────────┐         │ final_plan.json  │
│  Gemini 3.0 LLM     │         │                 │
│  (Multimodal)       │         │ - caption       │
│  - Text Prompts     │         │ - image_prompt  │
│  - Image Parts      │         │ - asset_url     │
│  - Video Transcripts│         │ - carousel_*    │
└──────────┬───────────┘         └─────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TEMP FILES (.tmp/)                         │
│  - source_content_*.txt      (Large source text)               │
│  - visual_context_*.json      (Images, videos, metadata)        │
│  - youtube_research.json      (YouTube results)                │
│  - viral_research.json        (Viral post results)              │
│  - analysis.json             (Topic analysis)                  │
│  - final_plan.json           (Generated output)                │
│  - carousel_layout.json       (Carousel structure)              │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### Frontend Components

#### Generate Tab (`frontend/index.html` lines 42-133)

- **Form Fields**:
  - Content Source: Direct Topic / News / Article
  - Format: Text Basic / Article
  - Purpose: Breakdown / Announcement / Money Math / ID-Challenge
  - Visual Aspect: None / Image / Video / Carousel
  - Aspect Ratio: 1:1 / 4:5 / 16:9 / 9:16
  - Topic: Text input
- **Submit Handler**: Uses `generateWithSSE()` to stream to `/api/generate-stream`

#### Horizontal Stepper Progress Tracker (`frontend/index.html` lines 284-323)

- **Location**: Inside `#results-panel`, between `#empty-state` and `#results-content`
- **Structure**: `.stepper-track` with two `.progress-stage` divs connected by `.stepper-connector`
- **Circle Content**: Each `.stepper-circle` contains a `.step-number` (numbered digit) and `.step-check` (SVG checkmark)
- **States**: Applied via class on `.progress-stage`: `active`, `done`, `error`, `skipped`
- **CSS**: Animated pulsing glow on active, green fill + checkmark swap on done, connector line fills via CSS sibling selectors

#### Competitor Hub (`frontend/index.html` lines 136-202)

- **Viral Tab**: Viral post research by topic
- **Competitor Tab**: LinkedIn profile scraping
- **YouTube Tab**: YouTube video analysis
- **Repurpose Button**: Opens shared repurpose modal

#### Repurpose Modal (`frontend/index.html` lines 353-432)

- **Source Preview (`.modal-content-grid`)**: Two-column layout optionally collapsing to one column based on visual content (`.no-visual` utility class).
- **Visual Context Indicator**: Shows analyzed media count.
- **Leads CRM Table (`.crm-table-wrapper`)**: Responsive table featuring custom scrollbars, sticky headers, high-contrast typography (`.crm-lead-name`), tier badges (`.crm-tier-badge`), and activity pills (`.crm-activity-pill`).
- **Form Fields**: Same as Generate tab (128 routing options)
- **Modal Actions Footer (`.modal-actions`, `.modal-tabs`)**: Decoupled flexbox CSS classes to push the Repurpose Post button to the right and tab buttons to the left.
- **Confirm Handler**: Aggregates visual context from all selected items

#### Drafts UI (`frontend/index.html`)

- **Entry point**: `History` → `Drafts` sub-tab
- **Draft list**: Grid of 3D “book” cards
  - Structure: `.draft-book` with `.cover` + `.inner` panels
  - Behavior: hover animation flips the cover to reveal actions
- **Draft Edit modal**: Edit caption/topic, delete draft, publish/schedule

#### Settings Modal (`frontend/index.html`)

- **Entry point**: Settings icon in the main header
- **Purpose**: Configure Blotato API key, save it to user settings, and test connection

### Backend Components

#### server.py

FastAPI application with 12 endpoints, SSE streaming, and validation error handling:

**Imports & Setup:**

```python
from typing import Optional, List
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
import asyncio

# Validation error handler — logs and returns detailed Pydantic errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    body = await request.body()
    print(f">>> VALIDATION ERROR: {exc.errors()}")
    return JSONResponse(status_code=422, content={"error": str(exc.errors()), "detail": str(exc.errors())})
```

**Helper Functions** (shared by `/api/generate` and `/api/generate-stream`):

```python
def _build_orchestrator_command(req):
    # Builds the subprocess command list from GenerateRequest fields
    # Handles source_content temp file, visual_context JSON, ref images
    return command

def _save_history_entry(req, result_data):
    # Saves generation result to history.json
```

**Pydantic Model** (uses `Optional` to accept `null` from frontend JSON):

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

**Endpoints:**

```python
@app.post("/api/generate")          # Main generation REST (128 routing configs)
@app.post("/api/generate-stream")   # SSE streaming generation with real-time progress
@app.post("/api/save")              # Save post to Baserow
@app.post("/api/regenerate-image")   # Regenerate image (refine/tweak modes)
@app.post("/api/regenerate-caption") # Regenerate caption
@app.post("/api/draft")             # Quick in-situ drafting
@app.get("/api/history")             # Generation history (max 100)
@app.get("/api/drafts")              # List drafts
@app.post("/api/drafts")             # Create draft
@app.put("/api/drafts/{draft_id}")    # Update draft
@app.delete("/api/drafts/{draft_id}") # Delete draft
@app.post("/api/drafts/{draft_id}/publish") # Publish/schedule draft via Blotato
@app.post("/api/blotato/test")       # Test Blotato API key and fetch account
@app.post("/api/research/viral")     # Viral research via Apify
@app.post("/api/research/competitor") # Competitor scraping via Apify
@app.post("/api/research/youtube")   # YouTube analysis (fast=yt-dlp, deep=Apify)
```

**SSE Streaming Endpoint** (`/api/generate-stream`):

```python
@app.post("/api/generate-stream")
async def generate_post_stream(req: GenerateRequest):
    command = _build_orchestrator_command(req)
    
    async def event_generator():
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=RUN_ENV, encoding='utf-8', errors='replace')
        while True:
            line = await asyncio.to_thread(proc.stdout.readline)
            if not line and proc.poll() is not None:
                break
            if line.startswith('>>>STAGE:'):
                stage = line.strip().replace('>>>STAGE:', '')
                yield f"event: stage\ndata: {json.dumps({'stage': stage})}\n\n"
        
        # Read final_plan.json and emit result
        result_data = json.load(open('.tmp/final_plan.json', 'r', encoding='utf-8'))
        _save_history_entry(req, result_data)
        yield f"event: result\ndata: {json.dumps(result_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Execution Layer

#### orchestrator.py

Main pipeline orchestrator with critical bug fix:

```python
def clear_temp_directory():
    # PRE-CLEAR: Read files before deletion
    if os.path.exists(source_content_path):
        with open(source_content_path, 'r') as f:
            source_content = f.read()
    if os.path.exists(visual_context_path):
        with open(visual_context_path, 'r') as f:
            visual_context = f.read()
    
    # Clear .tmp
    for file in os.listdir(".tmp"):
        os.remove(os.path.join(".tmp", file))
    
    # POST-CLEAR: Rewrite files
    if source_content:
        with open(source_content_path, 'w') as f:
            f.write(source_content)
    if visual_context:
        with open(visual_context_path, 'w') as f:
            f.write(visual_context)
```

**Routing Logic**:

```python
if args.type.lower() == "carousel" or args.visual_aspect.lower() == "carousel":
    gen_command = ["python", "execution/generate_carousel.py", 
                   "--topic", topic, "--purpose", args.purpose,
                   "--visual_context", args.visual_context]
else:
    gen_command = ["python", "execution/generate_assets.py",
                   "--type", args.type, "--purpose", args.purpose,
                   "--topic", topic, "--source", args.source,
                   "--style", args.style, "--aspect_ratio", args.aspect_ratio,
                   "--visual_aspect", args.visual_aspect,
                   "--source_content", args.source_content,
                   "--visual_context", args.visual_context]
```

#### generate_assets.py

Single/post generation with multimodal support. Prints `>>>STAGE:` markers to stdout for SSE progress tracking:

**Stage Markers** (detected by SSE endpoint):

```python
# Before LLM call
print(">>>STAGE:text_start")
raw_response = call_llm(system_prompt, contents, json_mode=True)
print(">>>STAGE:text_done")

# Before image generation
if should_generate_image:
    print(">>>STAGE:image_start")
    image_url, error_msg = generate_image_asset(full_prompt, aspect_ratio=aspect_ratio)
    print(">>>STAGE:image_done")  # fires even if image gen fails
```

**Key Functions**:

```python
def _build_visual_parts(visual_context_path):
    # Download images as Gemini Parts
    # Transcribe videos
    # Extract hooks, content structure, key messages
    return visual_parts, visual_desc

def generate_assets(post_type, purpose, topic, source_content, 
                    aspect_ratio, visual_aspect, visual_context_path):
    # 1. Load purpose directive
    directive_path = f"directives/{purpose}_caption.md"
    
    # 2. Build visual context
    visual_parts, visual_desc = _build_visual_parts(visual_context_path)
    
    # 3. Construct mega prompt
    user_content = f"""# TASK: Generate LinkedIn Post Assets
    Topic: {topic}
    Post Type: {post_type}
    Purpose: {purpose}
    Visual Aspect: {visual_aspect}
    TARGET ASPECT RATIO: {aspect_ratio}
    
    ## STEP 1: DEEP SOURCE ANALYSIS
    - Analyze text content
    - Extract hooks, rehooks, CTAs
    - Analyze images for typography, visual style, key messages
    - Transcribe videos for storytelling structure, memorable quotes
    
    ## STEP 2: GENERATE REPURPOSED POST
    - Post Type Adaptation: Text (150 words) vs Article (300-500 words)
    - Visual Aspect Adaptation: None/Image/Video/Carousel instructions
    - Purpose-Specific: Follow directive instructions
    
    ## STEP 3: VISUAL ASSET GENERATION
    - Only if visual_aspect == "image"
    - Generate single point (max 10 words)
    - Generate image prompt with aspect ratio
    """
    
    # 4. Call Gemini LLM with multimodal content
    response = call_llm(system_prompt, user_content, 
                       image_parts=visual_parts)
    
    # 5. Generate image if needed
    if visual_aspect == "image":
        image_url = generate_image(image_prompt, aspect_ratio)
    
    # 6. Return final plan
    return final_plan
```

#### generate_carousel.py

Dedicated 3-phase carousel generator:

```python
def generate_carousel(topic, purpose, visual_context_path=None):
    # Load visual context
    visual_parts, visual_desc = _build_visual_parts(visual_context_path)
    
    # Phase 1: Plan Structure
    carousel_plan = plan_carousel_structure(topic, purpose, 
                                            research_data, visual_desc)
    
    # Phase 2: Generate Slide Content
    slides_content = generate_slide_content(topic, purpose, 
                                           carousel_plan, research_data)
    
    # Phase 3: Generate Caption
    caption = generate_caption(topic, purpose, carousel_plan, slides_content)
    
    # Save layout and final plan
    return final_plan
```

#### viral_research_apify.py

LinkedIn post scraping with carousel manifest extraction:

```python
def extract_manifest_metadata(url):
    # Fetch carousel manifest JSON
    # Extract high-res image URLs
    # Get slide count and metadata

def sniff_manifest_from_html(url):
    # Fallback: Parse HTML for carousel data
    # Extract image URLs from DOM

def _fetch_og_image(url):
    # Get OG image from URL
    # Replace low-res with high-res
```

#### local_youtube.py

YouTube video analysis with transcript extraction:

```python
def run_local_youtube(urls):
    for url in urls:
        # Extract video info with yt-dlp
        info = ydl.extract_info(url, download=False)
        
        # Get transcript
        captions = info.get('subtitles') or info.get('automatic_captions')
        en_track = find_english_track(captions)
        transcript = download_and_clean_vtt(en_track)
        
        # Extract metadata
        title, description, thumbnail, views, likes = ...
        
        # Return result
        return {
            "title": title,
            "url": url,
            "thumbnail": thumbnail,
            "transcript": transcript,
            ...
        }
```

#### lead_scraper.py

Lead interaction scraper integrating two Apify actors (`datadoping/linkedin-post-reactions-scraper-no-cookie` and `curious_coder/linkedin-post-comments-scraper`).

- Combines data, normalizes into a unified schema, and deduplicates using LinkedIn profile URLs.
- Computes an Engagement Score to prioritize leads (comments carry higher weight than reactions).

#### supabase_client.py

Thin wrapper around Supabase Python SDK (`supabase.create_client()`).

- Coordinates reading/writing settings and history to Supabase PostgreSQL.
- Uses service role key for reliable backend access (never expires).
- Gracefully falls back to local JSON persistence (`.tmp/history_{uid}.json` and `.local_settings.json`) if Supabase is unreachable.
- All data is isolated per user ID for multi-tenant support.

### Directive Files

System prompts for each purpose type:

**educational_caption.md**: Teach, inform, educate

- Focus on actionable insights
- Use clear structure with bullet points
- Include data and statistics

**storytelling_caption.md**: Personal stories, narratives

- Use first-person perspective
- Emotional hooks and vulnerability
- Authentic voice and tone

**authority_caption.md**: Thought leadership, expertise

- Demonstrate expertise
- Share unique insights
- Credibility through examples

**promotional_caption.md**: Product/service promotion

- Focus on benefits over features
- Social proof and testimonials
- Clear CTA

## Data Flow

### Generate Tab Flow (SSE Streaming)

```
User fills form
    ↓
Submit → generateWithSSE() → POST /api/generate-stream
    ↓
Horizontal stepper shows in Output Console (text: waiting, image: waiting)
    ↓
server.py runs orchestrator via Popen, reads stdout
    ↓
>>>STAGE:text_start detected → SSE event → stepper: text circle pulses gold
    ↓
generate_assets.py calls Gemini LLM
    ↓
>>>STAGE:text_done detected → SSE event → stepper: text circle turns green ✓
    ↓
>>>STAGE:image_start detected → SSE event → stepper: image circle pulses gold
    ↓
generate_assets.py generates image
    ↓
>>>STAGE:image_done detected → SSE event → stepper: image circle turns green ✓
    ↓
result event with final_plan.json → stepper hides after 800ms → UI shows results
```

### Repurpose Flow (SSE Streaming)

```
User clicks repurpose button
    ↓
openRepurposeModal(source, sourceType, visualItems)
    ↓
Modal shows source preview + visual context indicator
    ↓
User configures options (128 routing)
    ↓
Confirm → generateWithSSE() → POST /api/generate-stream
    ↓
Same stepper progress flow as Generate Tab
    ↓
UI displays results
```

### Regenerate Caption Flow (Non-SSE)

```
User clicks "Regen Text" → showSimpleProgress('text')
    ↓
Stepper shows: text circle active (pulsing), image: waiting
    ↓
POST /api/regenerate-caption (REST)
    ↓
Success → completeSimpleProgress('text') → stepper hides after 800ms
Error → completeSimpleProgress('error') → stepper shows red, hides after 1500ms
```

### Regenerate Image Flow (Non-SSE)

```
User clicks "Regen Image" → showSimpleProgress('image')
    ↓
Stepper shows: text: waiting, image circle active (pulsing)
    ↓
POST /api/regenerate-image (REST, mode: tweak or refine)
    ↓
Success → completeSimpleProgress('image') → stepper hides after 800ms
Error → completeSimpleProgress('error') → stepper shows red, hides after 1500ms
```

## Critical Implementation Details

### 1. Temp File Handling (PRE-CLEAR/POST-CLEAR)

**Problem**: Files were deleted before being read.

**Solution**: Read into memory, clear directory, rewrite from memory.

### 2. Visual Context Aggregation

**Problem**: Multiple items need to be combined.

**Solution**: Aggregate all image URLs, carousel slides, and video URLs from `_repurposeItems` array.

### 3. Aspect Ratio Sanitization

**Problem**: Invalid values like "image", "video" leaking in.

**Solution**: Sanitize at start of generate_assets.py, default to "16:9".

### 4. Image Prompt Colons

**Problem**: Colons in image prompts break style rules.

**Solution**: Replace all colons with hyphens: `full_prompt.replace(":", " -")`

### 5. YouTube Thumbnail Integration

**Problem**: YouTube repurpose had no visual context.

**Solution**: Create visualItems array with thumbnail URL, pass to repurpose modal.

### 6. Carousel Routing

**Problem**: Carousel needs separate generator.

**Solution**: Check `args.type == "carousel"` or `args.visual_aspect == "carousel"` in orchestrator.

### 7. Video Transcription

**Problem**: Need to analyze video content.

**Solution**: Use Gemini multimodal to transcribe and extract storytelling structure.

### 8. CLI Length Limits

**Problem**: Large source_content exceeds Windows CLI limits.

**Solution**: Write to temp file, pass file path instead of content.

### 9. Pydantic 422 Validation Error (YouTube Repurpose)

**Problem**: `GenerateRequest` used bare `str = None` and `list = None` types. When frontend sent JSON `null` for nullable fields (e.g. `source_video_urls: null`), Pydantic rejected with 422 Unprocessable Entity. Frontend only checked `result.error` but FastAPI returns `result.detail`, so UI showed "Drafting failed: undefined".

**Solution** (in `server.py`):

1. Changed all nullable fields to `Optional[str]` / `Optional[List[str]]` (using `from typing import Optional, List`)
2. Added `RequestValidationError` exception handler that logs errors and returns both `error` and `detail` fields
3. Frontend now checks `result.error || result.detail || JSON.stringify(result)`
4. Added null safety for YouTube thumbnail: `item.thumbnail && item.thumbnail.startsWith && item.thumbnail.startsWith('http')`

### 10. YouTube Thumbnail Null Safety

**Problem**: `item.thumbnail.startsWith('http')` could throw if `thumbnail` is undefined or not a string.

**Solution**: Guard chain: `item.thumbnail && item.thumbnail.startsWith && item.thumbnail.startsWith('http')`, with fallback defaults for `title` and `channelName`.

### 11. Database Migration: Firebase → Supabase

**Problem**: Firebase Application Default Credentials (ADC) expired frequently, causing all Firestore operations to fail and fall back to local files. History and settings were not persisting to the cloud.

**Solution**: Migrated to Supabase PostgreSQL with service role key authentication (never expires). All user data (history, settings, surveillance) is now properly isolated per user ID in Supabase tables with local JSON fallbacks for offline resilience.

## Cloud Deployment (Modal)

The application is deployed on [Modal](https://modal.com) as a serverless full-stack web app.

**Live URL**: `https://tahir-70872--linkedin-post-generator-web.modal.run`

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODAL CLOUD (modal_app.py)                    │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Container: Debian Slim + Python 3.11                     │  │
│  │  Image: pip_install(requirements) + add_local_dir/file    │  │
│  │                                                           │  │
│  │  /app/                                                    │  │
│  │  ├── server.py        (FastAPI app, ASGI entrypoint)      │  │
│  │  ├── orchestrator.py  (Pipeline orchestrator)             │  │
│  │  ├── frontend/        (Static HTML/CSS/JS)                │  │
│  │  ├── execution/       (Python scripts)                    │  │
│  │  ├── directives/      (LLM system prompts)                │  │
│  │  └── .tmp/            (Runtime artifacts, ephemeral)      │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Secrets: modal.Secret.from_name("linkedin-post-generator")     │
│  Concurrency: 10 concurrent inputs per container                │
│  Timeout: 600s per request                                      │
│  Scaledown: 300s idle → container scales to zero                │
└─────────────────────────────────────────────────────────────────┘
```

### How modal_app.py Works

1. **Image Build**: Installs Python deps via `pip_install()`, copies project dirs/files via `add_local_dir()` / `add_local_file()` into `/app/`
2. **Runtime (`web()` function)**: Sets `cwd` to `/app`, adds `/app` and `/app/execution` to `sys.path`, creates `.tmp/` dir, then imports and returns the FastAPI `app` from `server.py`
3. **Secrets**: All env vars from `.env` are stored in Modal's encrypted secret store (`linkedin-post-generator`), injected at runtime
4. **ASGI**: The `@modal.asgi_app()` decorator exposes the FastAPI app directly via Modal's HTTPS edge

### Deployment Commands

```powershell
# Deploy (snapshot current code to production URL)
$env:PYTHONIOENCODING="utf-8"; modal deploy modal_app.py

# Dev mode (hot-reload with temporary URL)
$env:PYTHONIOENCODING="utf-8"; modal serve modal_app.py

# View logs
$env:PYTHONIOENCODING="utf-8"; modal app logs linkedin-post-generator

# Update secrets after .env changes
modal secret create linkedin-post-generator --from-dotenv .env --force
```

### Key Constraints

- **Ephemeral filesystem**: `.tmp/` is container-local and resets on cold start. Generated images/files are lost between container restarts.
- **Snapshot-based deploys**: Code changes require `modal deploy` to go live.
- **Cold starts**: ~10-15s on first request after idle period.
- **Supabase redirect**: Modal URL must be added to Supabase Auth allowed redirects.

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
```

## Dependencies

### Python (requirements.txt)

- fastapi: Web framework
- uvicorn: ASGI server (local only)
- python-dotenv: Environment variables
- google-genai: Gemini API
- Pillow: Image processing
- apify-client: LinkedIn/YouTube scraping
- yt-dlp: YouTube download
- supabase: Database client
- requests: HTTP requests
- beautifulsoup4: HTML parsing

### Deployment

- modal: Serverless cloud deployment platform

## File Structure

```
/
├── README.md
├── ARCHITECTURE.md
├── CHANGELOG.md
├── TROUBLESHOOTING.md
├── SUPABASE_SETUP.md
├── modal_app.py              ← Modal deployment config
├── server.py                 ← FastAPI backend (port 9999 local)
├── orchestrator.py           ← Pipeline orchestrator
├── requirements.txt
├── .env.example
├── frontend/
│   ├── index.html
│   ├── script.js
│   ├── style.css
│   ├── auth.js               ← Supabase Auth (Google OAuth)
│   ├── logo.png
│   └── favicon.png
├── execution/
│   ├── generate_assets.py
│   ├── generate_carousel.py
│   ├── viral_research_apify.py
│   ├── local_youtube.py
│   ├── apify_youtube.py
│   ├── rank_and_analyze.py
│   ├── regenerate_image.py
│   ├── regenerate_caption.py
│   ├── lead_scraper.py
│   ├── surveillance_scraper.py
│   ├── supabase_client.py
│   ├── baserow_logger.py
│   ├── cost_tracker.py
│   ├── jina_search.py
│   ├── ingest_source.py
│   └── linkedin_utils.py
├── directives/
│   ├── educational_caption.md
│   ├── storytelling_caption.md
│   ├── authority_caption.md
│   ├── promotional_caption.md
│   ├── image_prompt_design.md
│   ├── brand_knowledge.md
│   ├── color_palettes.json
│   └── style_types/
├── Web-Search-tool/
│   └── web_search.py
└── .tmp/                      ← Runtime artifacts (ephemeral on Modal)
    ├── source_content_*.txt
    ├── visual_context_*.json
    ├── youtube_research.json
    ├── viral_trends.json
    ├── final_plan.json
    └── generated_image_*.png
```
