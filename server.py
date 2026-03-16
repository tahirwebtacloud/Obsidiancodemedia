import uuid
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.exceptions import RequestValidationError
import os
import subprocess
import json
import time
from typing import Optional, List

# Load environment variables
load_dotenv()
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
import asyncio
from pydantic import BaseModel

app = FastAPI()

# Ensure execution/ is on sys.path so that direct imports from execution modules
# can find sibling modules like cost_tracker.py
import sys as _sys
_exec_dir = os.path.join(os.path.dirname(__file__), "execution")
if _exec_dir not in _sys.path:
    _sys.path.insert(0, _exec_dir)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    print(f"\n>>> VALIDATION ERROR on {request.url}")
    print(f">>> Errors: {exc.errors()}")
    print(f">>> Body (first 500 chars): {body[:500]}")
    return JSONResponse(status_code=422, content={"error": str(exc.errors()), "detail": str(exc.errors())})

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("frontend/favicon.png")

# Force Python subprocesses to use UTF-8 output
RUN_ENV = os.environ.copy()
RUN_ENV["PYTHONIOENCODING"] = "utf-8"

# Mount frontend files
# Mount frontend files logic moved to end of file to allow API routes to take precedence

# Serve .tmp as assets for previewing generated images
app.mount("/assets", StaticFiles(directory=".tmp"), name="assets")

@app.on_event("startup")
async def startup_event():
    # NOTE: Surveillance scrape on startup is disabled because there is no
    # authenticated user context available at server start.  Users trigger
    # refreshes manually via the UI which supplies their UID.
    pass

class GenerateRequest(BaseModel):
    action: str
    user_id: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    topic: Optional[str] = None
    custom_topic: Optional[str] = None
    type: str = "text"
    purpose: str = "educational"
    visual_aspect: Optional[str] = None
    visual_style: Optional[str] = None
    style_type: Optional[str] = None
    aspect_ratio: str = "16:9"
    color_palette: str = "brand"
    source_content: Optional[str] = None
    source_post_type: Optional[str] = None
    source_image_urls: Optional[List[str]] = None
    source_carousel_slides: Optional[List[str]] = None
    source_video_url: Optional[str] = None
    source_video_urls: Optional[List[str]] = None
    reference_image: Optional[str] = None

