# Troubleshooting Guide

## Common Issues and Solutions

### Server Issues

#### Issue: Server won't start - Port 9999 already in use
**Symptoms:**
```
OSError: [WinError 10048] Address already in use
```

**Solution:**
```bash
# Check what's using port 9999
netstat -ano | findstr ":9999"

# Kill the process
taskkill /PID <PID> /F

# Restart server
python server.py
```

**Prevention:**
- Always stop server before restarting: `Ctrl+C` in terminal

---

#### Issue: Server starts but UI not accessible
**Symptoms:**
- Server shows "Uvicorn running on http://0.0.0.0:9999"
- Browser shows "Connection refused" or "Unable to connect"

**Solution:**
```bash
# Check if server is actually running
netstat -ano | findstr ":9999"

# Try accessing via localhost
http://localhost:9999

# Check firewall settings
# Allow Python through Windows Firewall
```

---

### Generation Issues

#### Issue: No image generated when visual_aspect == "image"
**Symptoms:**
- visual_aspect set to "image"
- aspect_ratio selected
- No image in output

**Root Causes:**
1. Aspect ratio not sanitized
2. Image prompt contains colons
3. `should_generate_image` logic incorrect

**Solution 1: Check aspect ratio sanitization**
```python
# generate_assets.py lines 291-294
if aspect_ratio.lower() in ["image", "video", "carousel", "none", "null", "undefined"]:
    print(f">>> Warning: Invalid aspect ratio '{aspect_ratio}' detected. Defaulting to 16:9.")
    aspect_ratio = "16:9"
```

**Solution 2: Check colon removal**
```python
# generate_assets.py line 504
full_prompt = full_prompt.replace(":", " -")
```

**Solution 3: Check generation logic**
```python
# generate_assets.py lines 497-508
should_generate_image = post_type.lower() == "image" or str(visual_aspect).lower() == "image"

if should_generate_image:
    full_prompt = image_prompt_text if image_prompt_text else f"Professional {style} image about {topic}. Obsidian Black and Signal Yellow theme."
    full_prompt = full_prompt.replace(":", " -")
    # Generate image...
```

---

#### Issue: Carousel generation fails
**Symptoms:**
- visual_aspect set to "carousel"
- No carousel output
- Error in logs

**Root Causes:**
1. Routing logic not triggering
2. visual_context not passed
3. 3-phase generation fails

**Solution 1: Check routing logic**
```python
# orchestrator.py lines 145-149
if args.type.lower() == "carousel" or args.visual_aspect.lower() == "carousel":
    print(f">>> Routing to dedicated carousel generator...")
    gen_command = ["python", "execution/generate_carousel.py", 
                   "--topic", topic, "--purpose", args.purpose,
                   "--visual_context", args.visual_context]
else:
    gen_command = ["python", "execution/generate_assets.py", ...]
```

**Solution 2: Check visual_context passing**
```python
# orchestrator.py lines 148-149
if args.visual_context and os.path.exists(args.visual_context):
    gen_command.extend(["--visual_context", args.visual_context])
```

**Solution 3: Check 3-phase generation**
```python
# generate_carousel.py
def generate_carousel(topic, purpose, visual_context_path=None):
    # Phase 1: Plan Structure
    carousel_plan = plan_carousel_structure(topic, purpose, research_data, visual_desc)
    
    # Phase 2: Generate Slide Content
    slides_content = generate_slide_content(topic, purpose, carousel_plan, research_data)
    
    # Phase 3: Generate Caption
    caption = generate_caption(topic, purpose, carousel_plan, slides_content)
```

---

#### Issue: Output word count incorrect
**Symptoms:**
- Text type generates 300+ words
- Article type generates 100 words

**Root Cause:** LLM not following word count instructions

**Solution:**
Check prompt instructions in `generate_assets.py`:
```python
# generate_assets.py lines 410-412
**POST TYPE ADAPTATION ({post_type}):**
- If "text": Generate a standard LinkedIn post (150 words max). Concise, punchy, scroll-stopping. Single cohesive message.
- If "article": Generate a longer-form LinkedIn article-style post (300-500 words). Multi-paragraph structure with clear sections. More depth and detail.
```

**If still not working:**
- Strengthen the instruction: "STRICTLY limit to 150 words"
- Add word count to output validation
- Regenerate if word count outside range

