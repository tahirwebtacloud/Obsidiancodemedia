# Comprehensive Web Application Audit Report

**Project:** LinkedIn Post Generator v1.1  
**Date:** 2025-07-21  
**Auditor:** Senior Web Designer / UX-UI Engineer / Animator / Security Analyst  
**Scope:** Every file and folder — Security, Code Quality, Animation/Interaction, UX/Design, Deployment/Infrastructure

---

## Summary Scorecard

| Dimension                        | Score | Grade | Critical Issues |
|----------------------------------|-------|-------|-----------------|
| **Security Vulnerabilities**     | 38/100 | F    | 8               |
| **Code Quality & Bugs**         | 62/100 | C    | 5               |
| **Animation & Interaction**     | 74/100 | B-   | 2               |
| **UX & Design**                 | 68/100 | C+   | 4               |
| **Deployment & Infrastructure** | 45/100 | D    | 6               |
| **Overall**                     | **57/100** | **D+** | **25**     |

---

## Dimension 1: Security Vulnerabilities

### SEC-01 — Firestore Rules Allow Unrestricted Read/Write (CRITICAL)

- **File:** `firestore.rules:4-6`
- **Severity:** 🔴 CRITICAL
- **Description:** Rules grant `allow read, write: if true;` on ALL documents. Any unauthenticated user can read/write/delete any data in the entire Firestore database.
- **Fix:**
```
match /{document=**} {
  allow read, write: if request.auth != null && request.auth.uid == resource.data.user_id;
}
```
Or remove the Firestore config entirely since the app now uses Supabase.

---

### SEC-02 — Supabase Anon Key Hardcoded in Frontend (HIGH)

- **File:** `frontend/auth.js:5-6`
- **Severity:** 🟠 HIGH
- **Description:** `SUPABASE_URL` and `SUPABASE_ANON_KEY` are hardcoded as string literals in client-side JavaScript. While anon keys are designed for public use, the URL+key pair is committed to Git and visible in source. If RLS policies are misconfigured, this key grants broad data access.
- **Fix:** This is acceptable IF Supabase RLS is properly enforced on every table. However, several tables (`history`, `user_settings`, `user_brands`) in `supabase_setup.sql` do NOT have `ENABLE ROW LEVEL SECURITY` or any policies defined. Add RLS to ALL tables immediately.

---

### SEC-03 — Service Role Key Used Server-Side Without Request Auth Validation (CRITICAL)

- **File:** `execution/supabase_client.py:44`, `server.py` (all endpoints)
- **Severity:** 🔴 CRITICAL
- **Description:** The backend uses `SUPABASE_SERVICE_ROLE_KEY` (bypasses RLS) for ALL database operations. User identity comes solely from the `X-User-ID` header, which is trivially spoofable. Any client can set `X-User-ID: <victim_uid>` and access/modify/delete another user's data (history, drafts, CRM contacts, brand assets, persona, settings).
- **Fix:** Validate the JWT from Supabase Auth on every API request. Extract `user_id` from the verified token, not from a client-supplied header. Add FastAPI middleware:
```python
from jose import jwt
async def get_current_user(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
    return payload["sub"]
```

---

### SEC-04 — No CORS Configuration (HIGH)