@app.post("/api/generate")
async def generate_post(req: GenerateRequest, request: Request):
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", req.user_id or "default"))
    print(f"Received generation request: {req.action} | Aspect Ratio: {req.aspect_ratio} | Visual Aspect: {req.visual_aspect} | Style: {req.visual_style} | Style Type: {req.style_type}")
    
    # Construct orchestrator command
    # Add --preview to skip auto-saving defaults
    command = ["python", "orchestrator.py", "--action", req.action, "--preview"]
    
    if req.source: command.extend(["--source", req.source])
    if req.url: command.extend(["--url", req.url])
    if req.topic: command.extend(["--topic", req.topic])
    if req.type: command.extend(["--type", req.type])
    if req.purpose: command.extend(["--purpose", req.purpose])
    if req.visual_style: command.extend(["--style", req.visual_style])
    if req.visual_aspect: command.extend(["--visual_aspect", req.visual_aspect])
    if req.style_type: command.extend(["--style_type", req.style_type])
    if req.aspect_ratio: command.extend(["--aspect_ratio", req.aspect_ratio])
    if req.color_palette: command.extend(["--color_palette", req.color_palette])
    
    # FIX: Write long source_content to temp file to avoid WinError 206
    if req.source_content:
        os.makedirs(".tmp", exist_ok=True)
        temp_file = f".tmp/source_payload_{uuid.uuid4().hex[:8]}.txt"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(req.source_content)
        command.extend(["--source_content", temp_file])

    # Decode and save reference image if provided (base64 data URL)
    if req.reference_image and req.reference_image.startswith('data:'):
        import base64
        os.makedirs(".tmp", exist_ok=True)
        # Parse data URL: data:image/png;base64,xxxxx
        header, b64data = req.reference_image.split(',', 1)
        ext = 'png'
        if 'jpeg' in header or 'jpg' in header:
            ext = 'jpg'
        elif 'webp' in header:
            ext = 'webp'
        ref_img_path = f".tmp/ref_image_{uuid.uuid4().hex[:8]}.{ext}"
        with open(ref_img_path, 'wb') as f:
            f.write(base64.b64decode(b64data))
        command.extend(["--reference_image", ref_img_path])
        print(f"Reference image saved: {ref_img_path}")

    # Write visual context (images, carousel slides, video URLs) to temp JSON
    if req.source_post_type and req.source_post_type in ('image', 'carousel', 'video', 'mixed'):
        os.makedirs(".tmp", exist_ok=True)
        visual_ctx = {
            "source_post_type": req.source_post_type,
            "source_image_urls": req.source_image_urls or [],
            "source_carousel_slides": req.source_carousel_slides or [],
            "source_video_url": req.source_video_url or "",
            "source_video_urls": req.source_video_urls or []
        }
        visual_ctx_file = f".tmp/visual_context_{uuid.uuid4().hex[:8]}.json"
        with open(visual_ctx_file, "w", encoding="utf-8") as f:
            json.dump(visual_ctx, f)
        command.extend(["--visual_context", visual_ctx_file])
        print(f"Visual context: type={req.source_post_type} images={len(req.source_image_urls or [])} slides={len(req.source_carousel_slides or [])} videos={len(req.source_video_urls or [])}")
        

    print(f"Executing: {' '.join(command)}")
    
    try:
        process = subprocess.run(command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8', errors='replace')
        
        if process.returncode != 0:
            return JSONResponse(status_code=500, content={"error": process.stderr or process.stdout or f"Orchestrator exited with code {process.returncode}", "stdout": process.stdout[-2000:] if process.stdout else "", "stderr": process.stderr[-2000:] if process.stderr else "", "returncode": process.returncode})
        
        # Determine result file based on action
        result_file = ".tmp/final_plan.json"
        
        if os.path.exists(result_file):
            with open(result_file, "r", encoding="utf-8") as f:
                result_data = json.load(f)
            
            _save_history_entry(req, result_data, uid_override=uid)
            
            return result_data
        else:
            return JSONResponse(status_code=500, content={"error": "Orchestrator completed but no output file found.", "details": process.stdout})
            
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

def _build_orchestrator_command(req):
    """Build the orchestrator command list from a GenerateRequest. Shared by /api/generate and /api/generate-stream."""
    command = ["python", "-u", "orchestrator.py", "--action", req.action, "--preview"]
    
    if req.source: command.extend(["--source", req.source])
    if req.url: command.extend(["--url", req.url])
    if req.topic: command.extend(["--topic", req.topic])
    if req.type: command.extend(["--type", req.type])
    if req.purpose: command.extend(["--purpose", req.purpose])
    if req.visual_style: command.extend(["--style", req.visual_style])
    if req.visual_aspect: command.extend(["--visual_aspect", req.visual_aspect])
    if req.style_type: command.extend(["--style_type", req.style_type])
    if req.aspect_ratio: command.extend(["--aspect_ratio", req.aspect_ratio])
    if req.color_palette: command.extend(["--color_palette", req.color_palette])
    
    if req.source_content:
        os.makedirs(".tmp", exist_ok=True)
        temp_file = f".tmp/source_payload_{uuid.uuid4().hex[:8]}.txt"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(req.source_content)
        command.extend(["--source_content", temp_file])

    if req.reference_image and req.reference_image.startswith('data:'):
        import base64
        os.makedirs(".tmp", exist_ok=True)
        header, b64data = req.reference_image.split(',', 1)
        ext = 'png'
        if 'jpeg' in header or 'jpg' in header:
            ext = 'jpg'
        elif 'webp' in header:
            ext = 'webp'
        ref_img_path = f".tmp/ref_image_{uuid.uuid4().hex[:8]}.{ext}"
        with open(ref_img_path, 'wb') as f:
            f.write(base64.b64decode(b64data))
        command.extend(["--reference_image", ref_img_path])

    if req.source_post_type and req.source_post_type in ('image', 'carousel', 'video', 'mixed'):
        os.makedirs(".tmp", exist_ok=True)
        visual_ctx = {
            "source_post_type": req.source_post_type,
            "source_image_urls": req.source_image_urls or [],
            "source_carousel_slides": req.source_carousel_slides or [],
            "source_video_url": req.source_video_url or "",
            "source_video_urls": req.source_video_urls or []
        }
        visual_ctx_file = f".tmp/visual_context_{uuid.uuid4().hex[:8]}.json"
        with open(visual_ctx_file, "w", encoding="utf-8") as f:
            json.dump(visual_ctx, f)
        command.extend(["--visual_context", visual_ctx_file])

    return command

def _get_run_costs():
    cost_file = ".tmp/run_costs_default.json"
    costs = []
    total_cost = 0.0
    duration_ms = 0
    if os.path.exists(cost_file):
        try:
            with open(cost_file, "r", encoding="utf-8") as f:
                cdata = json.load(f)
                costs = cdata.get("costs", [])
                total_cost = cdata.get("total_cost", 0.0)
                duration_ms = cdata.get("duration_ms", 0)
        except Exception:
            pass
    return costs, total_cost, duration_ms

def _save_history_entry(req, result_data, run_type="generate", input_summary=None, full_results=None, error_message=None, uid_override=None):
    """Save a history entry. Combines both generation and research runs."""
    from execution.supabase_client import add_history_entry
    user_id = uid_override or getattr(req, "user_id", None) or "default"
    
    costs, total_cost, duration_ms = _get_run_costs()
    
    # Auto-generate summary for generation if none provided
    if not input_summary and run_type == "generate":
        input_summary = f"[{req.type.upper()}] {req.topic or req.source or 'Unknown'}"

    status = "success" if not error_message else "error"

    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": int(time.time() * 1000),
        "type": run_type,
        "status": status,
        "input_summary": input_summary,
        "topic": getattr(req, "topic", "Modern AI"),
        "purpose": getattr(req, "purpose", None),
        "style": getattr(req, "visual_style", "minimal"),
        "params": req.dict() if hasattr(req, "dict") else {},
        
        "caption": result_data.get("caption", ""),
        "full_caption": result_data.get("caption", ""),
        "asset_url": result_data.get("asset_url", ""),
        "final_image_prompt": result_data.get("final_image_prompt", ""),
        
        "full_results": full_results,
        "error_message": error_message,
        
        "costs": costs,
        "total_cost": total_cost,
        "duration_ms": duration_ms,
        
        "approved": False
    }
    
    add_history_entry(entry, uid=user_id)


