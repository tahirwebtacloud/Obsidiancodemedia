# Proposed Roadmap

**3 phases** | **15 requirements mapped** | All v1 requirements covered ✓

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | The Security DMZ | Establish the Next.js App Router foundation, locking down all API inputs via Zod and migrating Supabase Auth to secure HTTP-only cookies. | SEC-01, SEC-02, SEC-03, SEC-04, SEC-05 | 4 |
| 2 | The Visual Overhaul | Complete    | 2026-03-23 | 3 |
| 3 | The Evolution Engine | Build the Chrome Extension scraper, fuzzy-match data loop, and deterministic math Python script to safely update the User Playbooks. | EVO-01, EVO-02, EVO-03, EVO-04, EVO-05 | 4 |

## Phase Details

### Phase 1: The Security DMZ
Goal: Establish the Next.js App Router foundation, locking down all API inputs via Zod and migrating Supabase Auth to secure HTTP-only cookies.
Requirements: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05
**Plans:** 3 plans
Plans:
- [ ] 01-01-PLAN.md — Initialize Next.js App Router workspace and configure Supabase SSR Auth
- [ ] 01-02-PLAN.md — Remove development auth bypasses and enforce strict JWT validation in the FastAPI server
- [ ] 01-03-PLAN.md — Implement Next.js proxy endpoints with Zod validation and Upstash Rate Limiting
Success criteria:
1. `frontend-next/` directory compiles successfully.
2. User can log in/out using Supabase SSR (cookies present in browser).
3. Hitting the generation API with a malformed payload is rejected by Zod before hitting Python.
4. Python `AUTH_BYPASS` is totally removed.

### Phase 2: The Visual Overhaul
Goal: Rebuild the Studio, Intelligence, and Identity tabs using Progressive Disclosure, React Suspense, and Shadcn components.
Requirements: UI-01, UI-02, UI-03, UI-04, UI-05
Success criteria:
1. The new UI matches the split-screen design.
2. Generating a post shows a shimmering skeleton instantly instead of freezing the page.
3. Brand Identity is successfully centralized in one tab without data loss.

### Phase 3: The Evolution Engine
Goal: Build the Chrome Extension scraper, fuzzy-match data loop, and deterministic math Python script to safely update the User Playbooks.
Requirements: EVO-01, EVO-02, EVO-03, EVO-04, EVO-05
Success criteria:
1. Chrome Extension successfully pulls impressions from LinkedIn without triggering bans.
2. The fuzzy-matcher correctly maps a scraped post to its internal `history_id`.
3. The LLM updates the `user_playbook.md` strictly, without hallucination.
4. Python math accurately flags the "winning" hooks based on Impression/Comment conversion ratios.

---
