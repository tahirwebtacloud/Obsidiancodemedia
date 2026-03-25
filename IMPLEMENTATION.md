# IMPLEMENTATION.md
## LinkedIn Post Generator - Branding & CRM System
### Master Tracking Document

**Created:** 2026-03-01
**Architecture Decisions:**
- Database: Supabase (PostgreSQL + RLS)
- Auth: Supabase Auth (email/password + Google)
- Brand Extraction: Hybrid (client preview → server storage)
- ZIP Processing: Modal background worker
- Vector DB: Supabase pgvector
- Content Generation: Dual-Engine (parallel web + RAG)
- Frontend: Vanilla JS with CSS custom properties
- Live Preview: CSS custom properties
- Visual Rendering: No post-generation logo compositing in image generation/regeneration

**Status Legend:**
- `[ ]` - Not started
- `[-]` - In progress
- `[x]` - Completed
- `[~]` - Blocked/Issue

---

## PHASE 1: Brand Assets Foundation

### Database & Auth Setup
- [ ] **1.1** Initialize Supabase project with PostgreSQL
  - Dependencies: None
  - Output: Project URL, anon key, service role key
  - Notes:

- [ ] **1.2** Configure RLS policies for `user_profiles` table
  - Dependencies: 1.1
  - Output: RLS enabled, policies active
  - Notes:

- [ ] **1.3** Set up Supabase Auth with email/password + Google provider
  - Dependencies: 1.1
  - Output: Auth configured, OAuth credentials set
  - Notes:

- [ ] **1.4** Add `user_id` foreign key relationships to existing tables
  - Dependencies: 1.1
  - Output: Schema updated with FK constraints
  - Notes:

- [ ] **1.5** Create migration script from current SQLite (`app.db`) to Supabase
  - Dependencies: 1.4
  - Output: `migration_sqlite_to_supabase.py`
  - Notes:

### Backend - Brand Extraction
- [x] **1.6** Create `execution/brand_extractor.py` with Firecrawl integration
  - Dependencies: None
  - Output: `extract_brand_from_url()` function
  - Notes: Created with BrandAssets dataclass, validation, error handling

- [x] **1.7** Add `/api/preview-brand` endpoint (returns Firecrawl results without saving)
  - Dependencies: 1.6, server.py exists
  - Output: POST endpoint working
  - Notes: Added PreviewBrandRequest Pydantic model, BrandExtractor integration

- [x] **1.8** Add `/api/save-brand` endpoint (validates and stores to `user_profiles`)
  - Dependencies: 1.7
  - Output: POST endpoint with validation
  - Notes: Added SaveBrandRequest Pydantic model, validate_brand_assets integration

- [x] **1.9** Implement brand validation (hex color regex, font-family sanitization)
  - Dependencies: 1.8
  - Output: Validation functions
  - Notes: Implemented in brand_extractor.py with _validate_hex_color, _sanitize_font_family

- [ ] **1.10** Add rollback endpoint `/api/brand-history` (stores last 3 brand versions)
  - Dependencies: 1.8
  - Output: History tracking system
  - Notes:

### Frontend - Brand Settings Tab (GORGEOUS DESIGN)
- [x] **1.11** Add "Brand Assets" tab to existing index.html sidebar
  - Dependencies: None
  - Output: New tab in sidebar with modern styling
  - Design Notes: Implemented with dark glassmorphism styling and dedicated Brand Assets controls

- [x] **1.12** Create URL input with "Analyze Website" button (calls preview endpoint)
  - Dependencies: 1.11
  - Output: Input component with loading states
  - Design Notes: Implemented with loading states + preview panel reveal

- [x] **1.13** Build brand preview panel (shows extracted colors, fonts, logo)
  - Dependencies: 1.12
  - Output: Visual preview component
  - Design Notes: Includes extracted palette chips, extracted font chips, and live logo/brand-name swap

- [x] **1.14** Implement live CSS variable injection (`--brand-primary`, `--brand-secondary`)
  - Dependencies: 1.13
  - Output: Real-time preview working
  - Design Notes: Extended to full `ui_theme` token map application (not only core brand vars)

- [x] **1.15** Add manual override inputs for each brand property
  - Dependencies: 1.13
  - Output: Form inputs with validation
  - Design Notes: Core color overrides regenerate synced theme tokens on save

- [x] **1.16** Create "Save & Apply" button with success/error messaging
  - Dependencies: 1.15
  - Output: Action button with feedback
  - Design Notes: Save path persists `ui_theme`, `extracted_colors`, and `extracted_fonts` then applies globally

