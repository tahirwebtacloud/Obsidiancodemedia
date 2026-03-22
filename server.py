import uuid
import hashlib
import base64
from contextlib import asynccontextmanager
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.exceptions import RequestValidationError
import os
import subprocess
import json
import time
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Any

# Load environment variables
load_dotenv()
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan — runs startup logic before yield, shutdown after."""
    await _startup_cleanup()
    yield


app = FastAPI(lifespan=lifespan)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Dynamically add the correct localhost origin based on runtime port
_PORT = int(os.environ.get("PORT", 9999))
_LOCAL_ORIGIN_HTTP = f"http://localhost:{_PORT}"
_LOCAL_ORIGIN_IP = f"http://127.0.0.1:{_PORT}"

_CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
] or [
    "https://tahir-70872--linkedin-post-generator-web.modal.run",
    _LOCAL_ORIGIN_HTTP,
    _LOCAL_ORIGIN_IP,
]

# Ensure no duplicates if user provides localhost in env var
_CORS_ORIGINS = sorted(list(set(_CORS_ORIGINS)))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-User-ID"],
)

# ─── Per-request RLS middleware ────────────────────────────────────────────────
# Passes the user's Supabase JWT to supabase_client so every DB call in this
# request uses an RLS-aware client instead of the service-role key.
from starlette.middleware.base import BaseHTTPMiddleware

class _SupabaseRLSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from execution.supabase_client import set_request_token, clear_request_token
        auth_header = request.headers.get("authorization", "")
        token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else ""
        if token:
            set_request_token(token)
        try:
            response = await call_next(request)
            return response
        finally:
            clear_request_token()

app.add_middleware(_SupabaseRLSMiddleware)

# Global lock to serialize pipeline execution and avoid .tmp clobbering
generation_lock = asyncio.Lock()

# ─── Content-Security-Policy middleware ───────────────────────────────────────
# Mitigates XSS and supply-chain attacks from compromised CDNs.
_SUPABASE_ORIGIN = "https://bsaggewiyjaikkkbvgpr.supabase.co"
_CSP_POLICY = "; ".join([
    # Scripts: own origin + pinned CDN hosts only
    "default-src 'self'",
    "script-src 'self' https://unpkg.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
    # Styles: own origin + Google Fonts + Cloudflare CDN; 'unsafe-inline' needed for inline styles
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com",
    # Fonts: Google Fonts + Cloudflare (Font Awesome)
    "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:",
    # Images: own origin + LinkedIn CDN (post images) + Supabase Storage + data URIs + blobs
    "img-src 'self' data: blob: https://*.licdn.com https://*.supabase.co",
    # API connections: own origin + Supabase
    f"connect-src 'self' {_SUPABASE_ORIGIN} https://*.supabase.co",
    # Frames: none needed
    "frame-src 'none'",
    # Objects/embeds: blocked
    "object-src 'none'",
    # Base URI: prevent base tag hijacking
    "base-uri 'self'",
    # Form actions: own origin only
    "form-action 'self'",
])


class _CSPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Only add CSP to HTML responses (not API JSON or static assets)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            response.headers["Content-Security-Policy"] = _CSP_POLICY
        return response

app.add_middleware(_CSPMiddleware)

# Ensure execution/ is on sys.path so that direct imports from execution modules
# can find sibling modules like cost_tracker.py
import sys as _sys
_exec_dir = os.path.join(os.path.dirname(__file__), "execution")
if _exec_dir not in _sys.path:
    _sys.path.insert(0, _exec_dir)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    # Log full details server-side for debugging
    print(f"\n>>> VALIDATION ERROR on {request.url}")
    print(f">>> Errors: {exc.errors()}")
    print(f">>> Body (first 500 chars): {body[:500]}")
    # Return generic message to client — never expose internal field names or types
    return JSONResponse(status_code=422, content={"error": "Invalid request data. Please check your input and try again."})

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("frontend/favicon.png")


@app.get("/api/health")
async def health_check():
    """Lightweight liveness/readiness probe for load balancers and Modal."""
    checks = {"server": "ok"}
    overall = True

    # Supabase connectivity
    try:
        from execution.supabase_client import _get_client
        client = _get_client()
        client.table("user_settings").select("user_id", count="exact").limit(1).execute()
        checks["supabase"] = "ok"
    except Exception as e:
        checks["supabase"] = f"error: {str(e)[:80]}"
        overall = False

    # .tmp directory writable
    try:
        os.makedirs(".tmp", exist_ok=True)
        test_file = ".tmp/_health_check"
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        checks["tmp_writable"] = "ok"
    except Exception:
        checks["tmp_writable"] = "error"
        overall = False

    status_code = 200 if overall else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "healthy" if overall else "degraded", "checks": checks},
    )


@app.get("/api/health/models")
async def health_models():
    """Return effective runtime model configuration (safe diagnostics, no secret leakage)."""
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY", "")
    api_key_suffix = api_key[-6:] if api_key else ""

    return {
        "success": True,
        "models": {
            "gemini_text_model": os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview"),
            "gemini_crm_model": os.getenv("GEMINI_CRM_MODEL", "gemini-3.1-pro-preview"),
            "gemini_image_model": os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview"),
            "gemini_embedding_model": os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
        },
        "api_key": {
            "present": bool(api_key),
            "masked": "***" if api_key else "",
        },
        "notes": {
            "quota_scope": "Gemini quota is enforced by the Google project tied to GOOGLE_GEMINI_API_KEY.",
            "restart_required": "Restart server after .env changes to apply new model values.",
        },
    }

# Force Python subprocesses to use UTF-8 output
RUN_ENV = os.environ.copy()
RUN_ENV["PYTHONIOENCODING"] = "utf-8"

# ─── JWT Auth Verification ────────────────────────────────────────────────────
_verified_uid_cache: Dict[str, tuple] = {}  # {token_hash: (uid, expiry_ts)}
_AUTH_CACHE_TTL = 300  # Cache verified UIDs for 5 minutes

def get_verified_uid(request: Request) -> str:
    """Extract and verify user ID from Supabase JWT token.

    Priority:
      1. Authorization: Bearer <token> — verified via Supabase auth API
      2. Raises HTTP 401 if no valid authentication found
    """
    # 1. Try Bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            # Check cache first
            token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
            cached = _verified_uid_cache.get(token_hash)
            if cached and cached[1] > time.time():
                return cached[0]

            # Verify with Supabase auth API
            try:
                from execution.supabase_client import _get_client
                client = _get_client()
                user_response = client.auth.get_user(token)
                if user_response and user_response.user:
                    uid = user_response.user.id
                    _verified_uid_cache[token_hash] = (uid, time.time() + _AUTH_CACHE_TTL)
                    # Prune expired entries if cache grows too large
                    if len(_verified_uid_cache) > 500:
                        cutoff = time.time()
                        expired = [k for k, v in _verified_uid_cache.items() if v[1] < cutoff]
                        for k in expired:
                            del _verified_uid_cache[k]
                    return uid
            except Exception as e:
                print(f"[Auth] Token verification failed: {e}")
                raise HTTPException(status_code=401, detail="Invalid or expired authentication token")

    # 2. No valid auth — reject
    raise HTTPException(status_code=401, detail="Authentication required. Please sign in.")


# Mount frontend files
# Mount frontend files logic moved to end of file to allow API routes to take precedence

# Authenticated asset serving — only image files, no raw data exposure
_SAFE_ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf"}
_ASSET_MIME_MAP = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
}

@app.get("/assets/{file_path:path}")
async def serve_asset(file_path: str, request: Request):
    """Serve generated assets from .tmp/ with file-type restrictions.

    Auth is intentionally NOT required here because <img src> tags cannot
    send Authorization headers.  Security is enforced via path-traversal
    protection and a strict extension whitelist (images/PDFs only).
    """
    # Determine absolute path to .tmp/ relative to project root
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".tmp"))
    
    # Construct requested full path and normalize it
    full_path = os.path.abspath(os.path.join(base_dir, file_path))
    
    # Validate that the normalized absolute path is strictly within base_dir
    # This completely eliminates path traversal vulnerabilities (e.g. `../../.env`)
    if not full_path.startswith(base_dir + os.sep):
        return JSONResponse(status_code=403, content={"error": "Invalid path traverse detected"})

    # Only serve safe file types (images/PDFs)
    ext = os.path.splitext(full_path)[1].lower()
    if ext not in _SAFE_ASSET_EXTENSIONS:
        return JSONResponse(status_code=403, content={"error": "File type not allowed"})

    if not os.path.isfile(full_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})

    return FileResponse(full_path, media_type=_ASSET_MIME_MAP.get(ext, "application/octet-stream"))

async def _startup_cleanup():
    """Purge local profiles for users no longer in Supabase Auth.
    Called from the FastAPI lifespan context manager."""
    try:
        from execution import supabase_client as _sc
        _profile_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".local_profiles.json")
        if os.path.exists(_profile_file):
            with open(_profile_file, "r", encoding="utf-8") as _f:
                _local = json.load(_f)
            _client = _sc._get_client()
            _auth_users = _client.auth.admin.list_users()
            _valid_uids = {u.id for u in _auth_users} | {"default"}
            _stale = [uid for uid in _local if uid not in _valid_uids]
            if _stale:
                for _uid in _stale:
                    del _local[_uid]
                    try:
                        _client.table("voice_chunks").delete().eq("user_id", _uid).execute()
                        _client.table("crm_contacts").delete().eq("user_id", _uid).execute()
                    except Exception:
                        pass
                with open(_profile_file, "w", encoding="utf-8") as _f:
                    json.dump(_local, _f, indent=2, ensure_ascii=False)
                print(f"[Startup] Purged stale profiles for {len(_stale)} deleted user(s): {_stale}")
    except Exception as _e:
        print(f"[Startup] Profile cleanup skipped: {_e}")

class GenerateRequest(BaseModel):
    action: str = "develop_post"
    topic: str = ""
    auto_topic: bool = False
    include_lead_magnet: bool = False
    source: str = "topic" # topic | news | blog | surveillance | youtube
    type: str = "text"   # text | article
    purpose: str = "educational" 
    visual_style: str = "minimal"
    aspect_ratio: str = "16:9" 
    visual_aspect: str = "none" # image | video | carousel | none
    style_type: Optional[str] = None 
    color_palette: str = "brand_kit"
    url: Optional[str] = None
    reference_image: Optional[str] = None
    deep_research: bool = False
    time_range: Optional[str] = None
    brand_kit_palette: Optional[Dict[str, Any]] = None
    source_content: Optional[str] = None
    source_post_type: Optional[str] = None
    source_image_urls: Optional[List[str]] = None
    source_carousel_slides: Optional[List[str]] = None
    source_video_url: Optional[str] = None
    source_video_urls: Optional[List[str]] = None
    reference_image: Optional[str] = None
    raw_notes: Optional[str] = None


def _resolve_brand_kit_palette(uid: str, frontend_palette: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a fully-formed Brand Kit palette object for the active user."""
    if frontend_palette and isinstance(frontend_palette, dict):
        try:
            merged = {
                "id": "brand_kit",
                "name": frontend_palette.get("name") or "Brand Kit (My Brand)",
                "description": frontend_palette.get("description") or "User-isolated brand palette",
                "primary": frontend_palette.get("primary") or "#F9C74F",
                "secondary": frontend_palette.get("secondary") or "#0E0E0E",
                "accent": frontend_palette.get("accent") or "#FCF0D5",
                "neutral": frontend_palette.get("neutral") or "#111111",
                "dark": frontend_palette.get("dark") or frontend_palette.get("secondary") or "#0E0E0E",
                "light": frontend_palette.get("light") or "#F0F0F0",
                "color_theory": frontend_palette.get("color_theory") or "Derived from active user brand settings.",
                "emotional_context": frontend_palette.get("emotional_context") or "Brand-authentic and user-specific",
                "best_for": frontend_palette.get("best_for") or "Any generation that should follow the active user brand kit",
                "usage_guidelines": frontend_palette.get("usage_guidelines") or {
                    "primary_use": "Primary emphasis and highlights",
                    "secondary_use": "Supporting structure and contrast",
                    "accent_use": "Focal accents and CTA highlights",
                    "neutral_use": "Background surfaces and breathing room",
                },
            }
            return merged
        except Exception:
            pass

    try:
        from execution.supabase_client import get_user_brand
        brand = get_user_brand(uid) or {}
    except Exception:
        brand = {}

    ui_theme = brand.get("ui_theme") if isinstance(brand.get("ui_theme"), dict) else {}
    return {
        "id": "brand_kit",
        "name": "Brand Kit (My Brand)",
        "description": f"User-isolated palette for {brand.get('brand_name') or 'current brand'}",
        "primary": (brand.get("primary_color") or "#F9C74F").upper(),
        "secondary": (brand.get("secondary_color") or "#0E0E0E").upper(),
        "accent": (brand.get("accent_color") or "#FCF0D5").upper(),
        "neutral": ui_theme.get("bg_paper") or "#111111",
        "dark": ui_theme.get("bg_sidebar") or (brand.get("secondary_color") or "#0E0E0E"),
        "light": ui_theme.get("text_primary") or "#F0F0F0",
        "color_theory": "Derived from the active user brand settings for consistent visual identity.",
        "emotional_context": brand.get("tone_of_voice") or "Brand-authentic and user-specific",
        "best_for": "Any generation that should strictly follow the current user brand kit",
        "usage_guidelines": {
            "primary_use": "Primary emphasis, highlights, and key visual anchors",
            "secondary_use": "Supporting color blocks, secondary text, and structural accents",
            "accent_use": "Callouts, CTA highlights, and focal points",
            "neutral_use": "Background surfaces, spacing, and subtle containers",
        },
    }


