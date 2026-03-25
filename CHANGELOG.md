# Changelog

## [2.7.0] - 2026-03-08

### Security Hardening (Deep Audit Fixes)

#### HIGH — Critical Fixes
- **HIGH-1**: Added missing JWT auth (`get_verified_uid`) to 5 unprotected endpoints: `/api/save`, `/api/regenerate-caption`, `/api/draft`, `/api/blotato/accounts`, `/api/blotato/schedule`, `/api/blotato/quality-check`.
- **HIGH-2**: Removed `linkedin_tokens.json`, `linkedin_cookies.txt`, `.local_settings.json` from git tracking. Added all sensitive files to `.gitignore` (tokens, cookies, local settings/profiles/brands, `app.db`, `data.zip`, `credentials.json`).
- **HIGH-3**: Per-request RLS-aware Supabase client. Added thread-local context in `execution/supabase_client.py` (`set_request_token`/`clear_request_token`) and `_SupabaseRLSMiddleware` in `server.py`. When `SUPABASE_ANON_KEY` is configured, all DB queries from HTTP requests use the user's JWT so PostgreSQL RLS policies enforce data isolation. Background tasks fall back to service-role client.
- **HIGH-4**: Added 50MB upload size limit to `/api/upload-linkedin` to prevent ZIP bomb attacks.
- **HIGH-6**: Sanitized all subprocess arguments in `/api/regenerate-caption` (`req.topic`, `req.purpose`, `req.type`, `req.style`, `req.instructions`) with `_sanitize_arg()`.

#### MEDIUM — Error & Dependency Fixes
- **MED-2**: Wrapped all remaining raw `str(e)` error responses (~20 endpoints) with `_safe_error()` to prevent internal path/traceback leakage to clients.
- **DEP**: Migrated from deprecated `duckduckgo-search` to `ddgs>=9.0.0` in `requirements.txt`, `modal_app.py`, `execution/jina_search.py`, and `Web-Search-tool/web_search.py`.

### Previous Fixes (from earlier this session)
- **HIGH-5/HIGH-6**: Sanitized subprocess arguments in `/api/research/viral`, `/api/research/competitor`, `/api/research/youtube` with `_sanitize_arg()`.
- **BUG**: Fixed `NameError: name 'sanitize_untrusted_input' is not defined` in `execution/generate_assets.py`.

## [2.6.0] - 2026-03-07

### P0 Security & Infrastructure Hardening

#### Security Fixes
- **SEC-01**: Locked down `firestore.rules` — changed `allow read, write: if true` to `if false` (app uses Supabase now).
- **SEC-03**: Implemented JWT authentication on all 31 API endpoints via `get_verified_uid()` in `server.py`.
  - Verifies Supabase access tokens server-side using `client.auth.get_user(token)`.
  - 5-minute in-memory cache to avoid hammering the auth API.
  - Falls back to `X-User-ID` header ONLY when `AUTH_BYPASS=true` (local dev).
  - Admin endpoint now restricts self-purge only (returns 403 for cross-user purge).
- **SEC-05**: Replaced blanket `StaticFiles("/assets")` mount with authenticated endpoint.
  - Only serves image/PDF files (`.png`, `.jpg`, `.gif`, `.webp`, `.svg`, `.pdf`).
  - Blocks directory traversal and access to JSON/ZIP/CSV data files.
  - Requires valid JWT authentication.

#### Infrastructure
- **DEPLOY-01**: Added Supabase Storage integration for generated images.
  - New `upload_asset()` / `get_asset_public_url()` in `execution/supabase_client.py`.
  - Auto-creates `generated-assets` bucket (public, 10MB limit).
  - `_persist_asset_to_storage()` helper in `server.py` uploads images after generation.
  - Hooked into `/api/generate`, `/api/generate-stream`, and `/api/regenerate-image`.
  - Images now survive Modal container scale-downs; falls back to local URL if upload fails.

#### Frontend
- `frontend/auth.js`: Added fetch interceptor that auto-injects `Authorization: Bearer <token>` on all `/api/` requests.
- Token stored in `window.appAccessToken`, updated on auth state change and token refresh.
- Existing `X-User-ID` headers preserved for backward compatibility during transition.

