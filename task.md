# CRM Pipeline Overhaul — Task Tracker

> Last updated: All phases 1–4 complete. H1 + H3 done. H2 + 1C (low-priority) in progress.

---

## Overall Progress

| Phase | Name | Status |
|-------|------|--------|
| **Phase 1** | Contact Data Enrichment (Title + Company) | ✅ Complete |
| **Phase 2** | Two-Pass Gemini 2.5 Pro Classification | ✅ Complete |
| **Phase 3** | Intent Field + Frontend Updates | ✅ Complete |
| **Phase 4** | Personalized Message Generation | ✅ Complete |
| **History** | Log all CRM operations to history table | ✅ H1 ✅, H2 ✅, H3 ✅ |

---

## Phase 1 — Contact Data Enrichment

| Task | Description | Status |
|------|-------------|--------|
| **1A** | Fix connection matching — Unicode normalization, "Last, First" handling, difflib fuzzy match (≥0.80) | ✅ Done |
| **1B** | LLM-inferred title/company fallback from conversation text | ✅ Done (bundled in Pass B structured output) |
| **1C** | Apify profile scraper fallback for high-value contacts still missing title | ✅ Done — `execution/linkedin_profile_scraper.py`, wired post-ingestion in `server.py` |

**Files changed in 1A:**
- `server.py` — improved `_normalize_person_name`, new `_find_connection_for_contact` with fuzzy scan, `connection_list`, `title_source`/`title_confidence` metadata
- `execution/supabase_client.py` — `_normalize_crm_contact` exposes `title_source` + `title_confidence`
- `frontend/crm-hub.js` — confidence dot next to Title column
- `frontend/style.css` — `.crm-conf-dot`, `.crm-cell-with-dot`

---

## Phase 2 — Two-Pass Gemini 2.5 Pro Classification

| Task | Description | Status |
|------|-------------|--------|
| **2A** | Pass A — cold outreacher / spam filter (`_classify_pass_a`, JSON output, last 15 msgs) | ✅ Done |
| **2B** | Pass B — full schema: `behavioral_tag`, `reason_summary`, `evidence[]`, `buyer_stage`, all scores, title inference (`_classify_pass_b`) | ✅ Done |
| **2C** | Rewire ingestion loop: connection lookup before analysis, `use_llm_intent=True`, user_context passed, rate limit 2s, tag counter | ✅ Done |

**Files changed:**
- `execution/message_analyzer.py` — `_format_transcript`, `_classify_pass_a`, `_classify_pass_b`, updated `analyze_conversation` + `analyze_message_thread`
- `server.py` — user_context bundle, reordered loop, inferred title fallback, `time.sleep(2)`, `crm_tag_counter`

---

## Phase 3 — Intent Field + Frontend

| Task | Description | Status |
|------|-------------|--------|
| **3A** | Expose `reason_summary`, `evidence[]`, `buyer_stage`, `urgency_score`, `fit_score`, `confidence` in `/api/crm/contacts` payload | ✅ Done |
| **3B** | Frontend: intent column shows `reason_summary`; hover tooltip shows `evidence[]` bullets; `buyer_stage` sub-label | ✅ Done |
| **3C** | `supabase_client.py` `_normalize_crm_contact` includes all structured Phase 2 fields from metadata | ✅ Done |

**Files changed:**
- `execution/supabase_client.py` — Phase 2 fields in `_normalize_crm_contact`
- `server.py` — slim contacts payload promotes all new fields to top-level
- `frontend/crm-hub.js` — `reason_summary` as intent text, `evidenceTooltip` on hover, `buyer_stage` sub-label

---

## Phase 4 — Personalized Message Generation

| Task | Description | Status |
|------|-------------|--------|
| **4A** | Context bundle: `persona` + `products_services` from `get_user_brand` + `_build_prospect_summary` (reason_summary, evidence, buyer_stage, scores) | ✅ Done |
| **4B** | Adaptive per-tag instructions in `MESSAGE_TEMPLATES` — 7 tags, each with unique tone, goal, CTA, and tag-specific instruction block | ✅ Done |
| **4C** | 5-section structured prompt: Role → Owner Context → Prospect Intel → Conversation → Goal/Tone → Hard Constraints (no em dashes, no fillers, 60–170 words, one CTA only) | ✅ Done |
| **4D** | Fallback messages purged of filler phrases; `personalization_notes` returns tag + transcript count + products count + buyer_stage; auto-save already wired | ✅ Done |

**Files changed:**
- `execution/message_generator.py` — `MESSAGE_TEMPLATES`, `_build_products_block`, `_build_prospect_summary`, `generate_outreach`, `_fallback_message`, test block updated
- `server.py` — `/api/crm/generate-message` fetches `get_user_brand` and passes full `{persona, products_services}` bundle

---

## History — CRM Operations Logging

| Task | Description | Status |
|------|-------------|--------|
| **H1** | Bulk ingestion summary → `history` table (`type: crm_ingestion`) with tag distribution + duration | ✅ Done |
| **H2** | Per-batch LLM classification log (`type: crm_classification`) every 10 contacts | ✅ Done — logged in ingestion loop at `% 10` checkpoint |
| **H3** | Each message generation → `history` table (`type: crm_message_generation`) | ✅ Done |

---

## Next Step

> **All tasks complete. Pipeline fully delivered.**
>
> - 1A ✅ 1B ✅ 1C ✅ — Contact enrichment (fuzzy match, LLM inference, Apify fallback)
> - 2A ✅ 2B ✅ 2C ✅ — Two-pass Gemini 2.5 Pro classification
> - 3A ✅ 3B ✅ 3C ✅ — Intent field + frontend
> - 4A ✅ 4B ✅ 4C ✅ 4D ✅ — Personalized message generation
> - H1 ✅ H2 ✅ H3 ✅ — Full CRM operations history logging