@app.post("/api/generate-stream")
async def generate_post_stream(req: GenerateRequest, request: Request):
    """SSE streaming endpoint that emits real-time progress events during generation."""
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", req.user_id or "default"))
    print(f"[SSE] Received streaming generation request: {req.action}")
    
    command = _build_orchestrator_command(req)
    print(f"[SSE] Executing: {' '.join(command)}")

    async def event_generator():
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=RUN_ENV,
            encoding='utf-8',
            errors='replace',
            bufsize=1
        )

        try:
            while True:
                line = await asyncio.to_thread(proc.stdout.readline)
                if not line and proc.poll() is not None:
                    break
                line = line.strip()
                if not line:
                    continue

                if line.startswith(">>>STAGE:"):
                    stage = line.replace(">>>STAGE:", "").strip()
                    yield f"event: stage\ndata: {json.dumps({'stage': stage})}\n\n"
                else:
                    print(f"[SSE stdout] {line}")

            proc.wait()

            if proc.returncode != 0:
                stderr_out = proc.stderr.read() if proc.stderr else ""
                yield f"event: error\ndata: {json.dumps({'error': stderr_out or 'Orchestrator failed'})}\n\n"
                return

            result_file = ".tmp/final_plan.json"
            if os.path.exists(result_file):
                with open(result_file, "r", encoding="utf-8") as f:
                    result_data = json.load(f)
                
                _save_history_entry(req, result_data, uid_override=uid)
                yield f"event: result\ndata: {json.dumps(result_data, ensure_ascii=False)}\n\n"
            else:
                yield f"event: error\ndata: {json.dumps({'error': 'No output file found'})}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if proc.poll() is None:
                proc.kill()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


class SaveRequest(BaseModel):
    user_id: Optional[str] = None
    post_data: dict