#### Config

- `.env.example`: Added `AUTH_BYPASS=false` documentation.
- History endpoint (`GET /api/history`) no longer accepts `userId` query parameter (was a spoofing vector).

### P1 Fixes (High Severity)

#### Security

- **SEC-04**: Added CORS middleware — restricts origins to Modal deployment URL + localhost dev servers. Configurable via `CORS_ALLOWED_ORIGINS` env var.
- **SEC-06**: Admin purge endpoint restricted with `ADMIN_UIDS` env var whitelist. Non-admin users can only purge their own data.
- **SEC-02**: RLS policies already comprehensive in `supabase_setup.sql` — all 7 tables covered with `(SELECT auth.uid())::text = user_id` pattern.

#### Code Quality

- **BUG-01**: Eliminated ~60 lines of duplicated command-building logic in `/api/generate` — now calls shared `_build_orchestrator_command()`.
- **DEPLOY-02**: Replaced dead `netlify.toml` config with deprecation notice (app deploys on Modal).

#### Infrastructure

- **DEPLOY-03**: Added `/api/health` endpoint — checks Supabase connectivity + `.tmp` writability. Returns 200/503 with structured status.
- **DEPLOY-04**: Wrapped all blocking `subprocess.run()` calls in `asyncio.to_thread()` — `/api/generate`, `/api/regenerate-image`, `/api/regenerate-caption`, and all 3 research endpoints no longer block the FastAPI event loop.

#### UX

- **UX-01**: Added loading skeleton to main content panel during auth hydration. Swaps to real empty state once user session resolves.

### P2 Fixes (Medium Severity)

#### Security

- **SEC-07**: Persona skills/writing rules now use `textContent` instead of `innerHTML` — prevents XSS from malicious LinkedIn export data.
- **SEC-08**: Blotato API key masked in `GET /api/settings` response — only last 4 chars shown to frontend.

#### Code Quality

- **BUG-03**: `orchestrator.py` temp cleanup now scoped to known orchestrator files only (whitelist-based). No longer nukes per-user CRM caches, surveillance data, or generated images.
- **BUG-02**: Replaced last 2 bare `except:` clauses in `server.py` with proper typed catches and logging.
- **BUG-07**: Added `_sanitize_arg()` to strip leading `--` dashes from user input before passing to subprocess argparse.
- **BUG-08**: CRM auto-refresh reduced from 4s to 15s (`CRM_AUTO_REFRESH_MS` in `crm-hub.js`).

#### Infrastructure

- **DEPLOY-05**: Added in-memory per-user rate limiting. Generation endpoints: 10 req/min. Research endpoints: 5 req/min. Configurable via `RATE_LIMIT_RPM` env var. Returns 429 when exceeded.
- **DEPLOY-08**: Auto-recovery for profiles stuck in `processing` state for >30 minutes without a persona. `/api/persona` resets to `error` so users can retry.

#### Animations

- **ANIM-01**: Added `@media (prefers-reduced-motion: reduce)` to `style.css` — disables all animations/transitions for users with vestibular disorders (WCAG 2.1 AA).
- **ANIM-02**: Login particle canvas now stops `requestAnimationFrame` loop when overlay is hidden. Saves CPU/GPU after login.

#### UX

- **UX-02**: Added `_safe_error()` helper that strips Python tracebacks and internal file paths from user-facing error messages. Applied to `/api/generate`.

#### Deferred

- **UX-03** (responsive breakpoints) and **UX-05** (custom select accessibility) deferred — large UI tasks better suited for a dedicated frontend sprint.

### P3 Fixes (Low Severity)

#### Code Quality

- **BUG-04**: Migrated from deprecated `@app.on_event("startup")` to FastAPI `lifespan` context manager.
- **BUG-05**: Moved inline `import hashlib`, `import base64` to top-level imports in `server.py`. `execution.*` imports kept lazy to avoid circular deps.
- **BUG-06**: Replaced deprecated `req.dict()` with `req.model_dump()` (Pydantic v2).
- **BUG-09**: Capped login particle count at 150 (was unbounded on 4K displays → ~700 particles, O(n²) per frame).