- **File:** `server.py` (entire file)
- **Severity:** 🟠 HIGH
- **Description:** FastAPI app has no CORS middleware configured. When deployed to Modal, any origin can make API calls. This enables CSRF-style attacks where a malicious site can make authenticated requests on behalf of a logged-in user.
- **Fix:** Add CORSMiddleware restricting to known origins:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["https://your-domain.modal.run"], ...)
```

---

### SEC-05 — .tmp Directory Served Publicly Without Access Control (HIGH)

- **File:** `server.py:77`
- **Severity:** 🟠 HIGH
- **Description:** `app.mount("/assets", StaticFiles(directory=".tmp"))` serves the entire `.tmp` directory. This exposes ALL temp files: user-uploaded LinkedIn ZIPs, brand palettes, source content, generated images, cost data, history JSON, CRM contact data, and surveillance data. Any user can enumerate and download other users' files by guessing filenames (which follow predictable patterns like `leads_data_{uid}.json`).
- **Fix:** Add authentication middleware to the `/assets` route, or serve generated images through an authenticated endpoint that validates ownership.

---

### SEC-06 — Admin Endpoint Has Weak Auth Check (HIGH)

- **File:** `server.py:1801-1838`
- **Severity:** 🟠 HIGH
- **Description:** `DELETE /api/admin/user-data/{uid}` only checks `caller_uid == "default"` for 401. Any authenticated user (with any UID) can purge ANY other user's data by calling this endpoint with a target UID. No admin role validation exists.
- **Fix:** Implement admin role checking — either via Supabase custom claims or a hardcoded admin UID list.

---

### SEC-07 — XSS Risk in voice-engine.js Persona Rendering (MEDIUM)

- **File:** `frontend/voice-engine.js:295-303`
- **Severity:** 🟡 MEDIUM
- **Description:** `personaSkills.innerHTML` and `personaWritingStyle.innerHTML` inject persona data directly into HTML without escaping. If a malicious LinkedIn export contains XSS payloads in skill names or writing rules, they will execute.
- **Fix:** Use `textContent` or escape HTML before inserting:
```javascript
personaSkills.innerHTML = persona.core_skills.map(skill =>
    `<span>...</span>${escapeHtml(skill)}</span>`
).join('');
```

---

### SEC-08 — Blotato API Key Stored in User Settings (MEDIUM)

- **File:** `server.py:999` (`SettingsUpdateRequest`)
- **Severity:** 🟡 MEDIUM
- **Description:** The `blotatoApiKey` field is accepted from the frontend and stored in Supabase `user_settings` as plaintext JSON. Combined with SEC-03 (spoofable X-User-ID), any attacker can read another user's Blotato API key.
- **Fix:** Encrypt sensitive settings at rest, or store API keys server-side only (never expose via GET /api/settings).

---

### SEC-09 — surveillance_scraper.py Imports from Deprecated Module (LOW)

- **File:** `execution/surveillance_scraper.py:15-23`
- **Severity:** 🟢 LOW
- **Description:** Imports `get_setting` and `_read_local_settings` from `firestore_client`, which is the deprecated module. This may fail silently and fall through to `.env`, but indicates dead code paths.
- **Fix:** Update imports to use `supabase_client` module.

---

## Dimension 2: Code Quality & Bugs

### BUG-01 — Massive Code Duplication in server.py (HIGH)

- **File:** `server.py:205-292` vs `server.py:293-344`
- **Severity:** 🟠 HIGH
- **Description:** The `/api/generate` endpoint and `_build_orchestrator_command()` contain nearly identical 140-line blocks for building the orchestrator command, handling source_content temp files, reference images, and visual context. Any bug fix in one must be manually replicated in the other.
- **Fix:** Delete the duplicated logic from `/api/generate` and call `_build_orchestrator_command()` instead.

---

### BUG-02 — Bare `except:` Clauses Swallow Errors (MEDIUM)

- **File:** `server.py:660`, `server.py:679`, `execution/supabase_client.py` (multiple), `execution/rag_manager.py:55`
- **Severity:** 🟡 MEDIUM
- **Description:** At least 15 bare `except:` or `except Exception:` blocks silently swallow errors with only `pass`. This makes debugging production issues nearly impossible. Examples:
  - `server.py:660` — `except:` when parsing JSON output from caption regeneration
  - `server.py:679` — `except:` when clearing cost files
  - `supabase_client.py` — numerous `except Exception: pass` blocks
- **Fix:** Log all caught exceptions with `traceback.format_exc()` at minimum.

---

### BUG-03 — orchestrator.py Clears .tmp on Every Run (MEDIUM)

- **File:** `orchestrator.py:12-36`
- **Severity:** 🟡 MEDIUM
- **Description:** `clear_temp_directory()` deletes all files in `.tmp` except `generated_image_*.png` on every orchestrator run. This destroys per-user surveillance data, CRM thread caches, lead scan results, connection caches, and draft local files for ALL users. If two users generate content simultaneously, one will lose their cached data.
- **Fix:** Scope temp cleanup to only orchestrator-specific files (e.g., `analysis.json`, `final_plan.json`, `viral_trends.json`), not the entire directory.

---

### BUG-04 — Deprecated `@app.on_event("startup")` Usage (LOW)

- **File:** `server.py:79`
- **Severity:** 🟢 LOW
- **Description:** FastAPI has deprecated `on_event` in favor of lifespan context managers. This will emit deprecation warnings.
- **Fix:** Migrate to FastAPI lifespan:
```python
from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup code
    yield