- [x] **1.17** Add file upload area (logo SVG/PNG, brand guidelines PDF)
  - Dependencies: 1.11
  - Output: Drag-and-drop upload zone
  - Design Notes: Animated drop zone with pulse effect, file preview cards

- [x] **1.18** Implement client-side file validation (size, format checks)
  - Dependencies: 1.17
  - Output: Validation logic
  - Design Notes: Implemented extension-based filtering and file list rendering

### Integration
- [-] **1.19** Modify `orchestrator.py` to accept `--user_id` parameter
  - Dependencies: None
  - Output: Updated orchestrator
  - Notes: Implemented in code (`orchestrator.py`, `server.py`) and threaded to `generate_assets.py`; pending in-app E2E validation before marking complete.

- [x] **1.19.a** Remove logo compositing from generation pipeline (`generate_assets.py`)
  - Dependencies: Image generation pipeline in place
  - Output: Images are returned as generated, with no post-processing logo overlay
  - Notes: Removed logo-placement prompt contract and response fields (`logo_position`, `logo_variant`)

- [x] **1.19.b** Remove logo compositing from regeneration endpoint (`/api/regenerate-image`)
  - Dependencies: 1.19.a
  - Output: Tweak/refine regenerate modes return direct image output
  - Notes: Removed `_composite_logo` import/calls from `server.py`

- [-] **1.20** Update `generate_assets.py` to inject brand colors into image prompts
  - Dependencies: 1.19
  - Output: Dynamic brand injection
  - Notes: Runtime injection now uses active user brand profile + persona context in prompt stack; still pending in-app validation.

- [ ] **1.21** Test end-to-end: Extract brand → Preview → Save → Generate post with brand colors
  - Dependencies: 1.20
  - Output: Working integration test
  - Notes:

---

## PHASE 2: Voice Engine & LinkedIn Ingestion

### Database - Vector Setup
- [ ] **2.1** Enable `pgvector` extension in Supabase
  - Dependencies: 1.1
  - Output: Extension enabled
  - Notes:

- [x] **2.2** Create `voice_chunks` table
  - Dependencies: 2.1
  - Output: Table with embedding vector column
  - Notes:

- [x] **2.3** Create `voice_engine_profiles` table
  - Dependencies: 2.1
  - Output: Structured context table
  - Notes:

- [x] **2.4** Set up RLS policies for voice tables
  - Dependencies: 2.2, 2.3
  - Output: Policies active
  - Notes:

### Backend - LinkedIn Parser
- [x] **2.5** Create `execution/linkedin_parser.py` with folder-agnostic ZIP parsing
  - Dependencies: None
  - Output: Parser module
  - Notes:

- [x] **2.6** Build CSV extraction logic
  - Dependencies: 2.5
  - Output: Profile, Positions, Shares extraction
  - Notes:

- [x] **2.7** Add `/api/upload-linkedin` endpoint
  - Dependencies: 2.5, server.py
  - Output: Upload endpoint with job_id response
  - Notes:

- [x] **2.8** Implement Modal background worker for async processing
  - Dependencies: 2.7, Modal setup
  - Output: Background job processing
  - Notes:

- [x] **2.9** Create `execution/persona_builder.py`
  - Dependencies: 2.6
  - Output: Gemini integration for bio + writing style
  - Notes:

- [x] **2.10** Add chunking logic for career history
  - Dependencies: 2.9
  - Output: Vector-searchable chunks
  - Notes: LinkedIn ingestion now also supports structured knowledge chunks (pending in-app validation).

- [-] **2.10.a** Add structured knowledge extraction for persona/brand/products
  - Dependencies: 2.10
  - Output: `knowledge_extractor.py` JSON output to enrich RAG + brand assets
  - Notes: Pending in-app validation

- [x] **2.11** Store chunks in `voice_chunks` with embeddings
  - Dependencies: 2.10
  - Output: Populated vector database
  - Notes:

### Backend - RAG Search
- [x] **2.12** Create `execution/rag_manager.py`
  - Dependencies: 2.1
  - Output: Similarity search function
  - Notes:

- [x] **2.13** Implement relevance threshold logic (0.6 cutoff)
  - Dependencies: 2.12
  - Output: Fallback detection
  - Notes:

- [x] **2.14** Add `/api/search-voice` endpoint
  - Dependencies: 2.12
  - Output: Search endpoint
  - Notes:

### Frontend - Voice Engine Tab
- [x] **2.15** Add "Voice Engine" tab to sidebar
  - Dependencies: 1.11
  - Output: New tab with animations
  - Design Notes: Fade-in animations, staggered content reveal