@app.post("/api/save")
async def save_post(req: SaveRequest):
    print("Received save request.")
    try:
        # Write data to a temp file for the logger to read
        temp_file = ".tmp/manual_save.json"
        
        # Ensure .tmp exists
        os.makedirs(".tmp", exist_ok=True)
        
        # Wrap in expected structure for baserow_logger if needed, or pass directly.
        # baserow_logger for 'posts' expects a dict with keys: caption, type, asset_prompts
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(req.post_data, f, ensure_ascii=False)
            
        print(f"Data written to {temp_file}")

        # Run baserow_logger
        # Usage: python execution/baserow_logger.py --type posts --path .tmp/manual_save.json
        command = ["python", "execution/baserow_logger.py", "--type", "posts", "--path", temp_file]
        
        print(f"Executing logger: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8')
        
        if result.returncode != 0:
            print(f"Logger Error: {result.stderr}")
            # Combine stderr and stdout for debugging
            combined_error = f"STDERR: {result.stderr}\nSTDOUT: {result.stdout}"
            return JSONResponse(status_code=500, content={"error": combined_error})
            
        print(f"Logger Output: {result.stdout}")
        return {"message": "Successfully saved to Baserow", "details": result.stdout}

    except Exception as e:
        print(f"Exception in save: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

class RegenerateImageRequest(BaseModel):
    user_id: Optional[str] = None
    caption: str = ""
    style: str = "minimal"
    aspect_ratio: str = "16:9"
    instructions: str = ""
    source_image: str = ""
    history_entry: dict = None
    mode: str = "refine" # "refine" (VLM+IDM) or "tweak" (Text-to-Image)
    prompt: str = "" # For 'tweak' mode
    color_palette: str = "brand"
    reference_image: Optional[str] = None # base64 data URL for reference image

@app.post("/api/regenerate-image")
async def regenerate_image(req: RegenerateImageRequest, request: Request):
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", req.user_id or "default"))
    print(f"Regenerating Image. Mode: {req.mode}")
    
    # Helper to save history per-user
    def save_history(entry):
        from execution.supabase_client import add_history_entry
        add_history_entry(entry, uid=uid)

    # 1. Save Pre-Regen State (Old Image)
    if req.history_entry:
        save_history(req.history_entry)
        print("Saved previous state to history.")

    try:
        new_asset_url = None
        new_prompt = ""

        # MODE: TWEAK (Direct Text-to-Image)
        if req.mode == "tweak":
            from execution.generate_assets import generate_image_asset, _composite_logo
            
            print(f"DEBUG TWEAK START: Prompt='{req.prompt}' Aspect='{req.aspect_ratio}' Palette='{req.color_palette}'")
            # Call generation function directly
            new_asset_url, error = generate_image_asset(req.prompt, req.aspect_ratio)
            new_prompt = req.prompt 
            print(f"DEBUG TWEAK RESULT: URL='{new_asset_url}' Error='{error}'")
            
            if not new_asset_url: return JSONResponse(status_code=500, content={"error": error})

            # Composite logo onto the regenerated image
            local_path = new_asset_url.replace("/assets/", ".tmp/")
            _composite_logo(local_path, logo_variant="auto", logo_position="auto")

        # MODE: REFINE (VLM + IDM)
        else:
            command = [
                "python", "execution/regenerate_image.py", 
                "--caption", req.caption,
                "--style", req.style,
                "--aspect_ratio", req.aspect_ratio,
                "--color_palette", req.color_palette
            ]
            
            if req.instructions:
                command.extend(["--instructions", req.instructions])
            
            if req.source_image:
                # Convert URL to local path
                # URL: /assets/filename.png -> Local: .tmp/filename.png
                if "/assets/" in req.source_image:
                    local_path = req.source_image.replace("/assets/", ".tmp/")
                    # Remove query params if any
                    if "?" in local_path:
                        local_path = local_path.split("?")[0]
                    
                    if os.path.exists(local_path):
                        command.extend(["--source_image", local_path])
                    else:
                        print(f"Warning: Source image not found at {local_path}")
            
            print(f"Executing: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8')
            
            if result.returncode != 0:
                print(f"Regenerate Error: {result.stderr}")
                return JSONResponse(status_code=500, content={"error": result.stderr})
            
            # Read the result
            result_file = ".tmp/regenerated_image.json"
            if os.path.exists(result_file):
                with open(result_file, "r", encoding="utf-8") as f:
                    result_data = json.load(f)
                
                if "error" in result_data:
                     return JSONResponse(status_code=500, content={"error": result_data["error"]})
                
                new_asset_url = result_data.get("asset_url")
                new_prompt = result_data.get("final_image_prompt", "")

                # Composite logo onto refined image
                if new_asset_url:
                    from execution.generate_assets import _composite_logo
                    local_path = new_asset_url.replace("/assets/", ".tmp/")
                    _composite_logo(local_path, logo_variant="auto", logo_position="auto")
            else:
                return JSONResponse(status_code=500, content={"error": "Result file not found"})

        # 2. Save Post-Regen State (New Image) to History
        if new_asset_url and req.history_entry:
            import time
            import uuid
            new_entry = req.history_entry.copy()
            new_entry['asset_url'] = new_asset_url
            new_entry['final_image_prompt'] = new_prompt
            new_entry['id'] = str(uuid.uuid4())
            new_entry['timestamp'] = int(time.time() * 1000)
            # Mark as unapproved draft? Or keep original status? Usually reset approval.
            new_entry['approved'] = False 
            
            save_history(new_entry)
            print("Saved NEW state to history.")

        return {"asset_url": new_asset_url, "final_image_prompt": new_prompt}

            
    except Exception as e:
        print(f"Exception in regenerate: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

class RegenerateCaptionRequest(BaseModel):
    user_id: Optional[str] = None
    topic: str
    purpose: str
    type: str
    style: str = "minimal"
    instructions: str = None

@app.post("/api/regenerate-caption")
async def regenerate_caption(req: RegenerateCaptionRequest):
    print("Received regenerate caption request.")
    try:
        command = ["python", "execution/regenerate_caption.py", "--topic", req.topic, "--purpose", req.purpose, "--type", req.type, "--style", req.style]
        
        if req.instructions:
            command.extend(["--instructions", req.instructions])
            
        print(f"Executing: {' '.join(command)}")
        
        result = subprocess.run(command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8')
        
        if result.returncode != 0:
            return JSONResponse(status_code=500, content={"error": result.stderr})
            
        # Parse output - script prints JSON at the end
        # We need to find the JSON part if there are other prints
        lines = result.stdout.strip().split('\n')
        json_output = lines[-1] 
        try:
            data = json.loads(json_output)
            return data
        except:
             return JSONResponse(status_code=500, content={"error": "Invalid JSON from script", "details": result.stdout})
             
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/history")
async def get_history(userId: str = None, request: Request = None):
    from execution.supabase_client import get_user_history
    uid = userId or (request.headers.get("X-User-ID") if request else None) or "default"
    return get_user_history(uid=uid)

# --- RESEARCH ENDPOINTS ---

def _clear_costs():
    cost_file = ".tmp/run_costs_default.json"
    if os.path.exists(cost_file):
        try:
            os.remove(cost_file)
        except:
            pass

class ResearchRequest(BaseModel):
    user_id: Optional[str] = None
    topic: str = None
    urls: list = None
    deep_search: bool = False

@app.post("/api/research/viral")
async def research_viral(req: ResearchRequest, request: Request):
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", req.user_id or "default"))
    print(f"Viral research request for: {req.topic}")
    _clear_costs()
    command = ["python", "execution/viral_research_apify.py", "--topic", req.topic]
    process = subprocess.run(command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8')
    
    if process.returncode != 0:
        error_msg = process.stderr or "Viral research failed."
        _save_history_entry(req, {}, run_type="viral_research", input_summary=f"Viral search: {req.topic}", error_message=error_msg, uid_override=uid)
        return JSONResponse(status_code=500, content={"error": error_msg})
    
    result_file = ".tmp/viral_trends.json"
    if os.path.exists(result_file):
        with open(result_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        _save_history_entry(req, {}, run_type="viral_research", input_summary=f"Viral search: {req.topic}", full_results=data, uid_override=uid)
        return data
    
    _save_history_entry(req, {}, run_type="viral_research", input_summary=f"Viral search: {req.topic}", error_message="No results found in temp file.", uid_override=uid)
    return {"error": "No results found"}

@app.post("/api/research/competitor")
async def research_competitor(req: ResearchRequest, request: Request):
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", req.user_id or "default"))
    print(f"Competitor research request for: {req.urls}")
    if not req.urls:
        return JSONResponse(status_code=400, content={"error": "No URLs provided"})
    
    _clear_costs()
    urls_str = ",".join(req.urls)
    command = ["python", "execution/viral_research_apify.py", "--urls", urls_str]
    process = subprocess.run(command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8')
    
    if process.returncode != 0:
        error_msg = process.stderr or "Competitor research failed."
        _save_history_entry(req, {}, run_type="competitor_research", input_summary=f"Competitor scrape: {min(len(req.urls), 3)} URLs", error_message=error_msg, uid_override=uid)
        return JSONResponse(status_code=500, content={"error": error_msg})
    
    result_file = ".tmp/viral_trends.json"
    if os.path.exists(result_file):
        with open(result_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        _save_history_entry(req, {}, run_type="competitor_research", input_summary=f"Competitor scrape: {min(len(req.urls), 3)} URLs", full_results=data, uid_override=uid)
        return data
        
    _save_history_entry(req, {}, run_type="competitor_research", input_summary=f"Competitor scrape: {min(len(req.urls), 3)} URLs", error_message="No results found in temp file.", uid_override=uid)
    return {"error": "No results found"}

@app.post("/api/research/youtube")
async def research_youtube(req: ResearchRequest, request: Request):
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", req.user_id or "default"))
    print(f"YouTube repurpose request for: {req.urls} (Deep: {req.deep_search})")
    if not req.urls:
        return JSONResponse(status_code=400, content={"error": "No URLs provided"})
    
    _clear_costs()
    urls_str = ",".join(req.urls)
    
    # Always use Apify on cloud (yt-dlp blocked by YouTube on datacenter IPs)
    _is_cloud = os.path.exists("/app/modal_app.py") or os.environ.get("MODAL_ENVIRONMENT")
    if req.deep_search or _is_cloud:
        command = ["python", "execution/apify_youtube.py", "--urls", urls_str]
    else:
        command = ["python", "execution/local_youtube.py", "--urls", urls_str]
        
    process = subprocess.run(command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8')
    
    if process.returncode != 0:
        error_info = process.stderr or process.stdout or "YouTube research failed."
        _save_history_entry(req, {}, run_type="youtube_research", input_summary=f"YouTube scrape: {urls_str[:50]}...", error_message=error_info, uid_override=uid)
        return JSONResponse(status_code=500, content={"error": error_info})
    
    result_file = ".tmp/youtube_research.json"
    if os.path.exists(result_file):
        with open(result_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        _save_history_entry(req, {}, run_type="youtube_research", input_summary=f"YouTube scrape: {urls_str[:50]}...", full_results=data, uid_override=uid)
        return data
        
    _save_history_entry(req, {}, run_type="youtube_research", input_summary=f"YouTube scrape: {urls_str[:50]}...", error_message="Research completed but no results found.", uid_override=uid)
    return JSONResponse(status_code=500, content={"error": "Research completed but no results found."})

class DraftRequest(BaseModel):
    user_id: Optional[str] = None
    source_text: str
    source_type: str  # 'linkedin' or 'youtube'
    target_purpose: str = "storytelling"
    target_type: str = "text"

@app.post("/api/draft")
async def draft_content(req: DraftRequest):
    print(f"In-Situ drafting request for {req.source_type} as {req.target_type}")
    
    if not req.source_text or len(req.source_text.strip()) < 10:
        return JSONResponse(status_code=400, content={"error": "Insufficient source content for drafting."})

    # Specialized Drafting Prompt
    system_prompt = f"""You are an elite LinkedIn Ghostwriter. 
Your task is to REPURPOSE the provided source content into a high-engagement LinkedIn post.
STYLE: {req.target_purpose.upper()}
FORMAT: {req.target_type.upper()}

FORMAT RULES:
- TEXT: Focus on deep value and long-form narrative.
- IMAGE: Focus on a punchy caption that complements a visual asset.
- CAROUSEL: Write a breakdown that works as slides. Include [Slide 1], [Slide 2] markers.
- VIDEO: Focus on a hook that drives people to watch.

GENERAL RULES:
1. Hook: Start with a punchy first line.
2. Value: Extract the core lesson or insight from the source.
3. Formatting: Use whitespace, bullet points, and 0-3 relevant emojis.
4. Call to Action: End with a question or a clear CTA.
5. NO mentions of 'Here is a post' or 'Certainly'. Just the content.
"""
    user_content = f"SOURCE CONTENT ({req.source_type.upper()}):\n\n{req.source_text}\n\nDraft a viral LinkedIn post based on this."

    from google import genai
    from google.genai import types
    
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
         return JSONResponse(status_code=500, content={"error": "Gemini API key not configured."})

    try:
        client = genai.Client(api_key=api_key)
        model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3-pro-preview")
        response = client.models.generate_content(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
            ),
            contents=user_content
        )
        
        if not response or not response.text:
             return JSONResponse(status_code=500, content={"error": "LLM failed to generate a response."})

        draft = response.text.strip()
        # Clean potential markdown wrappers
        if draft.startswith("```"):
             draft = draft.strip("`").replace("markdown", "").replace("text", "").strip()
             
        return {"draft": draft}
    except Exception as e:
        print(f"Drafting error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- DRAFTS CRUD ENDPOINTS ---

class DraftSaveRequest(BaseModel):
    user_id: Optional[str] = None
    post_data: dict

class DraftUpdateRequest(BaseModel):
    user_id: Optional[str] = None
    data: dict

@app.get("/api/drafts")
async def list_drafts(request: Request, status: str = None):
    """List user's drafts with optional status filter."""
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", "default"))
    from execution.supabase_client import get_user_drafts
    drafts = get_user_drafts(uid=uid, status_filter=status)
    return {"drafts": drafts}

@app.post("/api/drafts")
async def create_draft(req: DraftSaveRequest, request: Request):
    """Save a new draft from generation/repurpose result."""
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", req.user_id or "default"))
    from execution.supabase_client import save_draft

    post = req.post_data
    draft_data = {
        "id": post.get("id", str(uuid.uuid4())),
        "caption": post.get("caption", post.get("full_caption", "")),
        "asset_url": post.get("asset_url", ""),
        "final_image_prompt": post.get("final_image_prompt", ""),
        "type": post.get("type", "text"),
        "purpose": post.get("purpose", ""),
        "topic": post.get("topic", ""),
        "status": "draft",
        "source_data": post,
        "carousel_layout": post.get("carousel_layout"),
        "quality_score": post.get("quality_score", 0),
    }

    saved = save_draft(draft_data, uid=uid)
    print(f"[Drafts] Saved draft '{saved.get('id')}' for user {uid}")
    return {"message": "Draft saved", "draft": saved}

@app.put("/api/drafts/{draft_id}")
async def update_draft_endpoint(draft_id: str, req: DraftUpdateRequest, request: Request):
    """Update an existing draft (caption, status, schedule, etc.)."""
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", req.user_id or "default"))
    from execution.supabase_client import update_draft

    success = update_draft(draft_id, req.data, uid=uid)
    if success:
        print(f"[Drafts] Updated draft '{draft_id}' for user {uid}")
        return {"message": "Draft updated"}
    return JSONResponse(status_code=500, content={"error": "Failed to update draft"})

@app.delete("/api/drafts/{draft_id}")
async def delete_draft_endpoint(draft_id: str, request: Request):
    """Delete a draft by ID."""
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", "default"))
    from execution.supabase_client import delete_draft

    success = delete_draft(draft_id, uid=uid)
    if success:
        print(f"[Drafts] Deleted draft '{draft_id}' for user {uid}")
        return {"message": "Draft deleted"}
    return JSONResponse(status_code=500, content={"error": "Failed to delete draft"})

class PublishRequest(BaseModel):
    user_id: Optional[str] = None
    scheduled_time: Optional[str] = None
    force: bool = False

@app.post("/api/drafts/{draft_id}/publish")
async def publish_draft_endpoint(draft_id: str, req: PublishRequest, request: Request):
    """Publish a draft to LinkedIn via Blotato API."""
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", req.user_id or "default"))
    
    from execution.supabase_client import get_user_drafts, update_draft
    
    # Load draft
    drafts = get_user_drafts(uid=uid)
    draft = next((d for d in drafts if d.get("id") == draft_id), None)
    if not draft:
        return JSONResponse(status_code=404, content={"error": "Draft not found"})
    
    try:
        from execution.blotato_bridge import publish_draft as _publish
        
        result = _publish(
            caption=draft.get("caption", ""),
            asset_url=draft.get("asset_url"),
            scheduled_time=req.scheduled_time,
            force=req.force,
        )
        
        status = result.get("status", "unknown")
        
        if status == "blocked":
            return JSONResponse(status_code=422, content=result)
        
        if status in ("published", "scheduled"):
            update_data = {
                "status": status,
                "blotato_post_id": result.get("submission_id", ""),
                "quality_score": result.get("quality_score", 0),
            }
            if status == "published":
                from datetime import datetime
                update_data["published_at"] = datetime.utcnow().isoformat()
            if req.scheduled_time:
                update_data["scheduled_at"] = req.scheduled_time
            
            update_draft(draft_id, update_data, uid=uid)
            print(f"[Blotato] Draft '{draft_id}' {status} for user {uid}")
        
        return result
        
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        print(f"[Blotato] Publish error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/blotato/accounts")
async def blotato_accounts(request: Request):
    """Test Blotato API connection and list connected accounts."""
    try:
        from execution.blotato_bridge import test_connection
        return test_connection()
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e), "connected": False})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "connected": False})

@app.get("/api/blotato/schedule")
async def blotato_schedule(request: Request):
    """Get upcoming schedule + next optimal slot."""
    try:
        from execution.blotato_bridge import get_schedule_info
        return get_schedule_info()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

class QualityCheckRequest(BaseModel):
    caption: str
    has_image: bool = False

@app.post("/api/blotato/quality-check")
async def blotato_quality_check(req: QualityCheckRequest):
    """Score a caption against the quality gate without publishing."""
    try:
        from execution.blotato_bridge import get_quality_score
        return get_quality_score(req.caption, has_image=req.has_image)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- SETTINGS ENDPOINTS ---

class SettingsUpdateRequest(BaseModel):
    trackedProfileUrl: Optional[str] = None
    blotatoApiKey: Optional[str] = None

@app.get("/api/settings")
async def get_settings(request: Request):
    """Return current app settings for the authenticated user."""
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", "default"))
    try:
        from execution.supabase_client import get_all_settings
        
        data = get_all_settings(uid=uid)
        # Fallback: if Supabase has no URL yet, seed from .env so UI isn't blank
        if not data.get("trackedProfileUrl"):
            data["trackedProfileUrl"] = os.getenv("LINKEDIN_PROFILE_URL", "")
        return data
    except Exception as e:
        print(f"[settings] Read failed, using .env fallback: {e}")
        return {"trackedProfileUrl": os.getenv("LINKEDIN_PROFILE_URL", "")}

@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest, request: Request, background_tasks: BackgroundTasks):
    """Persist settings for the authenticated user."""
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", "default"))
    try:
        from execution.supabase_client import update_settings as sb_update, _write_local_settings
        payload = {k: v for k, v in req.dict().items() if v is not None}
        
        # Save locally immediately so UI doesn't hang — per-user cache
        _write_local_settings(payload, uid=uid)
        
        # Supabase upsert in the background
        background_tasks.add_task(sb_update, payload, uid)
        
        return {"status": "saved", "data": payload}
    except Exception as e:
        print(f"[settings] POST /api/settings error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- LEAD INTELLIGENCE ENDPOINTS ---

class LeadScanRequest(BaseModel):
    post_urls: Optional[List[str]] = None  # Optional: if None, reads from surveillance data

@app.post("/api/run-lead-scan")
async def run_lead_scan(req: LeadScanRequest, request: Request, background_tasks: BackgroundTasks):
    """Triggers lead scan in the background. Use GET /api/leads/data to poll for results."""
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", "default"))
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "execution"))
    
    # Pre-write a scanning status so polling knows we're working on this specific URL
    os.makedirs(".tmp", exist_ok=True)
    with open(f".tmp/leads_data_{uid}.json", "w", encoding="utf-8") as f:
        json.dump({"status": "scanning", "summary": {"scanned_urls": req.post_urls}}, f)

    def _do_scan(urls, u):
        try:
            from execution.lead_scraper import run_lead_scan as _scan
            _scan(post_urls=urls, uid=u)
        except Exception as e:
            print(f"[lead-scan] Error: {e}")
            # Write error state
            with open(f".tmp/leads_data_{u}.json", "w", encoding="utf-8") as err_f:
                json.dump({"status": "error", "message": str(e), "summary": {"scanned_urls": urls}}, err_f)
    
    background_tasks.add_task(_do_scan, req.post_urls, uid)
    return {"status": "scanning", "message": "Lead scan started in background. Poll /api/leads/data for results."}

@app.get("/api/leads/data")
async def get_leads_data(request: Request):
    """Returns the latest lead scan results, per-user."""
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", "default"))
    leads_file = f".tmp/leads_data_{uid}.json"
    if os.path.exists(leads_file):
        try:
            with open(leads_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Error loading leads: {e}"})
    return {"summary": {"total_leads": 0, "scanned_posts": 0}, "leads": []}

# --- SURVEILLANCE ENDPOINTS ---

@app.get("/api/surveillance/data")
async def get_surveillance_data(request: Request):
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", "default"))
    data_file = f".tmp/surveillance_data_{uid}.json"
    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Error loading data: {e}"})
    return {"summary": {"total_posts": 0}, "posts": []}

class SurveillanceRefreshRequest(BaseModel):
    days: int = 30

@app.post("/api/surveillance/refresh")
async def refresh_surveillance_data(req: SurveillanceRefreshRequest, request: Request, background_tasks: BackgroundTasks):
    uid = request.headers.get("X-User-ID", request.headers.get("X-Firebase-UID", "default"))
    days = max(1, min(req.days, 365))  # clamp to 1–365
    def run_scrape():
        print(f"Manual refresh of surveillance data triggered (range: {days} days, uid: {uid}).")
        subprocess.run(["python", "execution/surveillance_scraper.py", "--days", str(days), "--uid", uid], env=RUN_ENV)
        
    background_tasks.add_task(run_scrape)
    return {"message": f"Surveillance refresh started ({days} days)."}

# Mount frontend to root (catch-all for static files)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)