#### Security

- **SEC-09**: Fixed `surveillance_scraper.py` — replaced dead `firestore_client` imports with `supabase_client`, fixed relative import path.

#### Infrastructure

- **DEPLOY-06**: Added `duckduckgo-search` to `requirements.txt` (was in `modal_app.py` only).
- **DEPLOY-07**: Added deprecation notice to `firebase.json`. `firestore.rules` already locked to deny-all from P0.

#### Animations

- **ANIM-03**: Removed dead `@keyframes shake` from `style.css` (only `stepperErrorShake` was referenced).
- **ANIM-05**: Extended staggered row animations from 5 to 16 rows in `design-system.css` for CRM table rendering.

#### UX

- **UX-04**: Confirmed all destructive actions (CRM delete, draft delete, publish) already have `confirm()` dialogs.
- **UX-06**: Theatrical "mad science" fake logs now render at 45% opacity + italic, distinguishing them from real system events.
- **UX-07**: Speech synthesis now opt-in via `localStorage.getItem('obsidian_speech_enabled')`. Default is off.

#### Responsive & Accessibility (previously deferred, now completed)

- **UX-03**: Full responsive breakpoints added to `style.css` — tablet sidebar overlay drawer (≤900px), mobile full-bleed (≤600px), hamburger toggle injected by `script.js`, scrim overlay, 44px touch targets, stacked form groups.
- **UX-05**: Custom select component rebuilt for WCAG 2.1 AA — `role="combobox"`, `aria-expanded`, `aria-haspopup`, `aria-activedescendant`, `role="listbox"`/`role="option"`, full keyboard navigation (ArrowUp/Down, Enter, Escape, Home/End, Tab), `.focused` outline state.
- **BUG-10**: CSS consolidation — discovered `design-system.css` is not loaded by `index.html` (orphaned). Migrated active `.glass-card` base styles into `style.css`. Marked `design-system.css` as reference-only with deprecation header.

## [2.5.1] - 2026-03-03

### CRM Hub Professionalization + Conversation-Aware Reply Drafting

#### Added
- CRM conversation thread caching helpers in `execution/supabase_client.py`:
  - `save_crm_conversation_thread(conversation_id, messages, uid)`
  - `get_crm_conversation_thread(conversation_id, uid)`
  - local cache file `.tmp/crm_threads_<uid>.json`
- New endpoint: `PUT /api/crm/contacts/{contact_id}/draft` for row-level draft persistence.

#### Changed
- `frontend/crm-hub.js` now renders CRM contacts as a professional Airtable/Baserow-style data table.
- CRM row actions now support:
  - conversation-aware message generation,
  - auto-saving generated message into contact draft,
  - draft editing/saving via modal per prospect row.
- `execution/message_generator.py` now:
  - defaults to `gemini-3-pro-preview`,
  - accepts full conversation messages,
  - injects full transcript into prompt for non-generic replies.
- `server.py` LinkedIn ingestion now saves conversation threads during CRM population and improves contact→connection matching to better populate title/company.
- `GET /api/crm/contacts` now returns a slimmer row payload plus `draft_message` and `draft_updated_at` fields for efficient table rendering.

#### Verification
- `python -m py_compile server.py execution\message_generator.py execution\supabase_client.py`
- `node -e "const fs=require('fs'); new Function(fs.readFileSync('frontend/crm-hub.js','utf8')); new Function(fs.readFileSync('frontend/voice-engine.js','utf8')); console.log('frontend_js_parse_ok');"`
- FastAPI `TestClient` smoke checks for:
  - `POST /api/crm/generate-message` (conversation-aware + draft auto-save),
  - `PUT /api/crm/contacts/{contact_id}/draft`,
  - `GET /api/crm/contacts` (row draft + populated role fields).