def _attach_brand_kit_palette_file(command: list, req: GenerateRequest, uid: str) -> None:
    if (req.color_palette or "").lower() != "brand_kit":
        return
    os.makedirs(".tmp", exist_ok=True)
    palette_payload = _resolve_brand_kit_palette(uid, req.brand_kit_palette)
    palette_file = f".tmp/brand_palette_{uuid.uuid4().hex[:8]}.json"
    with open(palette_file, "w", encoding="utf-8") as f:
        json.dump(palette_payload, f, ensure_ascii=False)
    command.extend(["--brand_palette_file", palette_file])

@app.post("/api/generate")
async def generate_post(req: GenerateRequest, request: Request):
    uid = get_verified_uid(request)
    if not _check_rate_limit(uid):
        return JSONResponse(status_code=429, content={"error": "Rate limit exceeded. Please wait a moment before generating again."})
    print(f"Received generation request: {req.action} | Aspect Ratio: {req.aspect_ratio} | Visual Aspect: {req.visual_aspect} | Style: {req.visual_style} | Style Type: {req.style_type}")
    
    command = _build_orchestrator_command(req, uid=uid)
    print(f"Executing: {' '.join(command)}")

    try:
        async with generation_lock:
            process = await asyncio.to_thread(
                subprocess.run, command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8', errors='replace'
            )

            if process.returncode != 0:
                return JSONResponse(status_code=500, content={"error": _safe_error(process.stderr or process.stdout, "Content generation failed. Please try again.")})

            # Determine result file based on action
            result_file = ".tmp/final_plan.json"

            if os.path.exists(result_file):
                with open(result_file, "r", encoding="utf-8") as f:
                    result_data = json.load(f)

                # Upload generated image to Supabase Storage (survives container restarts)
                result_data = _persist_asset_to_storage(result_data, uid)

                _save_history_entry(req, result_data, uid_override=uid)

                return result_data
            else:
                return JSONResponse(status_code=500, content={"error": "Orchestrator completed but no output file found.", "details": process.stdout})
            
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})

# ─── Error Sanitization ──────────────────────────────────────────────────────
def _safe_error(raw: str, fallback: str = "An internal error occurred. Please try again.") -> str:
    """Return a user-friendly error message, stripping tracebacks and file paths."""
    if not raw:
        return fallback
    # Log full error server-side
    print(f"[Error detail] {raw[:500]}")
    # If it looks like a traceback, return the fallback
    if "Traceback" in raw or "File \"" in raw or ".py\"," in raw:
        return fallback
    # Truncate very long messages
    if len(raw) > 200:
        return raw[:200].rsplit(" ", 1)[0] + "..."
    return raw


# ─── Rate Limiting ────────────────────────────────────────────────────────────
_RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "10"))  # requests per minute per user
_rate_buckets: Dict[str, list] = {}  # {uid: [timestamp, ...]}


def _check_rate_limit(uid: str, rpm: int = None) -> bool:
    """Return True if the user is within rate limits, False if exceeded."""
    limit = rpm or _RATE_LIMIT_RPM
    now = time.time()
    cutoff = now - 60

    bucket = _rate_buckets.get(uid, [])
    # Prune old entries
    bucket = [ts for ts in bucket if ts > cutoff]
    if len(bucket) >= limit:
        _rate_buckets[uid] = bucket
        return False
    bucket.append(now)
    _rate_buckets[uid] = bucket

    # Prune stale users periodically
    if len(_rate_buckets) > 200:
        stale = [k for k, v in _rate_buckets.items() if not v or v[-1] < cutoff]
        for k in stale:
            del _rate_buckets[k]
    return True


def _sanitize_arg(value: str) -> str:
    """Strip leading dashes from user input to prevent argparse flag injection."""
    if value and value.startswith("-"):
        return value.lstrip("-")
    return value


# ─── URL Validation (SSRF Prevention) ─────────────────────────────────────────
import urllib.parse as _urlparse

_ALLOWED_URL_DOMAINS = {
    "linkedin.com", "www.linkedin.com",
    "youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com",
    "medium.com", "www.medium.com",
    "substack.com",
    "twitter.com", "x.com", "www.x.com",
}

def _validate_external_url(url: str) -> str:
    """Validate that a user-supplied URL points to an allowed external domain.

    Blocks internal/private IPs (SSRF) and non-HTTPS schemes.
    Returns the validated URL or raises HTTPException.
    """
    if not url or not isinstance(url, str):
        return url

    url = url.strip()
    if not url:
        return url

    try:
        parsed = _urlparse.urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid URL format: {url[:100]}")

    # Only allow HTTPS (and HTTP for localhost dev)
    if parsed.scheme not in ("https", "http"):
        raise HTTPException(status_code=400, detail=f"URL must use HTTPS: {url[:100]}")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise HTTPException(status_code=400, detail="URL has no hostname")

    # Block private/internal IPs (SSRF prevention)
    _blocked_prefixes = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                         "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                         "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                         "172.30.", "172.31.", "192.168.", "127.", "0.", "169.254.")
    if any(hostname.startswith(p) for p in _blocked_prefixes):
        raise HTTPException(status_code=400, detail="Internal/private URLs are not allowed")
    if hostname in ("localhost", "metadata.google.internal", "[::1]"):
        raise HTTPException(status_code=400, detail="Internal/private URLs are not allowed")

    # Check domain allowlist — match base domain (strip subdomains like "blog.medium.com")
    domain_parts = hostname.split(".")
    # Check exact match first, then base domain (last two parts)
    base_domain = ".".join(domain_parts[-2:]) if len(domain_parts) >= 2 else hostname
    if hostname not in _ALLOWED_URL_DOMAINS and base_domain not in _ALLOWED_URL_DOMAINS:
        raise HTTPException(
            status_code=400,
            detail=f"URL domain '{hostname}' is not in the allowed list. Allowed: LinkedIn, YouTube, Medium, Substack, X/Twitter."
        )

    return url


