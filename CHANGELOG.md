# Changelog

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