#### Files Changed
- `server.py`
- `execution/message_generator.py`
- `execution/supabase_client.py`
- `frontend/crm-hub.js`
- `frontend/style.css`
- `README.md`
- `ARCHITECTURE.md`

## [2.5.0] - 2026-03-03

### LinkedIn Ingestion + CRM Auto-Population

#### Added
- `execution/knowledge_extractor.py` for structured persona/brand/product extraction (JSON output).
- LinkedIn ZIP ingestion now stores structured knowledge chunks into `voice_chunks` with category metadata.
- Automatic CRM contact creation from `messages.csv` threads during ZIP processing.
- Persona endpoint now returns processing status + voice chunk/CRM counts.

#### Changed
- Voice Engine UI locks generation actions during ZIP processing and reloads after completion.
- LinkedIn ingestion now merges extracted product knowledge into `user_brands` and updates processing status.

#### Files Changed
- `server.py`
- `execution/knowledge_extractor.py`
- `execution/rag_manager.py`
- `frontend/voice-engine.js`
- `frontend/script.js`
- `frontend/style.css`
- `frontend/index.html`

## [2.4.0] - 2026-03-02

### Phase 4: Dynamic Persona + Brand Injection Runtime

#### Added
- Tenant-scoped generation context loader in `execution/generate_assets.py`:
  - pulls active user persona from `get_user_profile(uid)`
  - pulls active brand profile from `get_user_brand(uid)`
  - normalizes writing rules/skills/offerings for deterministic prompt injection
- Dynamic prompt sections:
  - `ACTIVE USER PERSONA (HIGHEST PRIORITY)` in system instruction stack
  - `ACTIVE USER BRAND PROFILE` in system instruction stack
  - runtime context block injected into user content payload for caption/image alignment
- New regression test file: `tests/test_generate_assets_user_context.py`

#### Changed
- `server.py` now forwards resolved auth UID to orchestrator for both:
  - `POST /api/generate`
  - `POST /api/generate-stream`
- `orchestrator.py` now accepts `--user_id` and forwards it to `execution/generate_assets.py`.
- `execution/generate_assets.py` now accepts `--user_id` CLI arg and `user_id` function parameter.
- `execution/generate_assets.py` UTF-8 stdio wrapping moved from import-time to CLI runtime (`_configure_utf8_stdio`) to avoid side effects during module import/testing.

#### Verification
- `python -m py_compile server.py orchestrator.py execution\generate_assets.py tests\test_generate_assets_user_context.py`
- `pytest -q tests\test_generate_assets_user_context.py`

#### Files Changed
- `server.py`
- `orchestrator.py`
- `execution/generate_assets.py`
- `tests/test_generate_assets_user_context.py`

## [2.3.1] - 2026-03-02

### Visual Generation

#### Changed
- Removed automatic logo compositing from `execution/generate_assets.py` image output flow.
- Removed logo compositing from `POST /api/regenerate-image` in both `tweak` and `refine` modes.
- Simplified image-generation LLM response contract by removing `logo_position` and `logo_variant` fields.

#### Result
- Generated and regenerated visuals are now returned as normal image outputs without post-processing logo overlays.

#### Documentation
- Updated `README.md`, `ARCHITECTURE.md`, `TROUBLESHOOTING.md`, and `IMPLEMENTATION.md` to reflect the no-logo visual pipeline.

#### Files Changed
- `execution/generate_assets.py`
- `server.py`
- `README.md`
- `ARCHITECTURE.md`
- `TROUBLESHOOTING.md`
- `IMPLEMENTATION.md`

## [2.3.0] - 2026-03-02

### Brand Assets + Dynamic Theming

#### Added
- Full extracted website palette support in Brand Assets (`extracted_colors`) and UI chip rendering.
- Full extracted website font list support (`extracted_fonts`) and UI chip rendering.
- `extraction_schema_version` compatibility guard to bypass legacy partial cache payloads.
- Complete UI token theming application from `ui_theme` via CSS variable injection.