def _generate_auto_topic(uid: str) -> str:
    """Uses LLM to brainstorm a topic based on user profile and brand assets."""
    print(f"[{uid}] Generating auto-topic...")
    try:
        from execution.supabase_client import get_user_profile, get_user_brand
        profile = get_user_profile(uid=uid)
        brand = get_user_brand(uid=uid)

        profile_text = ""
        brand_text = ""

        if profile:
            profile_text = f"- Role/Headline: {profile.get('linkedin_headline', 'Professional')}\n- Description: {profile.get('profile_summary', '')}\n- Expertise: {', '.join(profile.get('skills', []))}"
        if brand:
            brand_text = f"- Target Audience: {brand.get('target_audience', '')}\n- Core Offerings: {', '.join(brand.get('core_offerings', []))}\n- Brand Values: {', '.join(brand.get('brand_values', []))}"

        prompt = f"""You are an expert LinkedIn strategist.
The user wants to write a new LinkedIn post but doesn't have a specific topic.
Based on their profile and brand information below, generate exactly ONE highly engaging, specific, and relevant topic for a LinkedIn post.

USER PROFILE:
{profile_text or "No specific profile provided."}

BRAND ASSETS:
{brand_text or "No specific brand provided."}

RULES:
1. Focus on a mix of their personal expertise and brand offerings.
2. The topic should be actionable and interesting to their target audience.
3. You MUST use the Google Search tool to find current industry trends, recent news, or fresh angles related to their expertise. Incorporate this real-time context into the topic you generate.
4. Do NOT output a full post or explanation. Output ONLY the topic (e.g. "How new AI features are changing B2B sales cycles").
5. Keep it under 10 words.
6. Do not use quotes around the topic.
"""
        api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
        model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")
        client = genai.Client(api_key=api_key)

        config = types.GenerateContentConfig(
            temperature=0.7,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO"),
                include_server_side_tool_invocations=True
            )
        )

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )
        topic = response.text.strip().replace('"', '')
        if not topic:
            return "General Industry Insights"
        return topic
    except Exception as e:
        print(f"[{uid}] Error generating auto topic: {e}")
        return "General Industry Insights"


def _build_orchestrator_command(req, uid: str = "default"):
    """Build the orchestrator command list from a GenerateRequest. Shared by /api/generate and /api/generate-stream."""
    command = ["python", "-u", "orchestrator.py", "--action", req.action, "--preview", "--user_id", uid]
    
    if req.source: command.extend(["--source", _sanitize_arg(req.source)])
    if req.url:
        validated_url = _validate_external_url(req.url)
        command.extend(["--url", validated_url])
    if req.topic: command.extend(["--topic", _sanitize_arg(req.topic)])
    if req.type: command.extend(["--type", _sanitize_arg(req.type)])
    if req.purpose: command.extend(["--purpose", _sanitize_arg(req.purpose)])
    if req.visual_style: command.extend(["--style", _sanitize_arg(req.visual_style)])
    if req.visual_aspect: command.extend(["--visual_aspect", _sanitize_arg(req.visual_aspect)])
    if req.style_type: command.extend(["--style_type", _sanitize_arg(req.style_type)])
    if req.aspect_ratio: command.extend(["--aspect_ratio", _sanitize_arg(req.aspect_ratio)])
    if req.color_palette: command.extend(["--color_palette", _sanitize_arg(req.color_palette)])
    if getattr(req, "deep_research", False): command.append("--deep_research")
    if req.time_range and req.time_range in ("day", "week", "month", "year"):
        command.extend(["--time_range", req.time_range])
    if req.include_lead_magnet: command.append("--include_lead_magnet")
    _attach_brand_kit_palette_file(command, req, uid)

    if req.source_content:
        os.makedirs(".tmp", exist_ok=True)
        temp_file = f".tmp/source_payload_{uuid.uuid4().hex[:8]}.txt"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(req.source_content)
        command.extend(["--source_content", temp_file])

    if req.raw_notes and req.raw_notes.strip():
        os.makedirs(".tmp", exist_ok=True)
        notes_file = f".tmp/raw_notes_{uuid.uuid4().hex[:8]}.txt"
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write(req.raw_notes)
        command.extend(["--raw_notes", notes_file])

    if req.reference_image and req.reference_image.startswith('data:'):
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

def _persist_asset_to_storage(result_data: dict, uid: str) -> dict:
    """Upload local /assets/ images to Supabase Storage and rewrite asset_url.

    Returns the (possibly modified) result_data dict.  Falls back gracefully
    if upload fails — the local URL will still work while the container is alive.
    """
    asset_url = result_data.get("asset_url", "")
    if not asset_url or not asset_url.startswith("/assets/"):
        return result_data

    # Convert URL to local path: /assets/foo.png -> .tmp/foo.png
    local_path = asset_url.replace("/assets/", ".tmp/", 1)
    if "?" in local_path:
        local_path = local_path.split("?")[0]

    if not os.path.isfile(local_path):
        return result_data

    try:
        from execution.supabase_client import upload_asset
        public_url = upload_asset(local_path, uid=uid)
        if public_url:
            result_data["asset_url"] = public_url
            result_data["_local_asset_url"] = asset_url  # Keep local fallback
    except Exception as e:
        print(f"[Storage] Persist failed, keeping local URL: {e}")

    return result_data


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
        "params": req.model_dump() if hasattr(req, "model_dump") else {},
        
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
    uid = get_verified_uid(request)
    if not _check_rate_limit(uid):
        return JSONResponse(status_code=429, content={"error": "Rate limit exceeded. Please wait a moment before generating again."})
    print(f"[SSE] Received streaming generation request: {req.action}")

    if req.auto_topic:
        auto_topic = _generate_auto_topic(uid)
        req.topic = auto_topic
        print(f"[SSE] Auto-generated topic: {req.topic}")

    command = _build_orchestrator_command(req, uid=uid)
    print(f"[SSE] Executing: {' '.join(command)}")

    async def event_generator():
        if req.auto_topic:
            yield f"event: auto_topic\ndata: {json.dumps({'topic': req.topic})}\n\n"

        async with generation_lock:
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

                    # Upload generated image to Supabase Storage (survives container restarts)
                    result_data = _persist_asset_to_storage(result_data, uid)

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
async def save_post(req: SaveRequest, request: Request):
    uid = get_verified_uid(request)
    print(f"Received save request from {uid}.")
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
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})

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
    uid = get_verified_uid(request)
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
            from execution.generate_image_prompt import generate_image_asset
            
            print(f"DEBUG TWEAK START: Prompt='{req.prompt}' Aspect='{req.aspect_ratio}' Palette='{req.color_palette}'")
            # Call generation function directly
            async with generation_lock:
                new_asset_url, error = await asyncio.to_thread(generate_image_asset, req.prompt, req.aspect_ratio)
            new_prompt = req.prompt
            print(f"DEBUG TWEAK RESULT: URL='{new_asset_url}' Error='{error}'")
            
            if not new_asset_url: return JSONResponse(status_code=500, content={"error": error})

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
            async with generation_lock:
                result = await asyncio.to_thread(
                    subprocess.run, command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8'
                )

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
                else:
                    return JSONResponse(status_code=500, content={"error": "Result file not found"})

        # Upload regenerated image to Supabase Storage
        if new_asset_url and new_asset_url.startswith("/assets/"):
            regen_data = {"asset_url": new_asset_url}
            regen_data = _persist_asset_to_storage(regen_data, uid)
            new_asset_url = regen_data.get("asset_url", new_asset_url)

        # 2. Save Post-Regen State (New Image) to History
        if new_asset_url and req.history_entry:
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
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})

class RegenerateCaptionRequest(BaseModel):
    user_id: Optional[str] = None
    topic: str
    purpose: str
    type: str
    style: str = "minimal"
    instructions: str = None

@app.post("/api/regenerate-caption")
async def regenerate_caption(req: RegenerateCaptionRequest, request: Request):
    uid = get_verified_uid(request)
    print(f"Received regenerate caption request from {uid}.")
    try:
        command = ["python", "execution/regenerate_caption.py", "--topic", _sanitize_arg(req.topic), "--purpose", _sanitize_arg(req.purpose), "--type", _sanitize_arg(req.type), "--style", _sanitize_arg(req.style), "--user-id", _sanitize_arg(uid)]
        
        if req.instructions:
            command.extend(["--instructions", _sanitize_arg(req.instructions)])
            
        print(f"Executing: {' '.join(command)}")

        async with generation_lock:
            result = await asyncio.to_thread(
                subprocess.run, command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8'
            )

            if result.returncode != 0:
                return JSONResponse(status_code=500, content={"error": _safe_error(result.stderr)})

            # Parse output - read from final_plan.json instead of stdout to avoid brittle parsing
            try:
                plan_path = ".tmp/final_plan.json"
                if os.path.exists(plan_path):
                    with open(plan_path, "r", encoding="utf-8") as f:
                        plan = json.load(f)
                    return {"caption": plan.get("caption", "")}
                else:
                    return JSONResponse(status_code=500, content={"error": "Result file not found."})
            except Exception as parse_err:
                print(f"[regenerate-caption] JSON parse error: {parse_err}")
                return JSONResponse(status_code=500, content={"error": "Caption regeneration failed. Please try again."})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})

@app.get("/api/history")
async def get_history(request: Request):
    from execution.supabase_client import get_user_history
    uid = get_verified_uid(request)
    return get_user_history(uid=uid)

# --- RESEARCH ENDPOINTS ---

def _clear_costs():
    cost_file = ".tmp/run_costs_default.json"
    if os.path.exists(cost_file):
        try:
            os.remove(cost_file)
        except OSError as e:
            print(f"[costs] Failed to clear {cost_file}: {e}")

class ResearchRequest(BaseModel):
    user_id: Optional[str] = None
    topic: str = None
    urls: list = None
    deep_search: bool = False