app = FastAPI(lifespan=lifespan)
```

---

### BUG-05 — `import base64` Inside Function Body (LOW)

- **File:** `server.py:235`, `server.py:317`, `server.py:609`
- **Severity:** 🟢 LOW
- **Description:** `import base64`, `import time`, `import uuid` are imported inside function bodies instead of at the top of the file. While Python caches imports, this is poor style and can confuse IDE tooling.
- **Fix:** Move all imports to the top of the file.

---

### BUG-06 — `req.dict()` Deprecated in Pydantic v2 (LOW)

- **File:** `server.py:384`
- **Severity:** 🟢 LOW
- **Description:** `req.dict()` is deprecated in Pydantic v2. Should use `req.model_dump()`.
- **Fix:** Replace `req.dict()` with `req.model_dump()`.

---

### BUG-07 — Subprocess Command Injection Risk (MEDIUM)

- **File:** `server.py:212-264` (command building)
- **Severity:** 🟡 MEDIUM
- **Description:** User-supplied values (topic, URL, style, etc.) are passed directly into subprocess command arrays. While `subprocess.run(list)` avoids shell injection, malicious `--` prefixed values could be interpreted as flags by the child scripts (argparse). For example, `topic="--help"` could trigger help output instead of generation.
- **Fix:** Validate and sanitize all user inputs before passing to subprocess. Reject topics/URLs containing `--` prefixes.

---

### BUG-08 — CRM Auto-Refresh at 4s Interval is Aggressive (MEDIUM)

- **File:** `frontend/crm-hub.js:27`
- **Severity:** 🟡 MEDIUM
- **Description:** `CRM_AUTO_REFRESH_MS = 4000` means the CRM tab polls `/api/crm/contacts` every 4 seconds during LinkedIn processing. With 1000+ contacts, this fetches the full contact list every 4s, creating significant load on Supabase and the backend.
- **Fix:** Increase to 15-30 seconds, or implement delta-only responses (return count + changed contacts).

---

### BUG-09 — login.js Particle System Has O(n²) Complexity (LOW)

- **File:** `frontend/login.js:119-137`
- **Severity:** 🟢 LOW
- **Description:** The `connect()` function iterates all particle pairs (O(n²)). On large screens, particle count = `(width*height)/12000`, which on a 4K display = ~700 particles → ~245,000 distance calculations per frame at 60fps.
- **Fix:** Use spatial hashing or limit connections to nearest neighbors. Or cap particle count at 200.

---

### BUG-10 — Multiple CSS Files Define Conflicting `:root` Variables (LOW)

- **File:** `frontend/style.css` vs `frontend/design-system.css`
- **Severity:** 🟢 LOW
- **Description:** Both `style.css` and `design-system.css` define `:root` CSS variables with the same names but potentially different values. Load order determines which wins. `design-system.css` appears to be a comprehensive but partially unused design system.
- **Fix:** Consolidate into a single source of truth. Remove `design-system.css` if unused, or import it as the base and override in `style.css`.

---

## Dimension 3: Animation & Interaction Quality

### ANIM-01 — No `prefers-reduced-motion` Support (MEDIUM)

- **File:** `frontend/style.css`, `frontend/design-system.css`, `frontend/login.css`
- **Severity:** 🟡 MEDIUM
- **Description:** Neither CSS file respects `prefers-reduced-motion`. Users with vestibular disorders or motion sensitivity will experience the full suite of animations: pulse, shimmer, shake, bounce, fadeIn, slideIn, and the particle background. This is a WCAG 2.1 Level AA violation.
- **Fix:** Add at end of each CSS file:
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

### ANIM-02 — Particle Canvas Runs Even When Login Is Hidden (MEDIUM)

- **File:** `frontend/login.js:139-146`
- **Severity:** 🟡 MEDIUM
- **Description:** The `animate()` loop runs via `requestAnimationFrame` indefinitely, even after login succeeds and the overlay is hidden (`display:none`). This wastes CPU/GPU cycles on every frame.
- **Fix:** Stop the animation loop when login overlay is hidden:
```javascript
function animate() {
    if (canvas.offsetParent === null) return; // not visible
    requestAnimationFrame(animate);
    // ... rest
}
```

---

### ANIM-03 — CSS `animation: shake` Has No Practical Trigger (LOW)

- **File:** `frontend/style.css` (shake keyframe defined)
- **Severity:** 🟢 LOW
- **Description:** The `shake` animation keyframe is defined but never applied to any element in HTML or JS. Dead animation code.
- **Fix:** Remove or wire up to validation error states.

---

### ANIM-04 — Toast slideIn Animation Direction Mismatch (LOW)

- **File:** `frontend/design-system.css:597`
- **Severity:** 🟢 LOW
- **Description:** Toast `.toast` uses `animation: slideIn` which slides from right (`translateX(100%)`), but the toast container is positioned `top-right`. The slide-in direction is correct but the `fadeOut` animation also translates right, which will look like the toast slides out the same way it came in — acceptable but not ideal. A slide-up or fade-up exit would feel more polished.
- **Fix:** Change fadeOut to `translateY(-20px)` for a more natural exit.

---

### ANIM-05 — Staggered Table Row Animations Limited to 5 Rows (LOW)

- **File:** `frontend/design-system.css:979-983`
- **Severity:** 🟢 LOW
- **Description:** Only 5 stagger delays are defined (`.data-table tr:nth-child(1-5)`). Rows 6+ all animate simultaneously, creating a jarring "batch appear" effect after the first 5 rows stagger in smoothly.
- **Fix:** Use CSS custom properties or JS to dynamically set animation delays, or extend to 20+ rows.

---

## Dimension 4: UX & Design Weaknesses

### UX-01 — No Loading Skeleton or Spinner for Initial Page Load (HIGH)

- **File:** `frontend/index.html`, `frontend/script.js`
- **Severity:** 🟠 HIGH
- **Description:** After login, the app content appears all at once with no skeleton states. The design system defines `.skeleton` and `.loading-spinner` classes in `design-system.css`, but they are NEVER used in `index.html` or `script.js`. On slow connections or cold Modal starts (5-15s), users see a blank white screen.
- **Fix:** Add skeleton placeholders in `index.html` for the sidebar, form, and output console that are shown until JS initializes.

---

### UX-02 — Error Messages Show Raw Technical Details (MEDIUM)

- **File:** `server.py` (all error responses), `frontend/script.js`
- **Severity:** 🟡 MEDIUM
- **Description:** Error responses include raw Python tracebacks, stderr output, and internal file paths. Example from `server.py:275`: `"stderr": process.stderr[-2000:]`. These are shown directly to users via `alert()` calls in the frontend.
- **Fix:** Return user-friendly error messages. Log technical details server-side only:
```python
return JSONResponse(status_code=500, content={"error": "Content generation failed. Please try again."})
```

---

### UX-03 — Mobile Responsiveness Is Incomplete (MEDIUM)

- **File:** `frontend/style.css`, `frontend/index.html`
- **Severity:** 🟡 MEDIUM
- **Description:** `style.css` has only one `@media (max-width: 768px)` breakpoint. The sidebar (400px fixed width) has no mobile collapse behavior defined in `style.css`. The CRM table (10 columns) will overflow horizontally on tablets. The login page handles mobile well, but the main app does not.
- **Fix:** Add responsive breakpoints: sidebar collapse to hamburger at <1024px, CRM table horizontal scroll wrapper, stack form elements vertically on mobile.

---

### UX-04 — No Confirmation Before Destructive Actions (MEDIUM)

- **File:** `frontend/crm-hub.js:442` (only CRM delete has confirm)
- **Severity:** 🟡 MEDIUM
- **Description:** CRM contact deletion has a `confirm()` dialog, but other destructive actions lack confirmation:
  - Drafts deletion (no confirm)
  - Brand asset reset (no confirm)
  - Re-importing LinkedIn data (overwrites existing persona, no confirm)
  - Admin user data purge (no frontend for this, but the API has no confirm)
- **Fix:** Add confirmation dialogs for all destructive operations.

---

### UX-05 — Custom Select Dropdown Accessibility Issues (MEDIUM)

- **File:** `frontend/script.js` (CustomSelect class)
- **Severity:** 🟡 MEDIUM
- **Description:** The `CustomSelect` component replaces native `<select>` elements with custom divs. These lack:
  - `role="listbox"` and `role="option"` ARIA attributes
  - Keyboard navigation (arrow keys, Enter, Escape)
  - Screen reader announcements for selected value changes
  - Focus management when opened/closed
- **Fix:** Add ARIA attributes and keyboard event handlers per WAI-ARIA Listbox pattern.

---

### UX-06 — System Log "Mad Scientist" Fake Logs May Confuse Users (LOW)

- **File:** `frontend/script.js` (madScienceInterval)
- **Severity:** 🟢 LOW
- **Description:** The "Mad Scientist Fake Log Stream" generates random fake system messages like "Injecting prompt sequences..." during generation. While entertaining, these can confuse users into thinking real processes are running, making debugging difficult when actual errors occur in the same log panel.
- **Fix:** Visually distinguish fake logs (e.g., dimmer color, italic) or add a toggle to disable them.

---

### UX-07 — Speech Synthesis Error Alert is Alarming (LOW)

- **File:** `frontend/script.js` (addSystemLog speech synthesis)
- **Severity:** 🟢 LOW
- **Description:** On error, the app speaks "Error. Error." in a low-pitch robotic voice. This can startle users, especially in quiet environments or with headphones.
- **Fix:** Make speech synthesis opt-in via settings, not on by default.

---

## Dimension 5: Deployment & Infrastructure Risks

### DEPLOY-01 — Modal Container Uses Ephemeral Filesystem for Persistent Data (CRITICAL)

- **File:** `modal_app.py`, `server.py`
- **Severity:** 🔴 CRITICAL
- **Description:** Modal containers have ephemeral filesystems. ALL local file operations (`.tmp/`, `.local_profiles.json`, `.local_settings.json`, `.local_brands.json`, history JSON files, CRM thread caches, connection caches) are lost on every container restart/scale-down. This means:
  - Generated images disappear after 5 minutes of inactivity
  - Local fallback data is permanently lost
  - LinkedIn connection caches (used for CRM title backfill) vanish
  - In-progress background tasks (LinkedIn import) will be killed on scale-down
- **Fix:** 
  1. Use Supabase Storage for generated images (not local `.tmp/`)
  2. Ensure ALL data operations go through Supabase, not local files
  3. Use Modal Volumes for persistent `.tmp/` if local files are necessary
  4. Set `scaledown_window` to at least 600s (currently 300s) for long-running LinkedIn imports

---

### DEPLOY-02 — Netlify Config Points to Wrong Architecture (HIGH)

- **File:** `netlify.toml`
- **Severity:** 🟠 HIGH
- **Description:** `netlify.toml` configures redirects to `/.netlify/functions/server/:splat`, but the app is a FastAPI monolith, not a Netlify Functions architecture. The `functions = "execution"` setting would attempt to deploy ALL execution scripts as Netlify Functions, which would fail. The app is deployed on Modal, making this config misleading and potentially dangerous if someone deploys to Netlify.
- **Fix:** Either remove `netlify.toml` (since Modal is the deployment target) or update it to proxy to the Modal backend URL.

---

### DEPLOY-03 — No Health Check Endpoint for Monitoring (HIGH)

- **File:** `server.py`
- **Severity:** 🟠 HIGH  
- **Description:** There is `/api/health/models` that returns model config, but no simple `/health` or `/api/health` endpoint that checks actual service health (Supabase connectivity, API key validity, disk space). Modal and external monitors need a lightweight health check.
- **Fix:** Add:
```python
@app.get("/api/health")
async def health():
    try:
        _get_client()  # test Supabase
        return {"status": "ok"}
    except:
        return JSONResponse(status_code=503, content={"status": "unhealthy"})
