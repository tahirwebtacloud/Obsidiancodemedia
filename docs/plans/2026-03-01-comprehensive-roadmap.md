# Multi-Tenant LinkedIn SaaS Platform - Master Roadmap

**Goal:** Build an enterprise-grade, multi-tenant SaaS platform that automates LinkedIn personal branding, network intelligence, and content generation. The system integrates deep personalization (Voice Engine), real-time network analytics (CRM), and automated brand asset extraction (Firecrawl).

**Architecture:** Python/FastAPI Backend, Supabase/Firestore Database (Vector + Relational), Vanilla JS Frontend.
**Core Pillars:** 1. Database Foundation, 2. Brand Identity Engine, 3. Network Intelligence (CRM), 4. Voice Engine (RAG), 5. Dynamic Content Generation.

---

## Phase 1: Database Foundation & Schema Architecture
**Objective:** Establish the multi-tenant data layer to support all subsequent features.
- **Objectives:**
    - Create `db_schema.py` defining core tables (`user_profiles`, `voice_engine_profiles`, `crm_contacts`, `posts`).
    - Establish `user_id` as the primary tenant isolation key.
    - Set up Vector Store schema for RAG (pgvector or compatible).
- **Deliverables:**
    - `execution/db_schema.py`: Complete Pydantic/SQLAlchemy models.
    - `docs/schema_diagram.md`: Visual representation of relationships.
    - Migration scripts for initial setup.
- **Success Criteria:** Database tables created successfully; dummy user data can be inserted and retrieved with isolation.
- **Risk:** Schema rigidity preventing future expansion. **Mitigation:** Use JSONB columns for flexible fields like `professional_context`.

## Phase 2: Frontend Branding & Firecrawl Integration
**Objective:** Build the "Brand Assets" dashboard tab that auto-extracts colors/fonts from a user's URL.
- **Objectives:**
    - Implement Firecrawl API to scrape brand assets (Logo, Fonts, Colors) from a URL.
    - Build `branding_dashboard.html` with real-time CSS variable injection.
    - Store extracted assets in `user_profiles`.
- **Deliverables:**
    - `execution/brand_extractor.py`: Firecrawl integration logic.
    - `frontend/branding_dashboard.html`: UI for inputting URL and viewing results.
    - `frontend/js/brand_preview.js`: Logic to update UI colors dynamically.
- **Success Criteria:** User enters "obsidianlogic.ai" -> Dashboard UI instantly recolors to match that brand.
- **Dependency:** Phase 1 (Schema).

## Phase 3: Network Intelligence - Ingestion Engine
**Objective:** Create the robust, folder-agnostic ZIP parser for LinkedIn data dumps.
- **Objectives:**
    - Implement `linkedin_parser.py` to handle `Profile.csv`, `Connections.csv`, `messages.csv`.
    - Ensure logic is folder-agnostic (handles `raw/` nesting).
    - Implement chunked processing for large CSVs (>10MB).
- **Deliverables:**
    - `execution/linkedin_parser.py`: Robust ZIP handling.
    - `execution/ingestion_manager.py`: Orchestrator for the upload process.
- **Success Criteria:** Parsing `raw.zip` (with nested folders) correctly extracts and structures data into memory/DB.
- **Dependency:** Phase 1.

## Phase 4: Network Intelligence - Behavioral CRM Logic
**Objective:** Implement the "2-Stage Message Analyzer" (Python Behavior + AI Intent) to tag connections.
- **Objectives:**
    - Stage 1 (Python): Tag "Cold Pitch", "Ghosted", "Warm", "Superficial" based on reply patterns (3+ msgs rule).
    - Stage 2 (AI): Send *only* genuine threads to Gemini Flash for Intent/Summary extraction.
    - Populate `crm_contacts` table with tags and summaries.
- **Deliverables:**
    - `execution/message_analyzer.py`: The core logic engine.
    - `execution/intent_classifier.py`: The Gemini Flash bridge.
- **Success Criteria:** 10,000+ messages processed in <30s (Stage 1). Connections accurately tagged.
- **Dependency:** Phase 3.

## Phase 5: CRM Dashboard & Smart Views UI
**Objective:** Build the "Network Intelligence" UI with unified search and filtering.
- **Objectives:**
    - Create `crm_dashboard.html` with a data grid.
    - Implement "Smart Views" dropdown (Hot Leads, Warm Network, Dormant).
    - Add "Generate Message" button to rows.
