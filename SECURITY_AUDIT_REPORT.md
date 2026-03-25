# SECURITY AUDIT REPORT — LinkedIn Post Generator v1.1

**Date:** 2026-03-08 (Revision 3 — Deep Penetration Audit)  
**Auditor:** Automated Deep Audit (Cascade)  
**Scope:** Full workspace — every file, every endpoint, every data flow (~200+ files, 2420-line server.py, 1058-line supabase_client.py)  
**Deployment Target:** Modal (multi-tenant cloud, scale-to-zero, 10 concurrent)  
**Risk Context:** Multi-tenant SaaS on Modal; can user data be leaked, damaged, or destroyed?

---

## EXECUTIVE SUMMARY

**Overall Risk Rating: MODERATE-HIGH — Deep audit reveals systemic issues beneath the surface**

The Rev 2 audit found 3 HIGH / 7 MEDIUM / 6 LOW issues. This Rev 3 deep-dive goes endpoint-by-endpoint, line-by-line, and reveals **7 HIGH**, **12 MEDIUM**, and **9 LOW** severity findings — including several new categories not previously identified.

### What's solid (confirmed working):
- ✅ **JWT authentication** via `get_verified_uid()` with 5-min token cache and Supabase verification
- ✅ **Firestore rules** locked (`allow read, write: if false`) — migration to Supabase complete
- ✅ **CORS middleware** with env-configurable origins + sensible defaults
- ✅ **Rate limiting** (10 RPM generation, 5 RPM research, in-memory per-user)
- ✅ **Asset serving** auth-gated with `os.path.abspath()` path traversal prevention + file-type whitelist
- ✅ **Error sanitization** via `_safe_error()` on generation endpoints
- ✅ **Admin endpoint** requires `ADMIN_UIDS` or self-delete
- ✅ **API key masking** in health and settings endpoints
- ✅ **Prompt injection defense** via `prompt_security.py` sanitizer
- ✅ **Startup cleanup** purges stale user profiles on boot

### What's broken (new findings from deep audit):

| Severity | Count | Status |
|----------|-------|--------|
| **CRITICAL** | 0 | All resolved ✅ |
| **HIGH** | 7 | Require fixes before production hardening |
| **MEDIUM** | 12 | Should fix for defense-in-depth |
| **LOW** | 9 | Hardening and cleanup opportunities |

---

## APPENDIX A: COMPLETE ENDPOINT AUTH MATRIX (40+ Endpoints)

Every endpoint in `server.py` audited for authentication, rate limiting, and input validation:

| Endpoint | Auth | Rate Limit | Input Sanitized | Error Handling | Line |
|----------|------|------------|-----------------|----------------|------|
| `GET /favicon.ico` | None (static) | - | - | - | 67 |
| `GET /api/health` | None (public) | - | - | Safe | 72 |
| `GET /api/health/models` | None (public) | - | - | Key masked ✅ | 107 |
| `GET /assets/{path}` | ✅ JWT | - | Path traversal guard ✅ | Safe | 200 |
| `POST /api/generate` | ✅ JWT | ✅ 10 RPM | `_sanitize_arg()` on most fields | `_safe_error()` ✅ | 348 |
| `POST /api/generate-stream` | ✅ JWT | ✅ 10 RPM | `_sanitize_arg()` on most fields | `_safe_error()` ✅ | 576 |
| **`POST /api/save`** | **❌ NONE** | **❌ NONE** | **❌ No validation** | **Raw `str(e)`** | **655** |
| `POST /api/regenerate-image` | ✅ JWT | - | Partial (base64 unsanitized) | Raw `str(e)` | 705 |
| **`POST /api/regenerate-caption`** | **❌ NONE** | **❌ NONE** | **❌ User input to subprocess** | **Raw `str(e)` + raw stderr** | **820** |
| `GET /api/history` | ✅ JWT | - | - | Implicit | 852 |
| `POST /api/research/viral` | ✅ JWT | ✅ 5 RPM | `_sanitize_arg()` ✅ | History logged | 874 |
| `POST /api/research/competitor` | ✅ JWT | ✅ 5 RPM | URLs not sanitized ⚠️ | History logged | 901 |
| `POST /api/research/youtube` | ✅ JWT | ✅ 5 RPM | URLs not sanitized ⚠️ | History logged | 932 |
| **`POST /api/draft`** | **❌ NONE** | **❌ NONE** | **source_text → LLM prompt directly** | **Raw `str(e)`** | **977** |
| `GET /api/drafts` | ✅ JWT | - | - | Implicit | 1047 |
| `POST /api/drafts` | ✅ JWT | - | Pydantic validates | Safe | 1055 |
| `PUT /api/drafts/{id}` | ✅ JWT | - | Allowlisted fields only ✅ | Safe | 1080 |
| `DELETE /api/drafts/{id}` | ✅ JWT | - | - | Safe | 1092 |
| `POST /api/drafts/{id}/publish` | ✅ JWT | - | Draft looked up by uid ✅ | Raw `str(e)` | 1109 |
| `GET /api/blotato/accounts` | **❌ NONE** | - | - | Raw `str(e)` | 1160 |
| `GET /api/blotato/schedule` | **❌ NONE** | - | - | Raw `str(e)` | 1171 |
| `POST /api/blotato/quality-check` | **❌ NONE** | - | caption → quality gate | Raw `str(e)` | 1184 |
| `GET /api/settings` | ✅ JWT | - | - | Key masked ✅ | 1199 |
| `POST /api/settings` | ✅ JWT | - | Pydantic validates | Safe | 1218 |
| `POST /api/run-lead-scan` | ✅ JWT | - | URLs unvalidated ⚠️ | Background task | 1242 |
| `GET /api/leads/data` | ✅ JWT | - | - | Safe | 1267 |
| `GET /api/surveillance/data` | ✅ JWT | - | - | Safe | 1282 |
| `POST /api/surveillance/refresh` | ✅ JWT | - | `uid` passed to subprocess unsanitized ⚠️ | Background task | 1297 |
| `POST /api/preview-brand` | ✅ JWT | - | **URL → SSRF risk** ⚠️ | Raw `str(e)` | 1318 |
| `POST /api/save-brand` | ✅ JWT | - | `validate_brand_assets()` ✅ | Safe | 1338 |
| `GET /api/brand` | ✅ JWT | - | - | Safe | 1365 |
| `POST /api/upload-linkedin` | ✅ JWT | - | **No file size limit** ⚠️ | Safe | 1402 |
| `POST /api/search-voice` | ✅ JWT | - | Topic → RAG query | Safe | 1908 |
| `GET /api/persona` | ✅ JWT | - | - | Raw `str(e)` | 1929 |
| `DELETE /api/admin/user-data/{uid}` | ✅ JWT + Admin | - | UID path param ✅ | Raw `str(e)` | 2019 |
| `POST /api/crm/analyze` | ✅ JWT | - | Messages → LLM | Raw `str(e)` | 2082 |
| `POST /api/crm/generate-message` | ✅ JWT | - | Contact → LLM prompt | Raw `str(e)` | 2121 |
| `PUT /api/crm/contacts/{id}/draft` | ✅ JWT | - | Draft text → Supabase | Raw `str(e)` | 2206 |
| `GET /api/crm/contacts` | ✅ JWT | - | Query params | Raw `str(e)` | 2230 |
| `POST /api/crm/backfill-titles` | ✅ JWT | - | - | Raw `str(e)` | 2295 |
| `DELETE /api/crm/contacts/{id}` | ✅ JWT | - | - | Raw `str(e)` | 2394 |

---

## HIGH SEVERITY FINDINGS

### HIGH-1: Missing Authentication on 6 Endpoints

**File:** `server.py`

Six endpoints do **not** call `get_verified_uid(request)`:

| Endpoint | Line | Impact |
|----------|------|--------|
| `POST /api/save` | 655 | Unauthenticated writes to Baserow |
| `POST /api/regenerate-caption` | 820 | Burns Gemini tokens, returns generated content |
| `POST /api/draft` | 977 | Burns Gemini tokens, returns generated content |
| `GET /api/blotato/accounts` | 1160 | Leaks connected LinkedIn account info |
| `GET /api/blotato/schedule` | 1171 | Leaks scheduling data |
| `POST /api/blotato/quality-check` | 1184 | Free quality scoring for any caller |

**Fix:** Add `uid = get_verified_uid(request)` and `request: Request` parameter to each.

---

### HIGH-2: Sensitive Files Tracked in Git

**Files in repo that contain credentials or PII:**