```

---

### DEPLOY-04 — Blocking subprocess.run() in Async Endpoints (HIGH)

- **File:** `server.py:272` (`/api/generate`), `server.py:587`, `server.py:648`, `server.py:694`, `server.py:721`, `server.py:755`
- **Severity:** 🟠 HIGH
- **Description:** Multiple async endpoints use `subprocess.run()` which blocks the entire event loop. With `@modal.concurrent(max_inputs=10)`, this means 10 concurrent generation requests will each block a thread, and the 11th request will hang indefinitely. The SSE endpoint (`/api/generate-stream`) correctly uses `subprocess.Popen` with `asyncio.to_thread`, but all other endpoints block.
- **Fix:** Wrap all `subprocess.run()` calls in `asyncio.to_thread()` or use `asyncio.create_subprocess_exec()`.

---

### DEPLOY-05 — No Rate Limiting on Any Endpoint (MEDIUM)

- **File:** `server.py` (all endpoints)
- **Severity:** 🟡 MEDIUM
- **Description:** No rate limiting exists on any endpoint. A malicious user could:
  - Spam `/api/generate` to exhaust Gemini API quota
  - Spam `/api/research/viral` to exhaust Apify credits
  - Spam `/api/crm/generate-message` to exhaust LLM quota
  - DDoS the server with requests to any endpoint
- **Fix:** Add `slowapi` or custom rate limiting middleware:
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
```