- **Deliverables:**
    - `frontend/crm_dashboard.html`: The main CRM view.
    - `frontend/js/crm_logic.js`: Client-side filtering and API calls.
- **Success Criteria:** User can filter 1,000 connections to find "Hot Leads" in <1s.
- **Dependency:** Phase 4.

## Phase 6: Voice Engine - RAG Knowledge Base Setup
**Objective:** Turn the user's history (Resume, Website, Past Posts) into a searchable brain.
- **Objectives:**
    - Scrape user's website using Firecrawl (from Phase 2).
    - Ingest `Positions.csv` and `Profile.csv`.
    - Chunk text into semantic vectors and store in Vector DB.
- **Deliverables:**
    - `execution/rag_manager.py`: Chunking and embedding logic.
    - `execution/vector_store.py`: DB interface.
- **Success Criteria:** Querying "AI" returns the user's specific past job experience with AI.
- **Dependency:** Phase 2 & Phase 3.

## Phase 7: Dynamic Prompt Engine
**Objective:** Build the system that combines Static SOPs with Dynamic User Context.
- **Objectives:**
    - Implement `prompt_engine.py` to read generic SOPs (`directives/*.md`).
    - Build the `construct_master_prompt` function to inject User Tone, Role, and RAG Context.
    - Ensure SOPs remain static files (no hardcoding in Python).
- **Deliverables:**
    - `execution/prompt_engine.py`: The prompt constructor.
    - `directives/`: (Already cleaned and ready).
- **Success Criteria:** Generating an "Authority Article" produces widely different results for User A vs User B using the same SOP.
- **Dependency:** Phase 6.

## Phase 8: Content Generation - "Dual Engine" Workflow
**Objective:** Integrate External Research (Web) with Internal Context (RAG).
- **Objectives:**
    - Process A: Firecrawl/Jina web search for "Topic Facts".
    - Process B: RAG search for "User Experience".
    - Merge A + B into the Master Prompt (Phase 7).
    - Handle "No Context Found" fallback gracefully.
- **Deliverables:**
    - `execution/generate_assets.py`: Updated main generation loop.
    - `execution/research_agent.py`: Web search integration.
- **Success Criteria:** A post about "AI Trends" cites *external* news AND *internal* user opinions.
- **Dependency:** Phase 7.

## Phase 9: Surveillance & "Golden Vault"
**Objective:** Automated tracking of post performance to feed the "Voice Engine".
- **Objectives:**
    - Build `surveillance_tab.html`.
    - Implement Post Tiering Logic (A/B/C) based on engagement percentiles.
    - Auto-save Tier A posts to the "Golden Vault" (Vector DB) for style mimicry.
- **Deliverables:**
    - `frontend/surveillance_tab.html`.
    - `execution/post_analyzer.py`: Scoring logic.
- **Success Criteria:** Top 20% of user posts are automatically saved to "Golden Vault".
- **Dependency:** Phase 8.

## Phase 10: "Inbound Sweeper" & Automations
**Objective:** Background jobs that monitor new connections and draft welcome messages.
- **Objectives:**
    - Monitor `Invitations.csv` or API for new connections.
    - Auto-score inbound profiles against ICP.
    - Draft welcome messages using Voice Engine.
- **Deliverables:**
    - `execution/inbound_sweeper.py`.
    - `execution/automation_scheduler.py`.
- **Success Criteria:** New connection request -> Auto-scored -> Draft welcome message appears in Dashboard.
- **Dependency:** Phase 5 (CRM).

## Phase 11: End-to-End Testing & Optimization
**Objective:** Verify the entire loop from ZIP upload to Post Generation.
- **Objectives:**
    - Run full integration tests.
    - Optimize latency for RAG retrieval and API calls.
    - Polish error handling (ZIP failures, API limits).
- **Deliverables:**
    - Test Suite (`tests/`).
    - Optimization Report.
- **Success Criteria:** Full "Onboarding -> Generation" flow completes without errors.

## Phase 12: Deployment & Documentation
**Objective:** Production readiness.
- **Objectives:**
    - Containerize the application (Docker).
    - Write user documentation.
    - Final security review (API keys, data isolation).
- **Deliverables:**
    - `Dockerfile`.
    - `docs/user_guide.md`.
- **Success Criteria:** Platform runs in a fresh environment.

---

### Immediate Action Plan
We will begin with **Phase 1: Database Foundation**.
1.  Define `User` and `VoiceProfile` schemas.
2.  Define `CRMContact` schema.
3.  Set up the persistence layer.