| File | Contains | In .gitignore? |
|------|----------|----------------|
| `linkedin_tokens.json` | OAuth access_token, id_token JWT (name, email, sub) | ❌ NO |
| `linkedin_cookies.txt` | LinkedIn session cookies (`li_at`, `JSESSIONID`) | ❌ NO |
| `.local_profiles.json` | User UUIDs, LinkedIn URLs, professional bios, personas | ❌ NO |
| `.local_settings.json` | User UUIDs, tracked profile URLs, Blotato keys | ❌ NO |
| `.local_brands.json` | User brand details, logo URLs, color schemes | ❌ NO |
| `data.zip` | Full LinkedIn data export (messages, connections, PII) | ❌ NO |
| `execution/app.db` | SQLite database with user data | ❌ NO |
| `execution/apimaestro_out.json` | API scrape output | ❌ NO |

**Impact:** Anyone with repo access can extract real LinkedIn session tokens, OAuth tokens, and user PII. PII persists in git history even after deletion.

**Fix:**

1. **Immediately revoke** LinkedIn tokens at `https://www.linkedin.com/psettings/permitted-services`
2. **Log out all sessions** and change LinkedIn password
3. Add all files to `.gitignore`
4. Scrub git history with `git filter-branch` or `BFG Repo-Cleaner`

---

### HIGH-3: Supabase Service Role Key Bypasses All RLS

**Files:** `execution/supabase_client.py:44`, `execution/rag_manager.py`

The singleton Supabase client uses `SUPABASE_SERVICE_ROLE_KEY` (line 44) which bypasses all 7 tables' RLS policies. Every `get_crm_contacts()`, `add_crm_contact()`, `get_user_history()` call operates as a superuser.

**Attack scenario:** If any endpoint has a logic bug where `uid` is wrong (e.g., from cache corruption, or the 3 unauth endpoints where uid is from request body), the attacker reads/writes ANY user's data with no database-level guard.

**Fix:** Create per-request clients using `create_client(url, anon_key)` + set the user's JWT via `client.auth.set_session()`. Reserve service role for admin/startup only.

---

### HIGH-4: ZIP Bomb / Decompression Bomb in LinkedIn Upload

**File:** `execution/linkedin_parser.py:105`, `server.py:1420`

The LinkedIn ZIP upload pipeline has **zero** protections against ZIP bombs:

1. **No file size limit** on upload (`server.py:1420` — `content = await file.read()`)
2. **No decompressed size limit** (`linkedin_parser.py:105` — `zipfile.ZipFile(io.BytesIO(zip_file_bytes))`)
3. **No entry count limit** — every CSV is parsed into a Pandas DataFrame in memory
4. **No path traversal check on ZIP entries** — `_find_file()` only matches filenames by suffix but doesn't validate that extracted paths stay within expected directories

A 1MB ZIP can decompress to 1GB+ (classic ZIP bomb), crashing the Modal container.

**Fix:**

```python
# Before parsing:
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
if len(zip_file_bytes) > MAX_UPLOAD_SIZE:
    return {"status": "error", "message": "File too large"}

# Inside validate_and_parse_zip:
total_uncompressed = sum(info.file_size for info in z.infolist())
if total_uncompressed > 500 * 1024 * 1024:  # 500MB
    return {"status": "error", "message": "Decompressed size too large"}
if len(z.infolist()) > 1000:
    return {"status": "error", "message": "Too many entries in ZIP"}
```

---

### HIGH-5: Subprocess Command Injection via `uid` Parameter

**File:** `server.py:1303`

The surveillance refresh endpoint passes `uid` directly to subprocess without `_sanitize_arg()`:

```python
subprocess.run(["python", "execution/surveillance_scraper.py", "--days", str(days), "--uid", uid], env=RUN_ENV)
```

While `uid` normally comes from JWT verification (safe UUID), if `AUTH_BYPASS=true` the uid comes from `X-User-ID` header — which is arbitrary user input. A crafted header like `X-User-ID: --help` or `X-User-ID: ; rm -rf /` (in a shell context) could cause issues.

**Mitigating factor:** `subprocess.run` with a list (not string) avoids shell injection. But argparse injection via `--` prefixed UIDs is still possible.

**Fix:** Apply `_sanitize_arg()` to all uid values passed to subprocess, or validate UID format (UUID regex).

---

### HIGH-6: Unsanitized `req.instructions` in Subprocess Call

**File:** `server.py:826-827`

The `/api/regenerate-caption` endpoint passes `req.instructions` directly to subprocess:

```python
if req.instructions:
    command.extend(["--instructions", req.instructions])
```

This endpoint has **no authentication** (HIGH-1), AND `req.instructions` is **not sanitized** with `_sanitize_arg()`. An attacker can inject argparse flags.

**Fix:** Add auth + apply `_sanitize_arg(req.instructions)`.

---

### HIGH-7: Hardcoded Supabase Anon Key in Frontend Source

**File:** `frontend/auth.js:3-4`

```javascript
const SUPABASE_URL = 'https://bsaggewiyjaikkkbvgpr.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIs...';
```

The Supabase anon key is committed in plaintext. While anon keys are **designed** to be public (they only have RLS-scoped access), this is still a concern because:

1. The project URL + key together allow anyone to call Supabase Auth endpoints (sign up accounts, password resets)
2. If RLS policies are misconfigured, the anon key grants read access to user data
3. The key in source code prevents key rotation without a code deploy

**Mitigating factor:** Supabase anon keys are intended to be client-facing. RLS policies in `supabase_setup.sql` are properly scoped to `auth.uid()`.

**Fix:** Consider loading from environment/config. Ensure email confirmation is required for signups. Monitor Supabase Auth for abuse.

---

## MEDIUM SEVERITY FINDINGS

### MED-1: SSRF Risk in Brand Extractor

**File:** `server.py:1318`, `execution/brand_extractor.py`

`/api/preview-brand` accepts any URL → forwards to Firecrawl API. No URL validation.

```
POST /api/preview-brand {"url": "http://169.254.169.254/latest/meta-data/"}
```

**Fix:** Validate `https://` scheme only. Reject private/reserved IP ranges. Add URL allowlist or blocklist.

---

### MED-2: Raw Error Messages Leak Stack Traces (21 Endpoints)

**File:** `server.py` — grep shows 21 endpoints return `str(e)` directly

Every endpoint listed in the auth matrix with "Raw `str(e)`" exposes internal error details including: file paths, database connection strings, Python stack information, and Supabase API errors.

**Fix:** Create a wrapper: `def _api_error(e, status=500): return JSONResponse(status_code=status, content={"error": "Internal error"})` and log the real error server-side.

---

### MED-3: Concurrent `.tmp/final_plan.json` Race Condition

**Files:** `orchestrator.py:29-49`, `server.py:367`

With `@modal.concurrent(max_inputs=10)`, concurrent generation requests share the same `.tmp/final_plan.json` path. User A's results can be overwritten by User B before server.py reads them.

**Fix:** Use per-request filenames: `.tmp/final_plan_{uuid}.json`.

---

### MED-4: No File Upload Size Limit (DoS Vector)

**File:** `server.py:1420`

`content = await file.read()` reads entire upload into memory. Combined with ZIP bomb risk (HIGH-4), this is a denial-of-service vector.

**Fix:** Add `Content-Length` check or streaming read with size cap at 100MB.

---

### MED-5: URL Bypass in `_sanitize_arg`

**File:** `server.py:441`

`req.url` explicitly skips `_sanitize_arg()` because "URLs may legitimately start with `-`". A crafted URL could inject argparse flags into child scripts.

**Fix:** Validate URL format (must start with `http://` or `https://`) before passing to subprocess.

---

### MED-6: Rate Limiting In-Memory Only — Resets on Container Restart

**File:** `server.py:401-426`

`_rate_buckets` dict resets when Modal containers scale to zero (300s idle). With 10 concurrent containers, rate limits don't synchronize.

**Fix:** Accept for current scale, or use Redis/Supabase for persistent rate state.

---

### MED-7: Dead Code — 6 Files Should Be Removed

- `execution/firestore_client.py` (258 lines) — replaced by `supabase_client.py`
- `execution/db_schema.py` (45 lines) — SQLAlchemy ORM, never used
- `execution/duck.py` (7 lines) — one-off HTML parser
- `execution/research_competitors.py` (53 lines) — returns mock data only
- `execution/identify_viral.py` — returns mock data only
- `execution/ingest_source.py` — returns mock data only

---

### MED-8: LinkedIn Token File Written to Project Root Without Encryption

**File:** `execution/linkedin_utils.py:80-81`

```python
def save_tokens(token_data):
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=4)
```

OAuth tokens (access_token, refresh_token, id_token containing name+email) are saved as plaintext JSON in the project root. The file is not in `.gitignore` and gets committed.

