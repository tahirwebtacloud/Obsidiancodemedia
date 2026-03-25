# Multi-ZIP LinkedIn Ingestion — Implementation Plan

**Goal:** Accept multiple LinkedIn ZIP exports, merge safely with deduplication, show diagnostics, and detect missing files.

**Architecture:** Parser gains merge + diagnostics layer. Server endpoint accepts multiple files and dedupes contacts by `conversation_id`. Frontend supports multi-file selection with a diagnostics report panel.

**Tech Stack:** Python (FastAPI), JavaScript (vanilla), Supabase

---

## Task 1: linkedin_parser.py — Diagnostics + Multi-ZIP merge

- `validate_and_parse_zip` returns a `diagnostics` dict (files_found, rows_per_file, missing_required, missing_optional, skipped_reasons)
- New `parse_multiple_zips(zip_list, user_name)` merges parsed data across ZIPs
- Dedupe connections by profile_url or normalized name
- Dedupe messages by conversation_id (union of messages per thread)

## Task 2: server.py — Multi-file upload + contact dedup

- `/api/upload-linkedin` accepts multiple files via multipart form
- Calls `parse_multiple_zips` on all uploaded ZIPs
- Before adding CRM contacts, checks existing contacts by `conversation_id` to skip duplicates
- Returns diagnostics summary in the upload response
- Stores diagnostics in user profile for frontend to read during polling

## Task 3: Frontend — Multi-file UI + diagnostics panel

- `index.html`: change file input to `multiple`, update dropzone text
- `voice-engine.js`: collect all files, validate each is .zip, show file count
- After upload succeeds, show diagnostics panel (files found, rows parsed, missing files with guidance)
- During polling, show diagnostics from `/api/persona` response

## Task 4: Deploy and verify