---

### Visual Context Issues

#### Issue: Visual context not analyzed
**Symptoms:**
- Visual context indicator badge not showing
- No "X images analyzed" message
- Images/videos not in LLM prompt

**Root Causes:**
1. visual_context file not created
2. visualItems array empty
3. _build_visual_parts not called

**Solution 1: Check visual_context file creation**
```python
# server.py lines 84-98
# Only created when source_post_type is image/carousel/video/mixed
if req.source_post_type and req.source_post_type in ('image', 'carousel', 'video', 'mixed'):
    visual_ctx = {
        "source_post_type": req.source_post_type,
        "source_image_urls": req.source_image_urls or [],
        "source_carousel_slides": req.source_carousel_slides or [],
        "source_video_url": req.source_video_url or "",
        "source_video_urls": req.source_video_urls or []
    }
    visual_ctx_file = f".tmp/visual_context_{uuid.uuid4().hex[:8]}.json"
with open(visual_ctx_file, "w", encoding="utf-8") as f:
    json.dump(visual_context_data, f)
```

**Solution 2: Check visualItems aggregation**
```javascript
// script.js lines 771-790
const allImageUrls = [];
const allCarouselSlides = [];
const allVideoUrls = [];

for (const it of _repurposeItems) {
    if (!it) continue;
    if (it.type === 'image' && it.image_urls) {
        const urls = Array.isArray(it.image_urls) ? it.image_urls : [it.image_urls];
        allImageUrls.push(...urls.filter(u => u));
    }
    // ... similar for carousel and video
}
```

**Solution 3: Check _build_visual_parts**
```python
# generate_assets.py lines 11-85
def _build_visual_parts(visual_context_path):
    visual_parts = []
    visual_desc_parts = []
    
    if visual_context_path and os.path.exists(visual_context_path):
        with open(visual_context_path, 'r') as f:
            data = json.load(f)
        
        # Download images
        for url in data.get('images', []):
            response = requests.get(url)
            image_bytes = response.content
            visual_parts.append(genai.types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg"
            ))
            visual_desc_parts.append(f"- Image: {url}")
    
    return visual_parts, "\n".join(visual_desc_parts)
```

---

#### Issue: YouTube thumbnail not analyzed
**Symptoms:**
- YouTube repurpose shows no visual context
- Thumbnail not in visual_items

**Root Cause:** visualItems array empty for YouTube

**Solution:**
```javascript
// script.js lines 981-1002
card.querySelector('.repurpose-yt-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    console.log("Repurpose button clicked on YT card");
    
    // Intelligent source selection
    let source = item.transcript;
    if (!source || source.includes("No transcript") || source.includes("requires advanced")) {
        source = item.description;
    }
    
    // Create visual item with thumbnail if available
    const visualItems = [];
    if (item.thumbnail && item.thumbnail.startsWith('http')) {
        visualItems.push({
            type: 'image',
            image_urls: [item.thumbnail],
            title: item.title,
            author_name: item.channelName
        });
    }
    
    openRepurposeModal(source || "YouTube Content", 'youtube', visualItems);
});
```

---

### Temp File Issues

#### Issue: Files deleted before being read
**Symptoms:**
- Error: "FileNotFoundError: .tmp/source_content.txt"
- visual_context file missing
- Generation fails

**Root Cause:** `clear_temp_directory()` deletes files before reading

**Solution:**
```python
# orchestrator.py lines 59-102
def clear_temp_directory():
    # PRE-CLEAR: Read files into memory
    source_content = ""
    visual_context = ""
    
    if os.path.exists(source_content_path):
        with open(source_content_path, 'r') as f:
            source_content = f.read()
    
    if os.path.exists(visual_context_path):
        with open(visual_context_path, 'r') as f:
            visual_context = f.read()
    
    # Clear .tmp directory
    for file in os.listdir(".tmp"):
        os.remove(os.path.join(".tmp", file))
    
    # POST-CLEAR: Rewrite files from memory
    if source_content:
        with open(source_content_path, 'w') as f:
            f.write(source_content)
    
    if visual_context:
        with open(visual_context_path, 'w') as f:
            f.write(visual_context)
```

---

#### Issue: CLI length limits for large source_content
**Symptoms:**
- Windows command line length exceeded
- subprocess.run fails
- Error: "The command line is too long"