**Fix:** Store tokens in Supabase or use OS keyring. At minimum, add to `.gitignore` and encrypt at rest.

---

### MED-9: `.tmp/` Files Shared Across Users on Modal

**Files:** Multiple scripts write to shared `.tmp/` paths

Some files use per-user naming (good): `.tmp/leads_data_{uid}.json`, `.tmp/surveillance_data_{uid}.json`

But others use global names: `.tmp/manual_save.json` (line 660), `.tmp/youtube_research.json` (line 960), `.tmp/brand_cache.json`

On Modal with 10 concurrent containers, two users' requests on the same container would collide.

**Fix:** Add `_{uid}` or `_{uuid}` suffix to all `.tmp/` file paths.

---

### MED-10: Pydantic Models Lack Input Constraints

**File:** `server.py` — all `BaseModel` classes

No field-level validation beyond types:

- `GenerateRequest.topic` — no max length (could send 1MB topic)
- `GenerateRequest.source_content` — no max length (injected into LLM prompt)
- `DraftRequest.source_text` — minimum 10 chars but no maximum
- `RegenerateCaptionRequest.instructions` — no max length, no sanitization
- `CRMDraftUpdateRequest.draft_message` — no max length

**Fix:** Add `Field(max_length=...)` constraints to all user-facing string fields.

---

### MED-11: `_startup_cleanup` Uses `list_users()` Admin API

**File:** `server.py:240`

```python
_auth_users = _client.auth.admin.list_users()
```

This uses the service role key to list ALL Supabase Auth users on every startup. At scale (thousands of users), this becomes slow and is an unnecessary admin API call.

**Fix:** Use a more targeted approach — only check UIDs present in local files, not enumerate all users.

---

### MED-12: Dependency Supply Chain — Loose Version Pinning

**File:** `requirements.txt`

Several dependencies use open upper bounds or no upper bound:

```
google-genai>=0.8.0       # No upper bound — breaking changes possible
apify-client>=1.7.0       # No upper bound
yt-dlp>=2024.8.6          # No upper bound
supabase>=2.0.0           # No upper bound
duckduckgo-search>=6.0.0  # No upper bound
```

**Fix:** Pin exact versions or use `~=` compatible release operator. Generate a `requirements.lock` file.

---

## LOW SEVERITY FINDINGS

### LOW-1: innerHTML XSS Surface — 102 Instances Across 5 Files

**Files:** `script.js` (76), `brand-assets.js` (11), `auth.js` (6), `voice-engine.js` (6), `crm-hub.js` (3)

**Highest-risk instances (user/scraped data interpolated into HTML):**

1. **`script.js:1268`** — Surveillance card renders scraped post data (tier, engagement, content) via innerHTML
2. **`script.js:1417`** — YouTube card renders `authorName` from scraped data
3. **`script.js:1507`** — Video player uses `item.video_url` as `src` attribute
4. **`script.js:241`** — System log renders subprocess output via innerHTML
5. **`crm-hub.js:187`** — CRM table renders `contact.full_name`, `contact.company`, `contact.position`
6. **`auth.js:184`** — User display renders `photoURL` from Google OAuth metadata as `img src`
7. **`brand-assets.js:172`** — Color palette renders hex values from Firecrawl API

**Mitigating factor:** `crm-hub.js` has an `escapeHtml()` function used in the draft modal (line 339), but it's not applied consistently across all contact fields.

**Fix:** Use `textContent` for all user-supplied strings. Add DOMPurify for rich content. Apply `escapeHtml()` consistently.

---

### LOW-2: No Content Security Policy (CSP) Headers

External scripts loaded without SRI from `@latest` CDN tags.

**Fix:** Pin CDN versions. Add SRI hashes. Add CSP middleware in server.py.

---

### LOW-3: Bare `except: pass` Silences Errors

At least 15 instances across `server.py`, `orchestrator.py`, `regenerate_caption.py`, `firestore_client.py`, `linkedin_parser.py:388`.

**Fix:** Log exceptions before `pass`.

---

### LOW-4: `AUTH_BYPASS` No Startup Warning

**Fix:** Add `print("WARNING: AUTH_BYPASS enabled")` at startup.

---

### LOW-5: Debug Print Statements Leak Data in Production Logs

UIDs, file paths, API key prefixes, command arguments all printed. Modal centralizes these logs.

**Fix:** Structured logging with configurable levels. Mask UIDs.