- [x] **2.16** Build LinkedIn ZIP upload UI with progress indicator
  - Dependencies: 2.15
  - Output: Upload component with progress
  - Design Notes: Animated progress bar, percentage counter

- [ ] **2.17** Create persona preview panel
  - Dependencies: 2.16
  - Output: Bio and writing rules display
  - Design Notes: Card flip animations, hover effects

- [ ] **2.18** Add manual editing forms for professional context
  - Dependencies: 2.17
  - Output: Editable forms
  - Design Notes: Inline editing with save animation

- [ ] **2.19** Build "Products & Services" dynamic form
  - Dependencies: 2.18
  - Output: Add/remove offerings
  - Design Notes: Smooth add/remove transitions, reorder drag animation

- [ ] **2.20** Add messaging pillars input
  - Dependencies: 2.18
  - Output: Tag-style interface
  - Design Notes: Animated tag creation/deletion

### Integration
- [-] **2.21** Modify prompt construction in `generate_assets.py`
  - Dependencies: 1.20
  - Output: Dual-engine ready
  - Notes: Added active-user prompt blocks (persona + brand) in system/runtime context. Needs app-level behavioral validation.

- [ ] **2.22** Implement Dual-Engine: parallel web search + RAG call
  - Dependencies: 2.21, 2.12
  - Output: Parallel processing
  - Notes:

- [ ] **2.23** Add fallback prompt logic when RAG relevance < 0.6
  - Dependencies: 2.22
  - Output: Graceful fallback
  - Notes:

- [ ] **2.24** Test: Upload ZIP → Build persona → Generate post with personal story
  - Dependencies: 2.23
  - Output: End-to-end test passing
  - Notes:

---

## PHASE 3: CRM & Message Intelligence

### Database - CRM Schema
- [ ] **3.1** Create `crm_contacts` table
  - Dependencies: 1.1
  - Output: Contact storage
  - Notes:

- [ ] **3.2** Create `message_threads` table
  - Dependencies: 3.1
  - Output: Conversation history
  - Notes:

- [ ] **3.3** Add RLS policies for CRM tables
  - Dependencies: 3.2
  - Output: Security policies
  - Notes:

- [ ] **3.4** Create indexes for fast filtering
  - Dependencies: 3.3
  - Output: Performance indexes
  - Notes:

### Backend - Message Analyzer
- [ ] **3.5** Create `execution/message_analyzer.py`
  - Dependencies: None
  - Output: Behavioral tagging module
  - Notes:

- [ ] **3.6** Implement reply pattern analysis
  - Dependencies: 3.5
  - Output: Cold pitch, Warm, Hot Lead detection
  - Notes:

- [ ] **3.7** Add tagging logic (Warm, Hot Lead, Ghosted, Dormant)
  - Dependencies: 3.6
  - Output: Complete tag set
  - Notes:

- [ ] **3.8** Create LLM intent extraction
  - Dependencies: 3.7
  - Output: Intent + summary generation
  - Notes:

- [ ] **3.9** Add `/api/crm/import-messages` endpoint
  - Dependencies: 3.8
  - Output: Import endpoint
  - Notes:

- [-] **3.10** Build CRM query endpoints
  - Dependencies: 3.9
  - Output: Filter and search APIs
  - Notes: Implemented (`GET /api/crm/contacts`) with pagination-aware backend fetch + slim row payload for datatable rendering; pending in-app validation.

### Backend - Message Generator
- [-] **3.11** Create `execution/message_generator.py`
  - Dependencies: None
  - Output: Reply generator
  - Notes: Implemented with Gemini model + full conversation transcript prompt context; pending in-app quality validation.

- [-] **3.12** Implement `draft_crm_reply()`
  - Dependencies: 3.11, 2.9
  - Output: Contextual reply drafting
  - Notes: Implemented via `/api/crm/generate-message` + row-level draft auto-save and manual draft persistence endpoint; pending in-app validation.

- [-] **3.13** Add `/api/crm/generate-reply` endpoint
  - Dependencies: 3.12
  - Output: API endpoint
  - Notes: Equivalent implementation exists as `POST /api/crm/generate-message`; now conversation-aware and draft-persistent. Pending in-app validation.

### Frontend - CRM Tab
- [ ] **3.14** Add "Network Intelligence" tab
  - Dependencies: 1.11
  - Output: New tab
  - Design Notes: Animated table rows, smooth filtering

- [-] **3.15** Build CRM table
  - Dependencies: 3.14
  - Output: Data table with columns
  - Design Notes: Implemented professional Airtable/Baserow-style table shell with sticky header, draft column, and row actions; pending in-app validation.