**Solution:**
```python
# orchestrator.py lines 121-142
# Write source_content to temp file instead of passing as argument
source_content_path = os.path.join(".tmp", f"source_content_{int(time.time())}.txt")
with open(source_content_path, 'w', encoding='utf-8') as f:
    f.write(args.source_content)

# Pass file path instead of content
gen_command.extend(["--source_content", source_content_path])
```

---

### YouTube Issues

#### Issue: YouTube transcript extraction fails
**Symptoms:**
- "No transcript available" message
- Transcript empty
- Error in local_youtube.py

**Root Causes:**
1. yt-dlp not installed
2. Video has no captions
3. Network issues

**Solution 1: Install yt-dlp**
```bash
pip install yt-dlp
```

**Solution 2: Check video has captions**
```python
# local_youtube.py lines 38-60
captions = info.get('subtitles') or info.get('automatic_captions') or {}
if not captions:
    transcript = "No transcript available."
else:
    # Find English track
    en_track = None
    for lang in captions:
        if lang.startswith('en'):
            formats = captions[lang]
            vtt = next((f for f in formats if f['ext'] == 'vtt'), None)
            if vtt:
                en_track = vtt['url']
                break
```

**Solution 3: Add error handling**
```python
# local_youtube.py lines 119-132
except Exception as e:
    print(f"Error processing {url}: {e}")
    results.append({
        "title": "Error fetching video",
        "url": url,
        "description": str(e),
        "transcript": "",
        ...
    })
```

---

#### Issue: YouTube video URL invalid
**Symptoms:**
- "Error fetching video"
- Invalid URL format

**Solution:**
```javascript
// Add URL validation in frontend
function isValidYouTubeUrl(url) {
    const pattern = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+/;
    return pattern.test(url);
}

// Validate before sending
if (!isValidYouTubeUrl(url)) {
    alert("Invalid YouTube URL");
    return;
}
```

---

### API Issues

#### Issue: /api/generate returns 422 Unprocessable Entity (YouTube Repurpose)
**Symptoms:**
- UI shows "Drafting failed: undefined"
- Server logs show `POST /api/generate HTTP/1.1" 422 Unprocessable Entity`
- Only happens when repurposing from YouTube tab (or any flow that sends `null` values)

**Root Cause:** `GenerateRequest` Pydantic model used bare `str = None` and `list = None` types. When the frontend sent JSON `null` for nullable fields like `source_video_urls`, Pydantic rejected them. Additionally, the frontend only checked `result.error` but FastAPI's 422 response uses `result.detail`, so the error message showed as "undefined".

**Solution (applied in `server.py`):**
```python
from typing import Optional, List
from fastapi.exceptions import RequestValidationError

# 1. Use Optional types in Pydantic model
class GenerateRequest(BaseModel):
    action: str
    source: Optional[str] = None          # NOT bare str = None
    source_image_urls: Optional[List[str]] = None  # NOT bare list = None
    source_video_urls: Optional[List[str]] = None
    # ... etc

# 2. Add validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    body = await request.body()
    print(f">>> VALIDATION ERROR: {exc.errors()}")
    print(f">>> Body (first 500 chars): {body[:500]}")
    return JSONResponse(status_code=422, content={"error": str(exc.errors()), "detail": str(exc.errors())})
```

**Frontend fix (applied in `script.js`):**
```javascript
// Check error OR detail OR stringify the whole response
const errMsg = result.error || result.detail || JSON.stringify(result);
addSystemLog(`Drafting failed: ${errMsg}`, 'error');
```

**YouTube null safety fix (applied in `script.js`):**
```javascript
// Guard chain prevents crash if thumbnail is undefined
if (item.thumbnail && item.thumbnail.startsWith && item.thumbnail.startsWith('http')) {
    visualItems.push({
        type: 'image',
        image_urls: [item.thumbnail],
        title: item.title || 'YouTube Video',
        author_name: item.channelName || 'Unknown Channel'
    });
}
```

---

#### Issue: /api/generate returns 500 error
**Symptoms:**
- Error message in response
- Generation fails

**Debug Steps:**
1. Check server logs for detailed error
2. Verify all required fields present
3. Check temp files exist
4. Verify environment variables set