---

### LOW-6: API Key Suffix Still Computed (Unused)

**File:** `server.py:111` — `api_key[-6:]` computed but not returned.

**Fix:** Remove the computation.

---

### LOW-7: `linkedin_utils.py` Contains Full LinkedIn API Integration (Unused)

**File:** `execution/linkedin_utils.py` — 490 lines of LinkedIn REST API calls

This file contains direct LinkedIn API posting (text, image, carousel, poll, event, article) using OAuth tokens from `linkedin_tokens.json`. None of these functions are called from `server.py` — publishing goes through Blotato. But the file reads plaintext tokens from disk.

**Fix:** Remove if Blotato is the publishing path. If kept, migrate token storage to Supabase.

---

### LOW-8: `_verified_uid_cache` Unbounded Growth Potential

**File:** `server.py:137`

The JWT verification cache prunes only when size exceeds 500 entries. Under sustained load with many unique tokens, memory grows. Each entry is small (~100 bytes), so 500 entries is only ~50KB — acceptable.

**Fix:** No immediate action needed. Monitor if user base grows past thousands.

---

### LOW-9: Supabase Storage Bucket Created as Public

**File:** `execution/supabase_client.py:992`

```python
client.storage.create_bucket(_STORAGE_BUCKET, options={"public": True, ...})
```

The `generated-assets` bucket is public, meaning anyone with the URL can access uploaded images without authentication. This is intentional for sharing generated images, but means all generated assets for all users are publicly accessible if URLs are guessed.

**Fix:** Consider private bucket with signed URLs for sensitive content. Current approach is acceptable for generated LinkedIn images.

---

## APPENDIX B: SUPABASE RLS ANALYSIS

**Tables with RLS enabled (7/7):** history, user_settings, user_brands, user_profiles, voice_chunks, crm_contacts, drafts ✅

**Policy pattern (all tables):** `(SELECT auth.uid())::text = user_id` — optimized for PostgreSQL planner ✅

**BUT:** All backend calls use `SUPABASE_SERVICE_ROLE_KEY` which **bypasses RLS entirely**. The RLS policies only protect against:
- Direct Supabase client access from the browser using the anon key
- Any future migration to client-side Supabase calls

**Data isolation actually depends on:** Backend code correctly passing `uid` from `get_verified_uid()` through to every Supabase query's `.eq("user_id", uid)` filter. This works correctly for all current endpoints — verified by tracing every data access path.

---

## APPENDIX C: SUBPROCESS COMMAND INJECTION TRACE

Every `subprocess.run` / `subprocess.Popen` call traced from user input to execution:

| Endpoint | Script Called | User Input | Sanitized? | Risk |
|----------|-------------|------------|------------|------|
| `/api/generate` | `orchestrator.py` | topic, source, url, type, purpose, style, aspect_ratio | `_sanitize_arg()` on most; URL skipped | **MED** |
| `/api/generate-stream` | `orchestrator.py` | Same as above | Same | **MED** |
| `/api/save` | `baserow_logger.py` | `req.post_data` (via temp file) | Written to JSON file, not CLI args | **LOW** |
| `/api/regenerate-image` | `regenerate_image.py` | caption, style, instructions | `_sanitize_arg()` ✅ | **LOW** |
| `/api/regenerate-caption` | `regenerate_caption.py` | topic, purpose, type, style, instructions | **NOT sanitized** + **no auth** | **HIGH** |
| `/api/research/viral` | `viral_research_apify.py` | topic | `_sanitize_arg()` ✅ | **LOW** |
| `/api/research/competitor` | `viral_research_apify.py` | urls (comma-joined) | URLs not sanitized | **MED** |
| `/api/research/youtube` | `local_youtube.py` | urls (comma-joined) | URLs not sanitized | **MED** |
| `/api/surveillance/refresh` | `surveillance_scraper.py` | days, uid | days clamped; uid not sanitized | **MED** |

---

## FILES THAT SHOULD BE ADDED TO `.gitignore`

```gitignore
# LinkedIn credentials (CRITICAL — revoke immediately)
linkedin_tokens.json
linkedin_cookies.txt

# User data / PII
.local_profiles.json
.local_settings.json
.local_brands.json
data.zip
Outside_of_this_workspace/raw.zip

# Database files
*.db

# Test/debug output
execution/apimaestro_out.json
execution/test_lead_scan_result.json
execution/freshdata_out.json
execution/*.html

# Archives
*.zip
```