@app.post("/api/research/viral")
async def research_viral(req: ResearchRequest, request: Request):
    uid = get_verified_uid(request)
    if not _check_rate_limit(uid, rpm=5):
        return JSONResponse(status_code=429, content={"error": "Research rate limit exceeded. Please wait before researching again."})
    print(f"Viral research request for: {req.topic}")
    _clear_costs()
    command = ["python", "execution/viral_research_apify.py", "--topic", _sanitize_arg(req.topic)]
    process = await asyncio.to_thread(
        subprocess.run, command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8'
    )
    
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
    uid = get_verified_uid(request)
    if not _check_rate_limit(uid, rpm=5):
        return JSONResponse(status_code=429, content={"error": "Research rate limit exceeded. Please wait before researching again."})
    print(f"Competitor research request for: {req.urls}")
    if not req.urls:
        return JSONResponse(status_code=400, content={"error": "No URLs provided"})

    # Validate all URLs before passing to scraper
    for u in req.urls:
        _validate_external_url(u)

    _clear_costs()
    urls_str = ",".join(req.urls)
    command = ["python", "execution/viral_research_apify.py", "--urls", _sanitize_arg(urls_str)]
    process = await asyncio.to_thread(
        subprocess.run, command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8'
    )
    
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
    uid = get_verified_uid(request)
    if not _check_rate_limit(uid, rpm=5):
        return JSONResponse(status_code=429, content={"error": "Research rate limit exceeded. Please wait before researching again."})
    print(f"YouTube repurpose request for: {req.urls} (Deep: {req.deep_search})")
    if not req.urls:
        return JSONResponse(status_code=400, content={"error": "No URLs provided"})

    # Validate all URLs before passing to scraper
    for u in req.urls:
        _validate_external_url(u)

    _clear_costs()
    urls_str = ",".join(req.urls)
    
    # Always use Apify on cloud (yt-dlp blocked by YouTube on datacenter IPs)
    _is_cloud = os.path.exists("/app/modal_app.py") or os.environ.get("MODAL_ENVIRONMENT")
    if req.deep_search or _is_cloud:
        command = ["python", "execution/apify_youtube.py", "--urls", _sanitize_arg(urls_str)]
    else:
        command = ["python", "execution/local_youtube.py", "--urls", _sanitize_arg(urls_str)]
        
    process = await asyncio.to_thread(
        subprocess.run, command, capture_output=True, text=True, env=RUN_ENV, encoding='utf-8'
    )
    
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
async def draft_content(req: DraftRequest, request: Request):
    uid = get_verified_uid(request)
    print(f"In-Situ drafting request for {req.source_type} as {req.target_type} from {uid}")
    
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
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})

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
    uid = get_verified_uid(request)
    from execution.supabase_client import get_user_drafts
    drafts = get_user_drafts(uid=uid, status_filter=status)
    return {"drafts": drafts}

@app.post("/api/drafts")
async def create_draft(req: DraftSaveRequest, request: Request):
    """Save a new draft from generation/repurpose result."""
    uid = get_verified_uid(request)
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
    uid = get_verified_uid(request)
    from execution.supabase_client import update_draft

    success = update_draft(draft_id, req.data, uid=uid)
    if success:
        print(f"[Drafts] Updated draft '{draft_id}' for user {uid}")
        return {"message": "Draft updated"}
    return JSONResponse(status_code=500, content={"error": "Failed to update draft"})

@app.delete("/api/drafts/{draft_id}")
async def delete_draft_endpoint(draft_id: str, request: Request):
    """Delete a draft by ID."""
    uid = get_verified_uid(request)
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
    uid = get_verified_uid(request)
    
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
        return JSONResponse(status_code=400, content={"error": _safe_error(str(e))})
    except Exception as e:
        print(f"[Blotato] Publish error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})

@app.get("/api/blotato/accounts")
async def blotato_accounts(request: Request):
    """Test Blotato API connection and list connected accounts."""
    get_verified_uid(request)
    try:
        from execution.blotato_bridge import test_connection
        return test_connection()
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": _safe_error(str(e)), "connected": False})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e)), "connected": False})

@app.get("/api/blotato/schedule")
async def blotato_schedule(request: Request):
    """Get upcoming schedule + next optimal slot."""
    get_verified_uid(request)
    try:
        from execution.blotato_bridge import get_schedule_info
        return get_schedule_info()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})

class QualityCheckRequest(BaseModel):
    caption: str
    has_image: bool = False

@app.post("/api/blotato/quality-check")
async def blotato_quality_check(req: QualityCheckRequest, request: Request):
    """Score a caption against the quality gate without publishing."""
    get_verified_uid(request)
    try:
        from execution.blotato_bridge import get_quality_score
        return get_quality_score(req.caption, has_image=req.has_image)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})

# --- SETTINGS ENDPOINTS ---

class SettingsUpdateRequest(BaseModel):
    trackedProfileUrl: Optional[str] = None
    blotatoApiKey: Optional[str] = None

@app.get("/api/settings")
async def get_settings(request: Request):
    """Return current app settings for the authenticated user."""
    uid = get_verified_uid(request)
    try:
        from execution.supabase_client import get_all_settings
        
        data = get_all_settings(uid=uid)
        # Fallback: if Supabase has no URL yet, seed from .env so UI isn't blank
        if not data.get("trackedProfileUrl"):
            data["trackedProfileUrl"] = os.getenv("LINKEDIN_PROFILE_URL", "")
        # SEC-08: Never expose API keys to the frontend — mask sensitive fields
        if data.get("blotatoApiKey"):
            data["blotatoApiKey"] = "••••" + data["blotatoApiKey"][-4:]
        return data
    except Exception as e:
        print(f"[settings] Read failed, using .env fallback: {e}")
        return {"trackedProfileUrl": os.getenv("LINKEDIN_PROFILE_URL", "")}