**Solution:**
```python
# server.py - Add better error handling
try:
    process = subprocess.run(command, capture_output=True, text=True, ...)
    if process.returncode != 0:
        error_info = process.stderr or process.stdout or "Generation failed."
        return JSONResponse(status_code=500, content={"error": error_info})
except Exception as e:
    return JSONResponse(status_code=500, content={"error": str(e)})
```

---

#### Issue: /api/research/youtube returns error
**Symptoms:**
- YouTube research fails
- Error in response

**Root Causes:**
1. local_youtube.py not found
2. yt-dlp not installed
3. Network issues

**Solution:**
```python
# server.py lines 397-400
command = ["python", "execution/local_youtube.py", "--urls", urls_str]
process = subprocess.run(command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8')
if process.returncode != 0:
    error_info = process.stderr or process.stdout or "YouTube research failed."
    return JSONResponse(status_code=500, content={"error": error_info})
```

---

### UI Issues

#### Issue: Repurpose modal not showing visual context indicator
**Symptoms:**
- Visual context badge hidden
- No media count shown

**Solution:**
```javascript
// script.js lines 720-737
const vizIndicator = document.getElementById('repurpose-visual-indicator');
if (vizIndicator) {
    const mediaItems = _repurposeItems.filter(it => it && (it.type === 'image' || it.type === 'carousel' || it.type === 'video'));
    if (mediaItems.length > 0) {
        const imgCount = mediaItems.filter(it => it.type === 'image').length;
        const carCount = mediaItems.filter(it => it.type === 'carousel').length;
        const vidCount = mediaItems.filter(it => it.type === 'video').length;
        const parts = [];
        if (imgCount) parts.push(`${imgCount} image${imgCount > 1 ? 's' : ''} analyzed`);
        if (carCount) parts.push(`${carCount} carousel${carCount > 1 ? 's' : ''} analyzed`);
        if (vidCount) parts.push(`${vidCount} video${vidCount > 1 ? 's' : ''} transcribed`);
        vizIndicator.innerHTML = `<i data-lucide="eye"></i> ${parts.join(' · ')}`;
        vizIndicator.classList.remove('hidden');
    } else {
        vizIndicator.classList.add('hidden');
    }
}
```

---

#### Issue: Aspect ratio dropdown not showing
**Symptoms:**
- Aspect ratio group hidden
- Can't select aspect ratio

**Root Cause:** visual_aspect change handler not triggering

**Solution:**
```javascript
// script.js lines 745-765
repurposeVisualAspect.addEventListener('change', () => {
    const aspect = repurposeVisualAspect.value;
    const aspectRatioGroup = document.getElementById('repurpose-aspect-ratio-group');
    
    if (aspect === 'none') {
        repurposeVisualStyleGroup.style.display = 'none';
        if (aspectRatioGroup) aspectRatioGroup.style.display = 'none';
    } else {
        repurposeVisualStyleGroup.style.display = 'block';
        repurposeVisualStyle.innerHTML = '';
        const options = visualStyleOptions[aspect] || [];
        options.forEach(opt => {
            const o = document.createElement('option');
            o.value = opt.value;
            o.textContent = opt.label;
            repurposeVisualStyle.appendChild(o);
        });
        // Show aspect ratio only for image
        if (aspectRatioGroup) {
            aspectRatioGroup.style.display = aspect === 'image' ? 'grid' : 'none';
        }
    }
});
```

---

### LLM Issues

#### Issue: LLM not following instructions
**Symptoms:**
- Output doesn't match routing instructions
- Word count incorrect
- Wrong tone/style

**Solution:**
1. Strengthen prompt instructions
2. Add explicit constraints
3. Use "STRICTLY" for critical rules
4. Add output validation

**Example:**
```python
# generate_assets.py
**POST TYPE ADAPTATION ({post_type}):**
- If "text": STRICTLY limit to 150 words max. Concise, punchy, scroll-stopping. Single cohesive message.
- If "article": STRICTLY write 300-500 words. Multi-paragraph structure with clear sections. More depth and detail.
```

---

#### Issue: LLM hallucinating information
**Symptoms:**
- Output contains facts not in source
- Made-up statistics
- Incorrect claims

**Solution:**
```python
# Add to mega prompt
**STRICT CONSTRAINTS:**
- ONLY use information provided in the source content
- DO NOT hallucinate or make up facts
- If information is missing, state that explicitly
- Attribute all claims to source when possible
```