---

## RECOMMENDED FIX PRIORITY

### Phase 1 — Immediate (Before Next Deploy) — ~2 hours

1. **Revoke and rotate** LinkedIn tokens and cookies, scrub git history (HIGH-2)
2. **Add auth** to 6 unauthenticated endpoints (HIGH-1)
3. **Add `.gitignore` entries** for all sensitive files (HIGH-2)
4. **Sanitize `req.instructions`** in `/api/regenerate-caption` (HIGH-6)
5. **Add ZIP upload size limit** (100MB upload, 500MB decompressed) (HIGH-4, MED-4)

### Phase 2 — Before Production Hardening — ~1 day

6. **Add SSRF protections** to brand preview URL validation (MED-1)
7. **Wrap all error responses** through `_safe_error()` or generic message (MED-2)
8. **Validate URL format** before subprocess calls (MED-5)
9. **Fix `.tmp/` race conditions** with per-request/per-user filenames (MED-3, MED-9)
10. **Add `Field(max_length=...)` to Pydantic models** (MED-10)
11. **Pin dependency versions** in requirements.txt (MED-12)

### Phase 3 — Defense in Depth — ~2-3 days

12. **Per-request Supabase clients** with user JWTs (HIGH-3)
13. **Remove dead code** (MED-7)
14. **Migrate linkedin token storage** to Supabase or remove (MED-8, LOW-7)
15. **Add CSP headers and pin CDN versions** (LOW-2)
16. **Replace innerHTML** with safe alternatives where user data is interpolated (LOW-1)
17. **Add AUTH_BYPASS runtime warning** (LOW-4)
18. **Migrate to structured logging** (LOW-5)

---

## ARCHITECTURE SECURITY POSTURE

| Layer | Status | Notes |
|-------|--------|-------|
| **Authentication** | ✅ Solid | JWT verified via Supabase, cached 5min. 6 endpoints still missing auth. |
| **Authorization** | ⚠️ Weak | Auth checks identity but DB uses service role (bypasses RLS). No RBAC. |
| **Input Validation** | ⚠️ Partial | Pydantic validates types; `_sanitize_arg` on most subprocess args; URLs and instructions not validated; no max_length on string fields |
| **Output Sanitization** | ⚠️ Partial | `_safe_error()` on 2 endpoints; 21+ endpoints return raw `str(e)` |
| **CORS** | ✅ Solid | Env-configurable, defaults to Modal URL + localhost |
| **Rate Limiting** | ✅ Adequate | In-memory, 10/5 RPM. Resets on container restart. |
| **Secrets Management** | ❌ Poor | `.env` gitignored but linkedin_tokens.json, .local_*.json committed with PII |
| **Data Isolation** | ⚠️ Partial | Per-user files for CRM/leads/surveillance. Shared paths for orchestrator/save/youtube. |
| **Upload Security** | ❌ Poor | No file size limit. No ZIP bomb protection. No decompressed size check. |
| **Frontend Security** | ⚠️ Partial | 102 innerHTML usages. Supabase anon key in source (expected). No CSP. |
| **Dependency Security** | ⚠️ Partial | No lock file. Loose version pinning. CDN scripts use `@latest`. |
| **Container Security** | ✅ Adequate | Modal containers are ephemeral. `.tmp` shared within container but isolated across containers. |

---

## SUMMARY

This Rev 3 deep audit traced every endpoint, every subprocess call, every data flow, and every file write in the system. The codebase has strong authentication foundations but reveals **systemic gaps in input validation, error handling, and file processing** that the surface-level Rev 2 audit missed.

**The five most impactful fixes are:**

1. **Add auth to 6 unauthenticated endpoints** (HIGH-1) — ~30 min
2. **Scrub sensitive files from git** (HIGH-2) — ~30 min
3. **Add ZIP bomb protections** (HIGH-4) — ~20 min
4. **Sanitize subprocess arguments on unauth endpoints** (HIGH-6) — ~15 min
5. **Wrap all error responses** (MED-2) — ~45 min

**Estimated total effort to reach production-hardened state:** 3-4 days of focused work across all 3 phases.

---

*Report generated from full audit of 200+ files across all directories. All execution/*.py, server.py, orchestrator.py, modal_app.py, frontend/*.js, config files, directives/, docs/, and tests/ reviewed line-by-line.*