---

### DEPLOY-06 — requirements.txt Missing `duckduckgo-search` (LOW)

- **File:** `requirements.txt` vs `modal_app.py:45`
- **Severity:** 🟢 LOW
- **Description:** `modal_app.py` installs `duckduckgo-search>=6.0.0` but `requirements.txt` does not include it. Local development won't have this dependency.
- **Fix:** Add `duckduckgo-search>=6.0.0` to `requirements.txt`.

---

### DEPLOY-07 — Firebase Config Still Present Despite Supabase Migration (LOW)

- **File:** `firebase.json`, `firestore.rules`, `firestore.indexes.json`, `.firebaserc`
- **Severity:** 🟢 LOW
- **Description:** The app has fully migrated to Supabase, but Firebase/Firestore config files remain. The `firestore.rules` with `allow read, write: if true` is especially dangerous if someone accidentally deploys to Firebase.
- **Fix:** Remove all Firebase config files, or add a README note that they are deprecated.

---

### DEPLOY-08 — Background Tasks Lost on Modal Scale-Down (MEDIUM)

- **File:** `server.py:1691` (LinkedIn processing), `server.py:1063` (lead scan), `server.py:1104` (surveillance refresh)
- **Severity:** 🟡 MEDIUM
- **Description:** Long-running background tasks (LinkedIn import can take 1-2 hours for large networks) are run via FastAPI `BackgroundTasks`. On Modal, if the container scales down due to inactivity timeout (300s), these tasks are killed mid-execution, leaving user data in a `processing` state permanently.
- **Fix:** Use Modal's `spawn()` for long-running tasks, or implement a job queue with status recovery.