#### Changed
- Firecrawl + Gemini theme flow now enforces strict core color locking (`brand_primary` and `border_focus` remain exact extracted primary).
- Manual core color edits (primary/secondary/accent) now regenerate synced `ui_theme` on Save & Apply.
- Added/updated cache-busting query params for frontend assets to avoid stale JS/CSS behavior after theme patches.

#### Fixed
- Cases where only 3 colors appeared in the Brand Assets section despite richer Firecrawl output.
- Cases where Save & Apply returned success but did not visibly re-theme all surfaces.
- Remaining hardcoded yellow/gold accents in hover/focus/active states across stepper, modal actions, filter pills, and CRM interactive elements.

#### Files Changed
- `execution/brand_extractor.py`
- `execution/supabase_client.py`
- `frontend/brand-assets.js`
- `frontend/index.html`
- `frontend/style.css`
- `frontend/script.js`
- `frontend/crm-hub.js`
- `README.md`
- `ARCHITECTURE.md`
- `TROUBLESHOOTING.md`
- `IMPLEMENTATION.md`

## [2.2.0] - 2026-02-28

### Drafts + Publishing

#### Added
- Drafts persistence (Supabase primary + local JSON fallback)
- Draft CRUD API endpoints:
  - `GET /api/drafts`
  - `POST /api/drafts`
  - `PUT /api/drafts/{draft_id}`
  - `DELETE /api/drafts/{draft_id}`
- Draft publishing via Blotato:
  - `POST /api/drafts/{draft_id}/publish`
  - `POST /api/blotato/test`

#### UI
- Drafts view under History with Draft Edit modal
- 3D “book flip” draft card design for the Drafts grid
- Settings modal in the main header for saving/testing Blotato API key

#### Fixed
- Settings icon not opening the modal (missing modal DOM element)

### Files Changed
- `supabase_setup.sql`
- `execution/supabase_client.py`
- `server.py`
- `execution/blotato_bridge.py`
- `frontend/index.html`
- `frontend/script.js`
- `frontend/style.css`
- `.env.example`
- `README.md`
- `ARCHITECTURE.md`
- `SUPABASE_SETUP.md`
- `TROUBLESHOOTING.md`

---

## [2.1.0] - 2026-02-28

### Cloud Deployment: Modal