@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest, request: Request, background_tasks: BackgroundTasks):
    """Persist settings for the authenticated user."""
    uid = get_verified_uid(request)
    try:
        from execution.supabase_client import update_settings as sb_update, _write_local_settings
        payload = {k: v for k, v in req.model_dump().items() if v is not None}
        
        # Save locally immediately so UI doesn't hang — per-user cache
        _write_local_settings(payload, uid=uid)
        
        # Supabase upsert in the background
        background_tasks.add_task(sb_update, payload, uid)
        
        return {"status": "saved", "data": payload}
    except Exception as e:
        print(f"[settings] POST /api/settings error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})

# --- LEAD INTELLIGENCE ENDPOINTS ---

class LeadScanRequest(BaseModel):
    post_urls: Optional[List[str]] = None  # Optional: if None, reads from surveillance data

@app.post("/api/run-lead-scan")
async def run_lead_scan(req: LeadScanRequest, request: Request, background_tasks: BackgroundTasks):
    """Triggers lead scan in the background. Use GET /api/leads/data to poll for results."""
    uid = get_verified_uid(request)
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
    uid = get_verified_uid(request)
    leads_file = f".tmp/leads_data_{uid}.json"
    if os.path.exists(leads_file):
        try:
            with open(leads_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": _safe_error(str(e), fallback="Error loading leads.")})
    return {"summary": {"total_leads": 0, "scanned_posts": 0}, "leads": []}

# --- SURVEILLANCE ENDPOINTS ---

@app.get("/api/surveillance/data")
async def get_surveillance_data(request: Request):
    uid = get_verified_uid(request)
    data_file = f".tmp/surveillance_data_{uid}.json"
    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": _safe_error(str(e), fallback="Error loading data.")})
    return {"summary": {"total_posts": 0}, "posts": []}

class SurveillanceRefreshRequest(BaseModel):
    days: int = 30

@app.post("/api/surveillance/refresh")
async def refresh_surveillance_data(req: SurveillanceRefreshRequest, request: Request, background_tasks: BackgroundTasks):
    uid = get_verified_uid(request)
    days = max(1, min(req.days, 365))  # clamp to 1–365
    def run_scrape():
        print(f"Manual refresh of surveillance data triggered (range: {days} days, uid: {uid}).")
        subprocess.run(["python", "execution/surveillance_scraper.py", "--days", str(days), "--uid", uid], env=RUN_ENV)
        
    background_tasks.add_task(run_scrape)
    return {"message": f"Surveillance refresh started ({days} days)."}

# --- BRAND ASSETS ENDPOINTS ---

class PreviewBrandRequest(BaseModel):
    url: str
    user_id: Optional[str] = None

class SaveBrandRequest(BaseModel):
    brand_assets: dict
    user_id: Optional[str] = None

@app.post("/api/preview-brand")
async def preview_brand(req: PreviewBrandRequest, request: Request):
    """Preview brand extraction from URL without saving."""
    uid = get_verified_uid(request)
    print(f"[Brand] Preview extraction for URL: {req.url}")
    
    try:
        from execution.brand_extractor import BrandExtractor, BrandValidationError
        
        extractor = BrandExtractor()
        brand_assets = extractor.preview_brand(req.url)
        
        return brand_assets
        
    except BrandValidationError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        print(f"[Brand] Preview error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e), fallback="Failed to extract brand. Please try again.")})

@app.post("/api/save-brand")
async def save_brand(req: SaveBrandRequest, request: Request):
    """Save brand assets to user profile."""
    uid = get_verified_uid(request)
    print(f"[Brand] Saving brand assets for user: {uid}")
    
    try:
        from execution.brand_extractor import validate_brand_assets
        from execution.supabase_client import update_user_brand
        
        # Validate brand assets
        is_valid, errors = validate_brand_assets(req.brand_assets)
        if not is_valid:
            return JSONResponse(status_code=400, content={"error": "Validation failed", "details": errors})
        
        # Save to Supabase
        success = update_user_brand(req.brand_assets, uid=uid)
        
        if success:
            # Embed brand data into vector DB for structured retrieval
            try:
                from execution.rag_manager import embed_user_knowledge
                from execution.supabase_client import get_user_profile
                profile = get_user_profile(uid)
                embed_user_knowledge(uid, profile=profile, brand=req.brand_assets)
            except Exception as embed_err:
                print(f"[Brand] Vector embedding warning (non-blocking): {embed_err}")
            return {"success": True, "message": "Brand assets saved successfully"}
        else:
            return JSONResponse(status_code=500, content={"error": "Failed to save brand assets"})
            
    except Exception as e:
        print(f"[Brand] Save error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e), fallback="Failed to save brand.")})

@app.get("/api/brand")
async def get_brand(request: Request):
    """Get current user's brand assets."""
    uid = get_verified_uid(request)
    
    try:
        from execution.supabase_client import get_user_brand
        
        brand = get_user_brand(uid)
        
        if brand:
            return {"success": True, "brand_assets": brand}
        else:
            # Return default brand
            return {
                "success": True,
                "brand_assets": {
                    "brand_name": "",
                    "primary_color": "#F9C74F",
                    "secondary_color": "#0E0E0E",
                    "accent_color": "#FCF0D5",
                    "font_family": "Inter",
                    "logo_url": "",
                    "visual_style": "",
                    "tone_of_voice": ""
                }
            }
            
    except Exception as e:
        print(f"[Brand] Get error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e), fallback="Failed to get brand.")})

# --- VOICE ENGINE ENDPOINTS (Rebuilt) ---

@app.post("/api/voice/scrape-profile")
async def voice_scrape_profile(request: Request):
    """Scrape a LinkedIn profile via Apify → LLM analysis → vector DB chunks."""
    uid = get_verified_uid(request)
    body = await request.json()
    linkedin_url = (body.get("linkedin_url") or "").strip()
    if not linkedin_url or "linkedin.com" not in linkedin_url:
        return JSONResponse(status_code=400, content={"error": "Valid LinkedIn URL required"})

    try:
        from execution.apify_linkedin import scrape_single_profile, normalize_url
        from execution.crm_db import get_profile_by_url, upsert_profile
        from execution.profile_analyzer import analyze_profile, create_profile_chunks
        from execution.rag_manager import RAGManager, VoiceChunk

        url = normalize_url(linkedin_url)

        # Step 1: Check for existing rich profile (skip re-scrape if data is fresh)
        existing = get_profile_by_url(uid, url)
        raw_data = existing.get("raw_json") if existing else None
        has_rich = raw_data and isinstance(raw_data, dict) and len(raw_data) > 2
        analyzed = existing.get("summary") if existing else None
        has_analysis = analyzed and isinstance(analyzed, dict) and analyzed.get("bio")
        if existing and has_rich and has_analysis:
            print(f"[Voice] Profile already analyzed: {url[:50]}")
            # Return existing analyzed profile
            result = dict(existing)
            result["analyzed_profile"] = analyzed
            return {"success": True, "profile": result}

        # Step 2: Scrape via Apify
        print(f"[Voice] Scraping profile via Apify: {url[:50]}")
        raw = scrape_single_profile(url)
        if not raw:
            # Store minimal profile
            profile = upsert_profile(user_id=uid, linkedin_url=url, is_owner=True)
            return {"success": True, "profile": profile, "analyzed_profile": None}

        # Step 3: Send raw Apify output to LLM for structured analysis
        print(f"[Voice] Analyzing profile via LLM...")
        analyzed_profile = analyze_profile(raw, linkedin_url=url)

        # Step 4: Store in DB (raw_json + analyzed_profile as summary)
        profile = upsert_profile(
            user_id=uid,
            linkedin_url=url,
            raw_json=raw,
            summary=analyzed_profile,
            is_owner=True,
        )

        # Step 5: Create chunks and store in vector DB
        chunks_data = create_profile_chunks(analyzed_profile)
        if chunks_data:
            try:
                rag = RAGManager()
                voice_chunks = [
                    VoiceChunk(
                        content=c["content"],
                        source_type=c["source_type"],
                        metadata=c["metadata"],
                    )
                    for c in chunks_data
                ]
                stored = rag.store_voice_chunks(uid, voice_chunks)
                print(f"[Voice] Stored {len(voice_chunks)} profile chunks in vector DB: {stored}")
            except Exception as chunk_err:
                print(f"[Voice] Chunk storage error (non-fatal): {chunk_err}")

        # Step 6: Return profile + analyzed data
        result = dict(profile) if profile else {}
        result["analyzed_profile"] = analyzed_profile
        return {"success": True, "profile": result}

    except Exception as e:
        print(f"[Voice] Scrape profile error: {e}")
        import traceback; traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})


@app.get("/api/voice/profile")
async def voice_get_profile(request: Request):
    """Get the user's own LinkedIn profile."""
    uid = get_verified_uid(request)
    try:
        from execution.crm_db import get_owner_profile
        profile = get_owner_profile(uid)
        return {"success": True, "profile": profile}
    except Exception as e:
        print(f"[Voice] Get profile error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})


@app.post("/api/upload-linkedin")
async def upload_linkedin(request: Request, background_tasks: BackgroundTasks):
    """Upload one or more LinkedIn ZIP exports for processing (rebuilt)."""
    uid = get_verified_uid(request)

    form = await request.form()
    MAX_ZIP_SIZE = 50 * 1024 * 1024
    zip_contents: list = []
    zip_filenames: list = []

    for key in form:
        item = form[key]
        if not hasattr(item, 'filename') or not item.filename:
            continue
        if not item.filename.lower().endswith('.zip'):
            return JSONResponse(status_code=400, content={"error": f"'{item.filename}' is not a ZIP archive."})
        raw = await item.read()
        if len(raw) > MAX_ZIP_SIZE:
            return JSONResponse(status_code=413, content={"error": f"'{item.filename}' too large ({len(raw)//(1024*1024)}MB). Max 50MB."})
        zip_contents.append(raw)
        zip_filenames.append(item.filename)

    if not zip_contents:
        return JSONResponse(status_code=400, content={"error": "No ZIP files provided"})
    
    try:
        job_id = f"linkedin_{uid}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        file_count = len(zip_contents)

        def process_linkedin_rebuild():
            """Rebuilt background processor using new execution scripts."""
            try:
                from execution.zip_processor import process_zip, derive_contact_name
                from execution.crm_db import (
                    wipe_user_crm_data, upsert_profile, upsert_conversation,
                    upsert_crm_contact, update_processing_status, get_crm_contact_count,
                )
                from execution.apify_linkedin import scrape_and_store_from_connection
                from execution.conversation_analyzer import analyze_conversation, analyze_connection
                from execution.profile_summarizer import summarize_profile, get_summary_text
                from execution.persona_builder import build_user_persona
                from execution.rag_manager import RAGManager
                from execution.knowledge_extractor import extract_structured_knowledge
                from execution import supabase_client as sc
                from collections import Counter

                update_user_profile_fn = getattr(sc, "update_user_profile", None)
                get_user_profile_fn = getattr(sc, "get_user_profile", None)
                get_user_brand_fn = getattr(sc, "get_user_brand", None)
                update_user_brand_fn = getattr(sc, "update_user_brand", None)

                # ── Phase 1: Set processing status ─────────────────────────
                if callable(update_user_profile_fn):
                    update_user_profile_fn(uid, {
                        "linkedin_processing_status": "processing",
                        "linkedin_imported": False,
                        "voice_chunks_count": 0,
                        "crm_contacts_count": 0,
                        "processing_phase": f"Parsing {file_count} LinkedIn export(s)...",
                    })

                # ── Phase 2: Parse ZIP(s) with new zip_processor ───────────
                # Merge multiple ZIPs by processing each and combining results
                all_conversations = {}
                all_connections = []
                zip_profile = None

                for i, zb in enumerate(zip_contents):
                    parsed = process_zip(zb)
                    if parsed["status"] == "error":
                        print(f"[LinkedIn] ZIP {i+1} error: {parsed['message']}")
                        continue
                    # Merge conversations
                    for conv_id, msgs in parsed.get("conversations", {}).items():
                        if conv_id in all_conversations:
                            existing_dates = {m.get("date") for m in all_conversations[conv_id]}
                            for m in msgs:
                                if m.get("date") not in existing_dates:
                                    all_conversations[conv_id].append(m)
                            all_conversations[conv_id].sort(key=lambda x: x.get("date", ""))
                        else:
                            all_conversations[conv_id] = msgs
                    # Merge connections (dedup by url)
                    seen_urls = {c.get("linkedin_url") for c in all_connections if c.get("linkedin_url")}
                    for conn in parsed.get("connections", []):
                        url = conn.get("linkedin_url", "")
                        if url and url in seen_urls:
                            continue
                        if url:
                            seen_urls.add(url)
                        all_connections.append(conn)
                    # Take first profile found
                    if not zip_profile and parsed.get("profile"):
                        zip_profile = parsed["profile"]

                total_convs = len(all_conversations)
                total_conns = len(all_connections)
                print(f"[LinkedIn] Parsed {file_count} ZIP(s): {total_convs} conversations, {total_conns} connections")

                if total_convs == 0 and total_conns == 0:
                    if callable(update_user_profile_fn):
                        update_user_profile_fn(uid, {
                            "linkedin_processing_status": "error",
                            "linkedin_imported": False,
                            "processing_phase": "No data found in ZIP",
                        })
                    return

                # ── Phase 3: Wipe old CRM data (fresh rebuild) ─────────────
                if callable(update_user_profile_fn):
                    update_user_profile_fn(uid, {"processing_phase": "Wiping old CRM data..."})
                wipe_counts = wipe_user_crm_data(uid)
                print(f"[LinkedIn] Wiped old data: {wipe_counts}")

                # ── Phase 4: Store user's own profile ──────────────────────
                if zip_profile:
                    owner_url = zip_profile.get("profile_url", "")
                    if owner_url:
                        upsert_profile(
                            user_id=uid,
                            linkedin_url=owner_url,
                            is_owner=True,
                            first_name=zip_profile.get("first_name", ""),
                            last_name=zip_profile.get("last_name", ""),
                            title=zip_profile.get("headline", ""),
                            industry=zip_profile.get("industry", ""),
                            location=zip_profile.get("location", ""),
                        )

                # ── Phase 5: Build persona + voice engine (legacy compat) ──
                if callable(update_user_profile_fn):
                    update_user_profile_fn(uid, {"processing_phase": "Extracting knowledge & persona..."})

                # Build legacy linkedin_data structure for persona_builder/knowledge_extractor
                from execution.linkedin_parser import LinkedInParser
                parser = LinkedInParser()
                legacy_zip_data = parser.validate_and_parse_zip(zip_contents[0])
                proceed = legacy_zip_data.get("proceed", legacy_zip_data.get("status") in ("complete", "partial"))

                persona = None
                chunks_stored = 0
                if proceed:
                    brand_assets = get_user_brand_fn(uid) if callable(get_user_brand_fn) else {}

                    try:
                        structured = extract_structured_knowledge(legacy_zip_data, brand_assets)
                    except Exception as ke:
                        print(f"[LinkedIn] Knowledge extraction error: {ke}")
                        structured = {}

                    quota_exhausted = bool(structured.get("_quota_exhausted")) if isinstance(structured, dict) else False
                    if quota_exhausted:
                        structured = {}

                    if structured.get("persona"):
                        persona = structured["persona"]
                    elif quota_exhausted:
                        persona = {
                            "professional_bio": "",
                            "writing_style_rules": ["Professional tone", "Clear and concise"],
                            "core_skills": ["Leadership", "Strategy"],
                            "expertise_areas": ["Business"],
                            "tone_of_voice": "Professional",
                        }
                    else:
                        try:
                            persona = build_user_persona(legacy_zip_data)
                        except Exception as pe:
                            print(f"[LinkedIn] Persona build error: {pe}")
                            persona = {"professional_bio": "Profile imported from LinkedIn"}

                    knowledge_chunks = structured.get("knowledge_chunks") or []
                    structured_brand = structured.get("brand") or {}
                    structured_products = structured.get("products_services") or []

                    # Merge brand
                    if structured_brand and callable(update_user_brand_fn):
                        merged_brand = dict(brand_assets or {})
                        for key in ("tagline", "description", "tone_of_voice", "visual_style"):
                            if not merged_brand.get(key) and structured_brand.get(key):
                                merged_brand[key] = structured_brand[key]
                        # Merge products
                        seen_prods = set()
                        merged_products = []
                        for item in (merged_brand.get("products_services") or []) + structured_products:
                            name = str(item.get("name", "")).strip().lower()
                            if name and name not in seen_prods:
                                seen_prods.add(name)
                                merged_products.append(item)
                        merged_brand["products_services"] = merged_products
                        update_user_brand_fn(merged_brand, uid)

                    # Build voice engine
                    if callable(update_user_profile_fn):
                        update_user_profile_fn(uid, {"processing_phase": "Building voice engine..."})
                    try:
                        rag = RAGManager()
                        chunks_stored = rag.process_linkedin_data(uid, legacy_zip_data, knowledge_chunks=knowledge_chunks)
                    except Exception as rag_err:
                        print(f"[LinkedIn] RAG error: {rag_err}")
                        chunks_stored = 0

                    # Save persona early
                    if callable(update_user_profile_fn):
                        update_user_profile_fn(uid, {
                            "persona": persona,
                            "linkedin_imported": True,
                            "voice_chunks_count": chunks_stored,
                            "processing_phase": "Analyzing conversations for CRM...",
                        })
                        print(f"[LinkedIn] Persona saved early ({chunks_stored} voice chunks)")

                    # Embed structured profile+brand into vector DB for granular retrieval
                    try:
                        from execution.rag_manager import embed_user_knowledge
                        profile_snapshot = get_user_profile_fn(uid) if callable(get_user_profile_fn) else {}
                        brand_snapshot = get_user_brand_fn(uid) if callable(get_user_brand_fn) else {}
                        embed_count = embed_user_knowledge(uid, profile=profile_snapshot, brand=brand_snapshot)
                        print(f"[LinkedIn] Embedded {embed_count} structured knowledge chunks")
                    except Exception as ek_err:
                        print(f"[LinkedIn] Structured embedding warning (non-blocking): {ek_err}")

                # ── Phase 6: Build connection lookup for name matching ──────
                connection_lookup = {}  # normalized_name -> connection dict
                connection_fuzzy = []   # (normalized_name, connection) for fuzzy
                for conn in all_connections:
                    first = conn.get("first_name", "").strip()
                    last = conn.get("last_name", "").strip()
                    full = conn.get("full_name", "") or f"{first} {last}".strip()
                    for candidate in {full, f"{first} {last}".strip(), first, last}:
                        nk = unicodedata.normalize("NFKD", (candidate or "").strip()).encode("ascii", "ignore").decode("ascii").lower().strip()
                        nk = re.sub(r"[^a-z\s]", " ", nk)
                        nk = " ".join(t for t in nk.split() if t)
                        if nk and nk not in connection_lookup:
                            connection_lookup[nk] = conn
                    pk = unicodedata.normalize("NFKD", (full or "").strip()).encode("ascii", "ignore").decode("ascii").lower().strip()
                    pk = re.sub(r"[^a-z\s]", " ", pk)
                    pk = " ".join(t for t in pk.split() if t)
                    if pk:
                        connection_fuzzy.append((pk, conn))

                # Helper to find connection by name
                def _find_conn(name: str) -> Optional[Dict]:
                    nk = unicodedata.normalize("NFKD", (name or "").strip()).encode("ascii", "ignore").decode("ascii").lower().strip()
                    nk = re.sub(r"[^a-z\s]", " ", nk)
                    nk = " ".join(t for t in nk.split() if t)
                    if nk in connection_lookup:
                        return connection_lookup[nk]
                    parts = nk.split()
                    if len(parts) >= 2:
                        for combo in [f"{parts[0]} {parts[-1]}", f"{parts[-1]} {parts[0]}"]:
                            if combo in connection_lookup:
                                return connection_lookup[combo]
                    for key, c in connection_lookup.items():
                        if nk and (nk in key or key in nk):
                            return c
                    if nk and connection_fuzzy:
                        best_s, best_c = 0.0, None
                        for key, c in connection_fuzzy:
                            s = SequenceMatcher(None, nk, key).ratio()
                            if s > best_s:
                                best_s, best_c = s, c
                        if best_s >= 0.80:
                            return best_c
                    return None

                # Build user context for LLM analysis
                user_summary = ""
                user_products = ""
                if persona:
                    user_summary = persona.get("professional_bio", "")
                brand_data = get_user_brand_fn(uid) if callable(get_user_brand_fn) else {}
                if isinstance(brand_data, dict):
                    prods = brand_data.get("products_services", [])
                    if prods:
                        user_products = "; ".join(
                            p.get("name", "") + ": " + p.get("description", "")
                            for p in prods if isinstance(p, dict)
                        )

                user_display_name = ""
                if zip_profile:
                    user_display_name = f"{zip_profile.get('first_name', '')} {zip_profile.get('last_name', '')}".strip()

                # ── Phase 7: Process conversations → CRM contacts ──────────
                crm_contacts_added = 0
                crm_tag_counter = Counter()
                ingestion_start = time.time()

                for conv_id, thread in all_conversations.items():
                    # Derive contact name
                    contact_name = derive_contact_name(thread, user_display_name)

                    # Find matching connection
                    conn = _find_conn(contact_name)
                    contact_info = {
                        "first_name": contact_name.split()[0] if contact_name.split() else "",
                        "last_name": " ".join(contact_name.split()[1:]) if len(contact_name.split()) > 1 else "",
                        "title": conn.get("position", "") if conn else "",
                        "company": conn.get("company", "") if conn else "",
                        "industry": "",
                        "years_of_experience": 0,
                        "connected_on": conn.get("connected_on", "") if conn else "",
                        "_user_name": user_display_name,
                    }

                    # Store minimal profile for this contact
                    profile_row = None
                    conn_url = conn.get("linkedin_url", "") if conn else ""
                    if conn:
                        profile_row = scrape_and_store_from_connection(uid, conn)

                    # Store conversation
                    conv_row = upsert_conversation(
                        user_id=uid,
                        conversation_id=conv_id,
                        contact_profile_id=profile_row["id"] if profile_row else None,
                        thread=thread,
                    )

                    # LLM analysis (quick_fail=True for bulk)
                    analysis = analyze_conversation(
                        user_summary=user_summary,
                        user_products=user_products,
                        contact_info=contact_info,
                        thread=thread,
                        quick_fail=True,
                    )

                    # Upsert CRM contact
                    upsert_crm_contact(
                        user_id=uid,
                        profile_id=profile_row["id"] if profile_row else str(uuid.uuid4()),
                        conversation_id=conv_row["id"] if conv_row else None,
                        analysis=analysis,
                        source="message",
                        linkedin_url=conn_url,
                        linkedin_conversation_id=conv_id,
                        connected_on=contact_info.get("connected_on", ""),
                    )

                    crm_contacts_added += 1
                    crm_tag_counter[analysis.get("tag", "prospect")] += 1

                    # Progress updates every 25 contacts
                    if crm_contacts_added % 25 == 0:
                        time.sleep(0.05)
                        if callable(update_user_profile_fn):
                            update_user_profile_fn(uid, {
                                "crm_contacts_count": crm_contacts_added,
                                "processing_phase": f"Analyzing contacts... {crm_contacts_added}/{total_convs}",
                            })

                # ── Phase 8: Process connection-only contacts ───────────────
                if callable(update_user_profile_fn):
                    update_user_profile_fn(uid, {"processing_phase": "Processing connection-only contacts..."})

                # Build set of names already processed via conversations
                processed_names = set()
                for thread in all_conversations.values():
                    name = derive_contact_name(thread, user_display_name)
                    if name and name != "Unknown Contact":
                        processed_names.add(name.lower())

                conn_only_added = 0
                for conn in all_connections:
                    full_name = conn.get("full_name", "").strip()
                    if not full_name or full_name.lower() in processed_names:
                        continue

                    contact_info = {
                        "first_name": conn.get("first_name", ""),
                        "last_name": conn.get("last_name", ""),
                        "title": conn.get("position", ""),
                        "company": conn.get("company", ""),
                        "industry": "",
                        "years_of_experience": 0,
                        "connected_on": conn.get("connected_on", ""),
                    }

                    # Store profile
                    profile_row = scrape_and_store_from_connection(uid, conn)

                    # LLM analysis for connection-only contacts
                    analysis = analyze_connection(
                        user_summary=user_summary,
                        user_products=user_products,
                        contact_info=contact_info,
                        quick_fail=True,
                    )

                    upsert_crm_contact(
                        user_id=uid,
                        profile_id=profile_row["id"] if profile_row else str(uuid.uuid4()),
                        analysis=analysis,
                        source="connection",
                        linkedin_url=conn.get("linkedin_url", ""),
                        connected_on=conn.get("connected_on", ""),
                    )

                    conn_only_added += 1
                    crm_contacts_added += 1
                    crm_tag_counter[analysis.get("tag", "prospect")] += 1

                    if conn_only_added % 50 == 0:
                        time.sleep(0.02)
                        if callable(update_user_profile_fn):
                            update_user_profile_fn(uid, {
                                "crm_contacts_count": crm_contacts_added,
                                "processing_phase": f"Processing connections... {conn_only_added}/{total_conns}",
                            })

                # ── Phase 9: Final status ──────────────────────────────────
                if callable(update_user_profile_fn):
                    update_user_profile_fn(uid, {
                        "persona": persona or {},
                        "linkedin_imported": True,
                        "linkedin_processing_status": "completed",
                        "voice_chunks_count": chunks_stored,
                        "crm_contacts_count": crm_contacts_added,
                        "processing_phase": "completed",
                    })

                duration_s = time.time() - ingestion_start
                tag_dist = ", ".join(f"{k}: {v}" for k, v in sorted(crm_tag_counter.items()))
                print(f"[LinkedIn] Completed in {duration_s:.1f}s: {crm_contacts_added} CRM contacts ({tag_dist}), {chunks_stored} voice chunks")

            except Exception as e:
                print(f"[LinkedIn] Processing error: {e}")
                import traceback
                traceback.print_exc()
                try:
                    from execution import supabase_client as sc
                    fn = getattr(sc, "update_user_profile", None)
                    if callable(fn):
                        fn(uid, {"linkedin_processing_status": "error", "linkedin_imported": False})
                except Exception:
                    pass

        background_tasks.add_task(process_linkedin_rebuild)

        return {
            "success": True,
            "job_id": job_id,
            "message": f"LinkedIn import started ({file_count} file(s)). Check status for progress.",
        }

    except Exception as e:
        print(f"[LinkedIn] Upload error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e), fallback="Upload failed.")})

# ── Voice Engine: Search + Persona ─────────────────────────────────────────────

class VoiceSearchRequest(BaseModel):
    topic: str
    user_id: Optional[str] = None

@app.post("/api/search-voice")
async def search_voice(req: VoiceSearchRequest, request: Request):
    """Search voice context for a topic."""
    uid = get_verified_uid(request)
    try:
        from execution.rag_manager import search_voice_context
        context, score = search_voice_context(uid, req.topic)
        return {"success": True, "context": context, "relevance_score": score, "has_relevant_context": score >= 0.6}
    except Exception as e:
        print(f"[Voice] Search error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e), fallback="Search failed.")})


@app.get("/api/voice/status")
async def voice_status(request: Request):
    """Get processing status for the Voice Engine / CRM pipeline."""
    uid = get_verified_uid(request)
    try:
        from execution import supabase_client as sc
        from execution.crm_db import get_crm_contact_count
        get_user_profile_fn = getattr(sc, "get_user_profile", None)
        profile = get_user_profile_fn(uid) if callable(get_user_profile_fn) else {}
        crm_count = get_crm_contact_count(uid)
        return {
            "success": True,
            "processing_status": (profile or {}).get("linkedin_processing_status", "idle"),
            "processing_phase": (profile or {}).get("processing_phase", ""),
            "crm_contacts_count": crm_count,
            "voice_chunks_count": (profile or {}).get("voice_chunks_count", 0),
            "linkedin_imported": (profile or {}).get("linkedin_imported", False),
        }
    except Exception as e:
        print(f"[Voice] Status error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})


@app.get("/api/persona")
async def get_persona(request: Request):
    """Get user's persona data (rebuilt — uses new CRM tables for counts)."""
    uid = get_verified_uid(request)
    try:
        from execution import supabase_client as sc
        from execution.crm_db import get_crm_contact_count
        get_user_profile_fn = getattr(sc, "get_user_profile", None)
        profile = get_user_profile_fn(uid) if callable(get_user_profile_fn) else {}

        if profile and profile.get("persona"):
            stored_status = profile.get("linkedin_processing_status")
            processing_phase = profile.get("processing_phase", "")
            voice_chunks_count = profile.get("voice_chunks_count", 0)
            crm_contacts_count = get_crm_contact_count(uid)

            # Stale processing detection (>30 min)
            effective_status = stored_status
            if stored_status == "processing":
                updated_at = profile.get("updated_at", "")
                if updated_at:
                    try:
                        from datetime import datetime as _dt, timezone as _tz
                        pt = _dt.fromisoformat(updated_at.replace("Z", "+00:00"))
                        if (datetime.now(_tz.utc) - pt).total_seconds() > 1800:
                            effective_status = "completed"
                            processing_phase = "completed"
                    except Exception:
                        pass
            elif stored_status != "completed":
                effective_status = "completed"

            return {
                "success": True,
                "persona": profile["persona"],
                "linkedin_imported": True,
                "processing_status": effective_status,
                "voice_chunks_count": voice_chunks_count,
                "crm_contacts_count": crm_contacts_count,
                "processing_phase": processing_phase if effective_status == "processing" else "completed",
                "ingestion_diagnostics": profile.get("ingestion_diagnostics") or {},
            }
        else:
            status = profile.get("linkedin_processing_status") if profile else None
            if status == "processing" and profile:
                updated_at = profile.get("updated_at", "")
                if updated_at:
                    try:
                        from datetime import datetime as _dt, timezone as _tz
                        pt = _dt.fromisoformat(updated_at.replace("Z", "+00:00"))
                        if (datetime.now(_tz.utc) - pt).total_seconds() > 1800:
                            fn = getattr(sc, "update_user_profile", None)
                            if callable(fn):
                                fn(uid, {"linkedin_processing_status": "error"})
                            status = "error"
                    except Exception:
                        pass
            return {
                "success": True,
                "persona": None,
                "linkedin_imported": False,
                "processing_status": status,
                "voice_chunks_count": profile.get("voice_chunks_count", 0) if profile else 0,
                "crm_contacts_count": profile.get("crm_contacts_count", 0) if profile else 0,
                "processing_phase": profile.get("processing_phase", "") if profile else "",
                "ingestion_diagnostics": profile.get("ingestion_diagnostics") or {} if profile else {},
            }
    except Exception as e:
        print(f"[Persona] Get error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e), fallback="Failed to get persona.")})

# --- ADMIN ENDPOINTS ---

@app.delete("/api/admin/user-data/{uid}")
async def admin_purge_user_data(uid: str, request: Request):
    """Purge ALL data for a user_id — voice chunks, CRM contacts, local profile.
    Use after deleting a user from Supabase Auth to prevent stale data issues.
    """
    caller_uid = get_verified_uid(request)
    _admin_uids = {u.strip() for u in os.getenv("ADMIN_UIDS", "").split(",") if u.strip()}
    is_self = caller_uid == uid
    is_admin = caller_uid in _admin_uids
    if not is_self and not is_admin:
        return JSONResponse(status_code=403, content={"error": "You can only purge your own data (or be an admin)"})

    results = {}
    try:
        from execution import supabase_client as sc
        client = sc._get_client()

        r1 = client.table("voice_chunks").delete().eq("user_id", uid).execute()
        results["voice_chunks_deleted"] = len(r1.data)

        r2 = client.table("crm_contacts").delete().eq("user_id", uid).execute()
        results["crm_contacts_deleted"] = len(r2.data)

        # Clear local profile
        import json, os
        profile_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".local_profiles.json")
        if os.path.exists(profile_file):
            with open(profile_file, "r", encoding="utf-8") as f:
                all_profiles = json.load(f)
            if uid in all_profiles:
                del all_profiles[uid]
                with open(profile_file, "w", encoding="utf-8") as f:
                    json.dump(all_profiles, f, indent=2, ensure_ascii=False)
                results["local_profile_cleared"] = True

        results["success"] = True
        results["uid"] = uid
        print(f"[Admin] Purged data for uid={uid}: {results}")
        return results
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})


# --- LLM QUOTA & MAINTENANCE ---

@app.get("/api/health/llm-quota")
async def health_llm_quota(request: Request):
    """Return LLM quota health status — call counts, failure rates, alerts."""
    uid = get_verified_uid(request)
    try:
        from execution.quota_monitor import get_health
        return {"success": True, **get_health()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})


class MaintenanceModeRequest(BaseModel):
    active: bool
    reason: str = Field(default="", max_length=500)
    resume_time: str = Field(default="", max_length=100)

@app.post("/api/admin/maintenance")
async def toggle_maintenance(req: MaintenanceModeRequest, request: Request):
    """Toggle maintenance mode. Blocks all LLM calls when active."""
    uid = get_verified_uid(request)
    try:
        from execution.quota_monitor import set_maintenance_mode, get_maintenance_info
        set_maintenance_mode(req.active, req.reason, req.resume_time)
        return {"success": True, "maintenance": get_maintenance_info()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})


@app.get("/api/admin/maintenance")
async def get_maintenance_status(request: Request):
    """Check current maintenance mode status."""
    try:
        from execution.quota_monitor import get_maintenance_info
        return {"success": True, "maintenance": get_maintenance_info()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})


@app.post("/api/crm/reanalyze")
async def crm_reanalyze(request: Request, background_tasks: BackgroundTasks):
    """Re-analyze unanalyzed CRM contacts via LLM.

    Finds contacts with tag='unanalyzed', retrieves their conversation threads,
    and re-runs LLM analysis. Runs in background to avoid timeout.
    """
    uid = get_verified_uid(request)
    try:
        from execution.crm_db import get_crm_contacts as crm_db_get_contacts

        # Count unanalyzed contacts
        unanalyzed = crm_db_get_contacts(uid, tag_filter="unanalyzed")
        count = len(unanalyzed)

        if count == 0:
            return {"success": True, "message": "No unanalyzed contacts found", "count": 0}

        # Run re-analysis in background
        background_tasks.add_task(_reanalyze_contacts, uid, unanalyzed)

        return {
            "success": True,
            "message": f"Re-analyzing {count} unanalyzed contact(s) in background",
            "count": count,
        }
    except Exception as e:
        print(f"[CRM] Reanalyze error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})


def _reanalyze_contacts(uid: str, contacts: list):
    """Background task: re-analyze unanalyzed contacts."""
    from execution.crm_db import (
        get_conversation_by_id, upsert_crm_contact,
    )
    from execution.conversation_analyzer import analyze_conversation, analyze_connection
    from execution import supabase_client as sc

    get_user_profile_fn = getattr(sc, "get_user_profile", None)
    get_user_brand_fn = getattr(sc, "get_user_brand", None)
    profile = get_user_profile_fn(uid) if callable(get_user_profile_fn) else {}
    persona = (profile or {}).get("persona", {})
    brand = get_user_brand_fn(uid) if callable(get_user_brand_fn) else {}
    products = brand.get("products_services", []) if isinstance(brand, dict) else []

    user_summary = persona.get("professional_bio", "") if isinstance(persona, dict) else ""
    user_products = "; ".join(
        p.get("name", "") + ": " + p.get("description", "")
        for p in products if isinstance(p, dict)
    ) if products else ""

    reanalyzed = 0
    still_failed = 0

    for contact in contacts:
        contact_info = {
            "first_name": contact.get("first_name", ""),
            "last_name": contact.get("last_name", ""),
            "title": contact.get("title", ""),
            "company": contact.get("company", ""),
            "industry": contact.get("industry", ""),
            "years_of_experience": contact.get("years_of_experience", 0),
            "connected_on": contact.get("connected_on", ""),
        }

        # Try to get conversation thread
        conv_id = contact.get("conversation_id")
        thread = []
        if conv_id:
            conv = get_conversation_by_id(conv_id)
            if conv:
                thread = conv.get("thread", [])

        # Run LLM analysis
        if thread:
            analysis = analyze_conversation(
                user_summary=user_summary,
                user_products=user_products,
                contact_info=contact_info,
                thread=thread,
                quick_fail=False,  # Don't quick-fail on re-analysis
            )
        else:
            analysis = analyze_connection(
                user_summary=user_summary,
                user_products=user_products,
                contact_info=contact_info,
                quick_fail=False,
            )

        # Update if LLM succeeded (tag != unanalyzed)
        if analysis.get("tag") != "unanalyzed":
            upsert_crm_contact(
                user_id=uid,
                profile_id=contact.get("profile_id", contact.get("id", "")),
                conversation_id=conv_id,
                analysis=analysis,
                source=contact.get("source", "message"),
                linkedin_url=contact.get("linkedin_url", ""),
                linkedin_conversation_id=contact.get("linkedin_conversation_id", ""),
                connected_on=contact.get("connected_on", ""),
            )
            reanalyzed += 1
        else:
            still_failed += 1

    print(f"[CRM] Re-analysis complete: {reanalyzed} updated, {still_failed} still unanalyzed")


# --- CRM ENDPOINTS (Rebuilt) ---

@app.get("/api/crm/contacts")
async def crm_contacts_list(
    tag: str = None,
    min_score: int = 0,
    request: Request = None,
):
    """Get CRM contacts with optional tag/score filtering (rebuilt)."""
    uid = get_verified_uid(request)
    try:
        from execution.crm_db import get_crm_contacts
        contacts = get_crm_contacts(uid, tag_filter=tag, min_score=min_score)
        return {"success": True, "contacts": contacts, "count": len(contacts)}
    except Exception as e:
        print(f"[CRM] Contacts error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e), fallback="Failed to get contacts.")})


@app.get("/api/crm/contacts/{contact_id}")
async def crm_contact_detail(contact_id: str, request: Request):
    """Get full CRM contact with profile + conversation data."""
    uid = get_verified_uid(request)
    try:
        from execution.crm_db import get_crm_contact_full
        contact = get_crm_contact_full(contact_id)
        if not contact:
            return JSONResponse(status_code=404, content={"error": "Contact not found"})
        # Verify ownership
        if contact.get("user_id") != uid:
            return JSONResponse(status_code=403, content={"error": "Access denied"})
        return {"success": True, "contact": contact}
    except Exception as e:
        print(f"[CRM] Contact detail error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e))})


@app.post("/api/crm/contacts/{contact_id}/generate-message")
async def crm_generate_message(contact_id: str, request: Request):
    """Generate a personalized draft message for a CRM contact (rebuilt)."""
    uid = get_verified_uid(request)
    try:
        from execution.crm_db import get_crm_contact_full, save_draft_message
        from execution.crm_message_drafter import generate_draft_message
        from execution import supabase_client as sc

        contact = get_crm_contact_full(contact_id)
        if not contact:
            return JSONResponse(status_code=404, content={"error": "Contact not found"})
        if contact.get("user_id") != uid:
            return JSONResponse(status_code=403, content={"error": "Access denied"})

        # Build user context
        get_user_profile_fn = getattr(sc, "get_user_profile", None)
        get_user_brand_fn = getattr(sc, "get_user_brand", None)
        profile = get_user_profile_fn(uid) if callable(get_user_profile_fn) else {}
        persona = (profile or {}).get("persona", {})
        brand = get_user_brand_fn(uid) if callable(get_user_brand_fn) else {}
        products = brand.get("products_services", []) if isinstance(brand, dict) else []

        user_summary = persona.get("professional_bio", "") if isinstance(persona, dict) else ""
        user_products = "; ".join(
            p.get("name", "") + ": " + p.get("description", "")
            for p in products if isinstance(p, dict)
        ) if products else ""

        # Get conversation thread if available
        conv = contact.get("conversation", {})
        thread = conv.get("thread", []) if conv else []

        gen_start = time.time()
        message = generate_draft_message(
            user_profile_summary=user_summary,
            user_products=user_products,
            contact_info=contact,
            conversation_thread=thread,
        )

        # Save draft
        save_draft_message(contact_id, message)

        return {
            "success": True,
            "message": message,
            "draft_saved": True,
            "duration_ms": int((time.time() - gen_start) * 1000),
        }
    except Exception as e:
        print(f"[CRM] Generate message error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e), fallback="Message generation failed.")})


class CRMDraftUpdateRequest(BaseModel):
    draft_message: str

@app.put("/api/crm/contacts/{contact_id}/draft")
async def crm_update_draft(contact_id: str, req: CRMDraftUpdateRequest, request: Request):
    """Save/update a draft message for a CRM contact."""
    uid = get_verified_uid(request)
    try:
        from execution.crm_db import save_draft_message
        ok = save_draft_message(contact_id, req.draft_message)
        if ok:
            return {"success": True, "draft_message": req.draft_message}
        return JSONResponse(status_code=500, content={"error": "Failed to save draft"})
    except Exception as e:
        print(f"[CRM] Draft update error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e), fallback="Failed to update draft.")})


@app.delete("/api/crm/contacts/{contact_id}")
async def crm_delete_contact(contact_id: str, request: Request):
    """Delete a CRM contact."""
    uid = get_verified_uid(request)
    try:
        from execution.crm_db import delete_crm_contact
        ok = delete_crm_contact(contact_id)
        if ok:
            return {"success": True, "message": "Contact deleted"}
        return JSONResponse(status_code=500, content={"error": "Failed to delete contact"})
    except Exception as e:
        print(f"[CRM] Delete error: {e}")
        return JSONResponse(status_code=500, content={"error": _safe_error(str(e), fallback="Delete failed.")})

# Explicit root route with no-cache so browsers always fetch the latest index.html
@app.get("/")
async def serve_index():
    return FileResponse(
        "frontend/index.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )

# Serve JS/CSS files with no-cache headers so deploys take effect immediately
_NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}

@app.get("/{filename:path}")
async def serve_frontend_file(filename: str):
    import mimetypes
    filepath = os.path.join("frontend", filename)
    if not os.path.isfile(filepath):
        # Fall through to 404
        return FileResponse("frontend/index.html", headers=_NO_CACHE_HEADERS)
    content_type, _ = mimetypes.guess_type(filepath)
    return FileResponse(filepath, headers=_NO_CACHE_HEADERS, media_type=content_type)


if __name__ == "__main__":
    import uvicorn
    # Allow port to be set by environment variable, default to 9999
    port = int(os.environ.get("PORT", 9999))
    uvicorn.run(app, host="0.0.0.0", port=port)