---

## Prioritized Remediation Checklist

### 🔴 P0 — Fix Immediately (Security Critical)

| # | Issue | File(s) | Effort |
|---|-------|---------|--------|
| 1 | SEC-01: Remove or lock down `firestore.rules` | `firestore.rules` | 5 min |
| 2 | SEC-03: Implement JWT auth validation on all endpoints | `server.py` | 4 hrs |
| 3 | SEC-05: Remove public `.tmp` serving or add auth | `server.py:77` | 2 hrs |
| 4 | DEPLOY-01: Migrate generated images to Supabase Storage | `server.py`, `execution/generate_assets.py` | 8 hrs |

### 🟠 P1 — Fix This Week (High Severity)

| # | Issue | File(s) | Effort |
|---|-------|---------|--------|
| 5 | SEC-04: Add CORS middleware | `server.py` | 30 min |
| 6 | SEC-06: Restrict admin endpoint to admin role | `server.py:1801` | 1 hr |
| 7 | SEC-02: Add RLS to ALL Supabase tables | `supabase_setup.sql` | 2 hrs |
| 8 | BUG-01: Deduplicate command building in server.py | `server.py` | 1 hr |
| 9 | DEPLOY-04: Make subprocess calls non-blocking | `server.py` | 3 hrs |
| 10 | DEPLOY-02: Remove or fix netlify.toml | `netlify.toml` | 15 min |
| 11 | DEPLOY-03: Add proper health check endpoint | `server.py` | 30 min |
| 12 | UX-01: Add loading skeletons for initial load | `frontend/index.html` | 2 hrs |

### 🟡 P2 — Fix This Sprint (Medium Severity) ✅ ALL COMPLETE