- [ ] **3.16** Implement Smart Views dropdown
  - Dependencies: 3.15
  - Output: Filter dropdown (Hot Leads, Warm, Spam)
  - Design Notes: Animated dropdown, active state highlighting

- [ ] **3.17** Add unified search bar
  - Dependencies: 3.15
  - Output: Search with debounce
  - Design Notes: Search icon animation, clear button

- [-] **3.18** Create "Generate Message" button with modal
  - Dependencies: 3.17, 3.13
  - Output: Message generation UI
  - Design Notes: Implemented generate action + modal-based draft editor with persistent save/copy flow; pending in-app validation.

- [ ] **3.19** Add contact detail drawer
  - Dependencies: 3.18
  - Output: Side panel with history
  - Design Notes: Slide-out drawer, chat bubble animations

### Integration
- [-] **3.20** Wire up ZIP processing to populate CRM
  - Dependencies: 2.8, 3.9
  - Output: Automatic CRM population
  - Notes: Implemented auto-ingestion from `messages.csv`; needs in-app validation

- [ ] **3.21** Test: Import messages → Tag → Filter → Generate reply
  - Dependencies: 3.20
  - Output: End-to-end test
  - Notes:

---

## PHASE 4: Surveillance & Polish

### Backend - Surveillance
- [ ] **4.1** Extend `execution/surveillance_scraper.py`
  - Dependencies: Existing scraper
  - Output: Database storage
  - Notes:

- [ ] **4.2** Add percentile-based tiering (top 20% = Tier A)
  - Dependencies: 4.1
  - Output: Tier classification
  - Notes:

- [ ] **4.3** Create `golden_vault` table
  - Dependencies: 2.1
  - Output: Top posts storage
  - Notes:

- [ ] **4.4** Add RAG search for similar high-performing posts
  - Dependencies: 4.3
  - Output: Similarity search
  - Notes:

- [ ] **4.5** Implement automated voice style updates
  - Dependencies: 4.4
  - Output: Style evolution
  - Notes:

### Frontend - Surveillance Tab
- [ ] **4.6** Add "Surveillance" tab
  - Dependencies: 1.11
  - Output: New tab
  - Design Notes: Real-time stats animation

- [ ] **4.7** Build post performance table
  - Dependencies: 4.6
  - Output: Engagement metrics
  - Design Notes: Animated counters, sparklines

- [ ] **4.8** Add Golden Vault view
  - Dependencies: 4.7
  - Output: Top 20% posts display
  - Design Notes: Trophy icons, gold accent animations

- [ ] **4.9** Create "Analyze for Voice" button
  - Dependencies: 4.8
  - Output: Style extraction UI
  - Design Notes: Processing animation, success confirmation

### Polish & Testing
- [ ] **4.10** Add comprehensive error handling
  - Dependencies: All phases
  - Output: User-friendly errors
  - Notes:

- [ ] **4.11** Implement loading states for all async operations
  - Dependencies: All phases
  - Output: Consistent loading UX
  - Design Notes: Skeleton screens, shimmer effects

- [ ] **4.12** Add confirmation dialogs
  - Dependencies: All phases
  - Output: Destructive action protection
  - Design Notes: Modal animations, clear CTAs

- [ ] **4.13** Create onboarding flow
  - Dependencies: All phases
  - Output: First-time setup wizard
  - Design Notes: Step-by-step animations, progress indicator

- [ ] **4.14** Write integration tests
  - Dependencies: All phases
  - Output: Test suite
  - Notes:

- [ ] **4.15** Performance testing
  - Dependencies: All phases
  - Output: Benchmarks
  - Notes:

---

## LAST UPDATED
**Status:** Phase 4 In Progress (runtime personalization wired; validation pending)  
**Completed:**
- Phase 1: Brand Assets Foundation (brand_extractor.py, brand APIs, Brand Assets tab, full extracted palette/fonts UI, LLM-generated full UI theme tokens)
- Phase 2: Voice Engine (linkedin_parser.py, persona_builder.py, rag_manager.py, upload endpoints, Voice Engine tab)
- Phase 3: CRM schema + UI architecture split (controls in sidebar, heavy data in output console)
**Next Action:** In-app validate the new CRM datatable + conversation-aware drafting flow (title/company population, row drafts, generated message quality) before marking Phase 3 CRM tasks complete.
**Notes:** `server.py` now stores CRM thread caches (`conversation_id`) and persists row-level drafts; `execution/message_generator.py` uses full conversation transcript context for reply generation; frontend `crm-hub.js` now renders a professional datatable with per-row draft modal actions.