#### Added
- **`modal_app.py`**: Full-stack serverless deployment config for [Modal](https://modal.com)
  - Packages FastAPI backend + static frontend into a single ASGI web endpoint
  - Container image: Debian Slim + Python 3.11 with all `requirements.txt` deps
  - Copies `frontend/`, `execution/`, `directives/`, `Web-Search-tool/`, `server.py`, `orchestrator.py` into `/app/`
  - Secrets injected from Modal's encrypted store (`linkedin-post-generator`)
  - Scale-to-zero with 300s idle scaledown, 600s request timeout, 10 concurrent inputs
- **Modal workspace**: `tahir-70872` authenticated and linked
- **Modal secret**: `linkedin-post-generator` created from `.env` with all API keys

#### Deployment Details
- **Live URL**: `https://tahir-70872--linkedin-post-generator-web.modal.run`
- **Deploy command**: `$env:PYTHONIOENCODING="utf-8"; modal deploy modal_app.py`
- **Dev mode**: `$env:PYTHONIOENCODING="utf-8"; modal serve modal_app.py`
- **Logs**: `$env:PYTHONIOENCODING="utf-8"; modal app logs linkedin-post-generator`

#### Bug Fixes During Deployment
- Fixed `ModuleNotFoundError: No module named 'server'` — added `/app` to `sys.path` in `modal_app.py` before importing `server.py`
- Fixed `RuntimeError` from missing `.tmp/` directory — `server.py` mounts `.tmp` as `StaticFiles` at import time; now created before import
- Fixed Windows `charmap` encoding error during deploy — requires `$env:PYTHONIOENCODING="utf-8"` prefix
- Updated deprecated Modal parameters: `allow_concurrent_inputs` → `@modal.concurrent`, `container_idle_timeout` → `scaledown_window`

#### Documentation Updates
- Updated `README.md` with Modal deployment section (Option B), deployment architecture diagram, env vars reference
- Updated `ARCHITECTURE.md` with Modal deployment layer, deployment commands, key constraints, updated file structure
- Updated `CHANGELOG.md` with this entry
- Updated `TROUBLESHOOTING.md` with Modal-specific issues section

### Files Changed
- `modal_app.py` — New file
- `README.md` — Added Modal deployment section
- `ARCHITECTURE.md` — Added Modal deployment section, updated file structure
- `CHANGELOG.md` — Added v2.1.0 entry
- `TROUBLESHOOTING.md` — Added Modal deployment issues

---

## [2.0.0] - 2026-02-28

### Major Changes

#### Database Migration: Firebase → Supabase
- **Removed**: All Firebase dependencies (firebase-admin, firestore_client.py, Firebase Auth)
- **Added**: Supabase PostgreSQL backend with service role authentication
- **Created**: `execution/supabase_client.py` - drop-in replacement for firestore_client.py
- **Created**: `supabase_setup.sql` - table definitions for history and user_settings
- **Updated**: Frontend auth to use Supabase Auth with Google OAuth
- **Updated**: All API endpoints to use `X-User-ID` header (backwards compatible with `X-Firebase-UID`)

#### Performance Optimizations
- **jina_search.py**: Switched from deep page scraping to snippet-only mode (10-30s faster)
- **orchestrator.py**: Skip `rank_and_analyze.py` subprocess for topic-only searches (5-10s faster)
- **rank_and_analyze.py**: Fast-path static analysis when no viral/competitor data exists
- **Total speedup**: 15-35 seconds for typical "Direct Topic + Image" generation

#### Bug Fixes
- **CRITICAL**: Fixed missing `response_modalities=["TEXT", "IMAGE"]` in Gemini image generation API calls
- **CRITICAL**: Fixed infinite recursion in `regenerate_image.py` (dead code referencing `args` inside function)
- **CRITICAL**: Fixed `cost_tracker` import error in server tweak mode (added execution/ to sys.path)
- Fixed server response key mismatch: `image_prompt` → `final_image_prompt`
- Fixed regenerate caption - results panel now re-shows after update
- Fixed auth.js variable shadowing: `const supabase` → `const sbClient`

#### User Isolation Fixes
- Fixed `/api/generate` to use `_save_history_entry` (was bypassing Supabase)
- Fixed `/api/history` to check `X-User-ID` header in addition to query param
- Fixed `loadSettings()` to defer until auth is ready (was loading "default" user data)
- Removed shared-file fallbacks from surveillance and leads endpoints (data leak)
- All local files now use user-specific paths: `.tmp/history_{uid}.json`, `.tmp/surveillance_data_{uid}.json`

#### UI Improvements
- Widened repurpose modal from 560px to 740px
- Added proper scrolling and overflow handling to all modals
- Added visual context badge styling
- Fixed source content textarea max-height to prevent cutoff

### Files Changed
- `frontend/auth.js` - Complete rewrite for Supabase
- `frontend/index.html` - Firebase SDK → Supabase CDN
- `frontend/script.js` - All headers updated to X-User-ID
- `frontend/style.css` - Modal width and scroll improvements
- `server.py` - All firestore_client → supabase_client, isolation fixes
- `execution/supabase_client.py` - New file
- `execution/generate_assets.py` - Fixed response_modalities
- `execution/regenerate_image.py` - Fixed response_modalities + infinite recursion
- `execution/jina_search.py` - Performance optimization
- `execution/rank_and_analyze.py` - Performance optimization
- `orchestrator.py` - Performance optimization
- `.env` - Firebase → Supabase config
- `requirements.txt` - firebase-admin → supabase

### Files Created
- `supabase_setup.sql` - Database schema
- `SUPABASE_SETUP.md` - Setup guide
- `CHANGELOG.md` - This file

### Migration Notes
- Firebase files (.firebaserc, firebase.json, firestore.rules) can be deleted
- Old `execution/firestore_client.py` can be deleted
- Run `supabase_setup.sql` in Supabase SQL Editor before first use
- Enable Google Auth provider in Supabase Dashboard