| # | Issue | File(s) | Status |
|---|-------|---------|--------|
| 13 | BUG-03: Scope orchestrator temp cleanup | `orchestrator.py` | ✅ Done |
| 14 | BUG-02: Replace bare except clauses with logging | Multiple files | ✅ Done |
| 15 | BUG-07: Validate subprocess inputs | `server.py` | ✅ Done |
| 16 | BUG-08: Reduce CRM auto-refresh frequency | `frontend/crm-hub.js` | ✅ Done |
| 17 | ANIM-01: Add prefers-reduced-motion | CSS files | ✅ Done |
| 18 | ANIM-02: Stop particle animation when hidden | `frontend/login.js` | ✅ Done |
| 19 | UX-02: Sanitize error messages shown to users | `server.py` | ✅ Done |
| 20 | UX-03: Add responsive breakpoints for tablet/mobile | `frontend/style.css`, `script.js` | ✅ Done |
| 21 | UX-05: Fix custom select accessibility | `frontend/script.js`, `style.css` | ✅ Done |
| 22 | DEPLOY-05: Add rate limiting | `server.py` | ✅ Done |
| 23 | DEPLOY-08: Handle background task recovery | `server.py` | ✅ Done |
| 24 | SEC-07: Escape persona HTML injection | `frontend/voice-engine.js` | ✅ Done |
| 25 | SEC-08: Encrypt sensitive settings | `server.py` | ✅ Done |

### 🟢 P3 — Fix When Convenient (Low Severity) ✅ ALL COMPLETE

| # | Issue | File(s) | Status |
|---|-------|---------|--------|
| 26 | BUG-04: Migrate to FastAPI lifespan | `server.py` | ✅ Done |
| 27 | BUG-05: Move inline imports to top of file | `server.py` | ✅ Done |
| 28 | BUG-06: Replace req.dict() with model_dump() | `server.py` | ✅ Done |
| 29 | BUG-09: Optimize particle system | `frontend/login.js` | ✅ Done |
| 30 | BUG-10: Consolidate CSS design systems | CSS files | ✅ Done |
| 31 | SEC-09: Fix surveillance_scraper imports | `execution/surveillance_scraper.py` | ✅ Done |
| 32 | DEPLOY-06: Sync requirements.txt with modal_app.py | `requirements.txt` | ✅ Done |
| 33 | DEPLOY-07: Remove deprecated Firebase configs | Root directory | ✅ Done |
| 34 | ANIM-03: Remove dead shake animation | `frontend/style.css` | ✅ Done |
| 35 | ANIM-05: Extend staggered row animations | `frontend/design-system.css` | ✅ Done |
| 36 | UX-04: Add confirm dialogs for destructive actions | Multiple frontend files | ✅ Already present |
| 37 | UX-06: Distinguish fake logs visually | `frontend/script.js` | ✅ Done |
| 38 | UX-07: Make speech synthesis opt-in | `frontend/script.js` | ✅ Done |

---

## Files Audited

### Frontend (14 files)
- `frontend/index.html` — Main app layout, login forms, tabs, UI panels
- `frontend/auth.js` — Supabase auth logic, OAuth flows
- `frontend/script.js` — Core UI logic, SSE, form handling, custom selects
- `frontend/style.css` — Primary stylesheet with brand colors, animations
- `frontend/design-system.css` — Comprehensive design token system (partially unused)
- `frontend/login.css` — Login page styling with glassmorphism
- `frontend/login.js` — Login panel toggle, particle background canvas
- `frontend/brand-assets.js` — Brand extraction, live preview, saving
- `frontend/crm-hub.js` — CRM data table, filtering, drafts, auto-refresh
- `frontend/voice-engine.js` — LinkedIn ZIP upload, persona display, voice search
- `frontend/favicon.png` — App icon (binary, no issues)
- `frontend/logo.png` — App logo (binary, no issues)
- `frontend/index.html.backup` — Backup file (should not be in production)
- `frontend/style.css.backup` — Backup file (should not be in production)

### Backend (2 files)
- `server.py` — FastAPI server (2199 lines), all API endpoints
- `orchestrator.py` — CLI orchestration pipeline (277 lines)

