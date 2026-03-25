"""
Modal deployment for LinkedIn Post Generator v1.1
Deploys the full-stack FastAPI app (backend + frontend) as a single Modal web endpoint.

Usage:
  1. Install Modal:        pip install modal
  2. Authenticate:         modal token new
  3. Create secrets:       modal secret create linkedin-post-generator \
                             GOOGLE_GEMINI_API_KEY=xxx \
                             APIFY_API_KEY=xxx \
                             APIFY_API_KEY_2=xxx \
                             APIFY_API_KEY_3=xxx \
                             APIFY_API_KEY_4=xxx \
                             APIFY_API_KEY_5=xxx \
                             BASEROW_URL=https://api.baserow.io \
                             BASEROW_TOKEN=xxx \
                             BASEROW_TABLE_ID_GENERATED_CONTENT=xxx \
                             BASEROW_TABLE_ID_COMPETITOR_POSTS=xxx \
                             JINA_API_KEY=xxx \
                             SUPABASE_URL=xxx \
                             SUPABASE_SERVICE_ROLE_KEY=xxx \
                             SUPABASE_ANON_KEY=xxx \
                             LINKEDIN_PROFILE_URL=xxx \
                             FIRECRAWL_API_KEY=xxx \
                             GEMINI_TEXT_MODEL=gemini-3.1-pro-preview \
                             GEMINI_IMAGE_MODEL=gemini-3-pro-image-preview \
                             GEMINI_CRM_MODEL=gemini-3.1-pro-preview \
                             GEMINI_EMBEDDING_MODEL=gemini-embedding-001
  4. Deploy:               modal deploy modal_app.py
  5. Dev (hot-reload):     modal serve modal_app.py

Optional secrets (add if you use these features):
  BLOTATO_API_KEY        — LinkedIn publishing via Blotato
  IMGBB_API_KEY          — Image hosting for Blotato publishing
  CORS_ALLOWED_ORIGINS   — Comma-separated allowed origins (auto-configured if omitted)
  ADMIN_UIDS             — Comma-separated Supabase UIDs for admin endpoints

Supabase setup:
  - Add your Modal URL to Supabase Auth → URL Configuration → Redirect URLs:
    https://<your-modal-subdomain>--linkedin-post-generator-web.modal.run
    https://<your-modal-subdomain>--linkedin-post-generator-web.modal.run/**
"""

import modal

app = modal.App("linkedin-post-generator")

# ---------------------------------------------------------------------------
# Container image: install deps + copy project source into the image
# ---------------------------------------------------------------------------
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        # Core API server
        "fastapi>=0.110,<1.0",
        "uvicorn>=0.29,<1.0",
        "pydantic>=2.6,<2.10",
        "python-multipart>=0.0.9",
        # HTTP + environment
        "requests>=2.31,<3.0",
        "python-dotenv>=1.0,<2.0",
        # AI generation
        "google-genai==1.68.0",
        "openai>=1.30.0",
        "Pillow>=10.0,<12.0",
        # Research / scraping
        "apify-client>=1.7.0",
        "yt-dlp>=2024.8.6",
        # Supabase
        "supabase>=2.0.0",
        # Web search (Tavily) + parsing
        "beautifulsoup4>=4.12,<5.0",
        "tavily-python>=0.5.0",
        # LinkedIn data parsing
        "pandas>=2.0.0",
        # Utility
        "filelock>=3.13.0",
    )
    # Symlink python -> python3 so subprocess calls to "python" work
    .run_commands("ln -sf /usr/bin/python3 /usr/bin/python")
    # Copy project directories into the container image at /app
    .add_local_dir("frontend", remote_path="/app/frontend")
    .add_local_dir("execution", remote_path="/app/execution")
    .add_local_dir("directives", remote_path="/app/directives")
    .add_local_dir("Web-Search-tool", remote_path="/app/Web-Search-tool")
    # Skills required at runtime (Commented out because they were removed from the local workspace)
    # .add_local_dir(".agents/skills/brand-identity", remote_path="/app/.agents/skills/brand-identity")
    # .add_local_dir(".agents/skills/blotato_publisher", remote_path="/app/.agents/skills/blotato_publisher")
    # Copy top-level Python files
    .add_local_file("server.py", remote_path="/app/server.py")
    .add_local_file("orchestrator.py", remote_path="/app/orchestrator.py")
    .add_local_file("modal_app.py", remote_path="/app/modal_app.py")
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("linkedin-post-generator")],
    timeout=3600,
    scaledown_window=300,
    # Allow container to use enough memory for pandas + LLM payloads
    memory=2048,
)
@modal.concurrent(max_inputs=10)
@modal.asgi_app()
def web():
    """Serve the FastAPI application."""
    import os
    import sys

    # Set working directory to the project root inside the container
    os.chdir("/app")

    # Add /app to sys.path so Python can find server.py and other modules
    if "/app" not in sys.path:
        sys.path.insert(0, "/app")

    # Ensure execution/ is on the path (mirrors server.py behavior)
    exec_dir = os.path.join("/app", "execution")
    if exec_dir not in sys.path:
        sys.path.insert(0, exec_dir)

    # Ensure .agent/skills is importable (blotato_bridge.py needs it)
    skills_dir = os.path.join("/app", ".agents", "skills")
    if skills_dir not in sys.path:
        sys.path.insert(0, skills_dir)

    # Ensure .tmp directory exists BEFORE importing server.py
    # (server.py mounts .tmp as a StaticFiles directory at import time)
    os.makedirs("/app/.tmp", exist_ok=True)

    # Force UTF-8 for subprocesses
    os.environ["PYTHONIOENCODING"] = "utf-8"

    # Import the FastAPI app from server.py
    from server import app as fastapi_app

    return fastapi_app