---

### SSE / Progress Tracker Issues

#### Issue: Progress stepper not showing during generation
**Symptoms:**
- Output console stays on empty state
- No horizontal stepper visible
- Generation completes but no progress was shown

**Root Causes:**
1. Frontend using `/api/generate` instead of `/api/generate-stream`
2. `#generation-progress` element missing or has wrong ID
3. `lucide.createIcons()` not called after showing progress

**Solution:**
- Verify main form and repurpose handlers use `generateWithSSE()` (not direct `fetch` to `/api/generate`)
- Check that `#generation-progress` exists in HTML between `#empty-state` and `#results-content`
- Ensure `showProgress()` is called which removes `.hidden` class

---

#### Issue: Progress stepper stuck on active (never completes)
**Symptoms:**
- Circle keeps pulsing gold indefinitely
- No green checkmark appears
- Generation may have actually completed

**Root Causes:**
1. `>>>STAGE:` markers not being printed by `generate_assets.py`
2. SSE events not being parsed correctly in frontend
3. Subprocess stdout not being flushed

**Solution:**
```python
# Verify markers exist in generate_assets.py:
print(">>>STAGE:text_start")   # Before call_llm()
print(">>>STAGE:text_done")    # After call_llm()
print(">>>STAGE:image_start")  # Before generate_image_asset()
print(">>>STAGE:image_done")   # After generate_image_asset()
```
- Check server.py SSE endpoint reads stdout line-by-line and detects `>>>STAGE:` prefix
- Ensure `generate_assets.py` stdout is not buffered (Python's `-u` flag or `PYTHONUNBUFFERED=1`)

---

#### Issue: Completion sound plays multiple times
**Symptoms:**
- "Ding" sound fires 2-3 times when generation completes

**Root Cause:** `addSystemLog()` with `'success'` type triggers `playSystemSound()`. If per-stage logs use `'success'`, sound fires for each stage + final completion.

**Solution (already applied):**
- Per-stage logs in `setStage()` use `'info'` type (no sound)
- Only the final "Neural generation sequence complete" log uses `'success'` type
```javascript
// setStage() uses 'info' — no sound
addSystemLog('Text generation complete \u2713', 'info');
addSystemLog('Image generation complete \u2713', 'info');

// Final completion uses 'success' — plays sound once
addSystemLog('Neural generation sequence complete \u2713', 'success');
```

---

#### Issue: Connector line not animating between steps
**Symptoms:**
- Circles change state but horizontal line stays gray

**Root Cause:** CSS sibling selectors not matching. The `.stepper-connector` must be a direct sibling after the first `.progress-stage`.

**Solution:**
- Verify HTML structure: `.progress-stage#stage-text` + `.stepper-connector` + `.progress-stage#stage-image`
- CSS uses `.progress-stage.active + .stepper-connector .stepper-connector-fill` and `.progress-stage.done + .stepper-connector .stepper-connector-fill`

---

#### Issue: Unicode/emoji characters broken in SSE stream
**Symptoms:**
- Emojis in captions display as `\uXXXX` escape sequences

**Root Cause:** `json.dumps()` defaults to `ensure_ascii=True`

**Solution (already applied in server.py):**
```python
yield f"event: result\ndata: {json.dumps(result_data, ensure_ascii=False)}\n\n"
```

---

### Performance Issues

#### Issue: Slow generation times
**Symptoms:**
- Generation takes > 60 seconds
- Timeout errors
- Poor user experience

**Solutions:**
1. Cache generated content
2. Use smaller image sizes for previews
3. SSE streaming already implemented for real-time feedback
4. Optimize LLM prompt length

**Example:**
```python
# Add timeout
response = client.models.generate_content(
    model=model_name,
    config=config,
    contents=user_content,
    timeout=60  # 60 second timeout
)
```

---

#### Issue: Memory usage high
**Symptoms:**
- System slows down
- Out of memory errors
- Crashes

**Solutions:**
1. Clear temp files regularly
2. Limit concurrent generations
3. Stream large responses
4. Use pagination for research results

---

## Debugging Tips

### Enable Verbose Logging
```python
# Add to orchestrator.py
import logging
logging.basicConfig(level=logging.DEBUG)

# Add debug prints
print(f">>> DEBUG: visual_context_path = {visual_context_path}")
print(f">>> DEBUG: source_content_path = {source_content_path}")
```

### Check Temp Files
```bash
# List all temp files
dir .tmp

# Check file contents
type .tmp\final_plan.json
type .tmp\visual_context_*.json
type .tmp\source_content_*.txt
```

### Monitor Network Requests
1. Open browser DevTools (F12)
2. Go to Network tab
3. Click Generate
4. Check `/api/generate` request
5. Verify payload structure
6. Check response status

### Check Server Logs
```bash
# Server logs show detailed errors
# Look for:
# - "Error:" messages
# - Stack traces
# - File not found errors
```

### Test Individual Components
```bash
# Test YouTube scraper
python execution/local_youtube.py --urls https://youtube.com/watch?v=VIDEO_ID

# Test carousel generator
python execution/generate_carousel.py --topic "Test" --purpose educational

# Test asset generator
python execution/generate_assets.py --type text --purpose educational --topic "Test" --visual_aspect none
```

## Common Error Messages

### "No directive found for purpose: X"
**Cause:** Directive file missing
**Solution:** Create `directives/X_caption.md`

### "Invalid aspect ratio 'image' detected"
**Cause:** Aspect ratio not sanitized
**Solution:** Check sanitization logic in generate_assets.py

### "visual_context file not found"
**Cause:** File deleted before read
**Solution:** Check PRE-CLEAR/POST-CLEAR pattern

### "YouTube research failed"
**Cause:** local_youtube.py error
**Solution:** Check yt-dlp installation and video URL

### "Carousel generation failed"
**Cause:** 3-phase generation error
**Solution:** Check each phase logs

### "Image generation failed"
**Cause:** Image service error
**Solution:** Check image service status and prompt format

### "Drafting failed: undefined"
**Cause:** Pydantic 422 validation error. `GenerateRequest` model used `str = None` / `list = None` instead of `Optional[str]` / `Optional[List[str]]`. Frontend sends JSON `null` for empty fields, which bare types reject. Also, frontend only checked `result.error` but FastAPI 422 returns `result.detail`.
**Solution:** 
1. Use `Optional[str]` and `Optional[List[str]]` in `GenerateRequest` (server.py lines 42-57)
2. Add `RequestValidationError` handler (server.py lines 20-26)
3. Frontend: check `result.error || result.detail || JSON.stringify(result)` (script.js line 846)

### "422 Unprocessable Entity" in server logs
**Cause:** Pydantic model type mismatch — frontend sending `null` for fields typed as non-Optional
**Solution:** Ensure all nullable fields use `Optional[type]` from `typing` module. Check server console for `>>> VALIDATION ERROR` log with exact field details.

## Getting Help

### Before Asking for Help:
1. Check this guide
2. Check server logs
3. Test individual components
4. Verify environment variables
5. Check temp files

### When Asking for Help:
1. Provide error message
2. Share server logs
3. Describe what you were doing
4. Include configuration details
5. Mention recent changes

## Prevention Checklist

### Before Starting Work:
- [ ] Server not running on port 9999
- [ ] Environment variables set
- [ ] Dependencies installed
- [ ] Temp directory exists
- [ ] Directive files present

### Before Generating:
- [ ] Topic entered
- [ ] Purpose selected
- [ ] Visual aspect selected
- [ ] Aspect ratio correct (if image)
- [ ] Source content provided (if repurposing)

### After Generation:
- [ ] Check final_plan.json
- [ ] Verify word count
- [ ] Check image generated (if needed)
- [ ] Verify tone matches purpose
- [ ] Clear temp files if needed

## Summary

This guide covers:
- Server issues (startup, accessibility)
- Generation issues (images, carousels, word count)
- Visual context issues (analysis, thumbnails)
- Temp file issues (deletion, CLI limits)
- YouTube issues (transcripts, URLs)
- API issues (500 errors, research failures)
- UI issues (modals, dropdowns)
- LLM issues (instructions, hallucinations)
- **SSE / Progress tracker issues** (stepper stuck, sound, connector line, unicode)
- Performance issues (speed, memory)

For more details:
- `README.md` - Overview and setup
- `ARCHITECTURE.md` - Technical details
- `ROUTING.md` - 128 routing matrix
- `WORKFLOWS.md` - Common workflows