### Execution Scripts (42+ files)
- `execution/supabase_client.py` — Supabase data layer (970 lines)
- `execution/generate_assets.py` — Core content generation (1092 lines)
- `execution/brand_extractor.py` — Brand extraction via Firecrawl + Gemini (639 lines)
- `execution/message_analyzer.py` — CRM message classification (733 lines)
- `execution/message_generator.py` — Outreach message generation
- `execution/rag_manager.py` — Vector RAG with pgvector (475 lines)
- `execution/blotato_bridge.py` — LinkedIn publishing bridge (179 lines)
- `execution/linkedin_parser.py` — LinkedIn ZIP parser (441 lines)
- `execution/surveillance_scraper.py` — Profile monitoring (178 lines)
- `execution/cost_tracker.py` — Run cost tracking (102 lines)
- `execution/lead_scraper.py` — Comment/reaction lead scoring (379 lines)
- `execution/viral_research_apify.py` — Apify research (large file)
- `execution/generate_carousel.py` — Carousel generation
- `execution/regenerate_image.py` — Image refinement
- `execution/regenerate_caption.py` — Caption regeneration
- `execution/baserow_logger.py` — Baserow CRM logging
- `execution/linkedin_profile_scraper.py` — Apify profile enrichment
- `execution/persona_builder.py` — Persona construction
- `execution/knowledge_extractor.py` — Structured knowledge extraction
- `execution/jina_search.py` — Jina web search
- `execution/local_youtube.py` — Local yt-dlp fallback
- `execution/apify_youtube.py` — Apify YouTube scraping
- `execution/ingest_source.py` — URL content ingestion
- `execution/rank_and_analyze.py` — Trend analysis
- `execution/placid_client.py` — Placid API (deactivated)
- `execution/firestore_client.py` — Deprecated Firestore client
- `execution/db_schema.py` — Database schema definitions
- `execution/dm_automation.py` — DM draft automation
- Various test files (`test_*.py`, `check_fields.py`, `find_actors.py`)
- Data files (`*.json`, `*.html`) — Test/debug artifacts

### Deployment & Config (10 files)
- `modal_app.py` — Modal deployment definition
- `netlify.toml` — Netlify config (deprecated/incorrect)
- `firebase.json` — Firebase config (deprecated)
- `firestore.rules` — CRITICAL security issue
- `firestore.indexes.json` — Firebase indexes (deprecated)
- `.firebaserc` — Firebase project config (deprecated)
- `supabase_setup.sql` — Supabase schema + RLS policies
- `requirements.txt` — Python dependencies
- `.env.example` — Environment variable template
- `.gitignore` — Git ignore rules

### Other Directories
- `directives/` — SOP markdown files (18+ files) — No code issues, content quality is good
- `tests/` — 4 test files — Low coverage, only tests DB schema and placid
- `docs/plans/` — 7 planning documents — Well-structured project roadmap
- `.agent/` — Skills and rules — Audit context files, no issues
- `LinkedIn guidelines/` — Reference materials — No code issues
- `Outside_of_this_workspace/` — External tools — Not part of main app
- `Interactive Sign Up & Sign In/` — Standalone demo — Not deployed
- `Interactive Glaas nav/` — Standalone demo — Not deployed
- `Web-Search-tool/` — Utility script — No critical issues

---

## Positive Findings

The audit also identified several strong points worth noting:

1. **Robust local fallback system** — `supabase_client.py` gracefully falls back to local JSON files when Supabase is unreachable, ensuring the app works offline.
2. **Well-structured SSE streaming** — The `/api/generate-stream` endpoint correctly uses `subprocess.Popen` with `asyncio.to_thread` for non-blocking streaming.
3. **Good HTML escaping in CRM** — `crm-hub.js` uses a proper `escapeHtml()` function for all dynamic content rendering.
4. **Smart polling strategy in voice-engine.js** — Fast poll (2min at 2s) → slow poll (20min at 10s) → lazy poll (30s) is a well-designed pattern that respects server resources.
5. **Comprehensive design system** — `design-system.css` provides a complete, consistent token system with proper accessibility focus styles.
6. **Good cost tracking** — `cost_tracker.py` provides transparent API cost tracking per run.
7. **Visibility-aware polling** — Both `crm-hub.js` and `voice-engine.js` pause polling when the tab is hidden.
8. **Brand color escaping** — `brand-assets.js` uses `_escAttr()` for HTML attribute escaping.

---

*End of Audit Report*
