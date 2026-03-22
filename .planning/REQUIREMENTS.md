# Requirements: Next.js Auto-Evolution System

**Defined:** 2026-03-22
**Core Value:** The system must intelligently evolve generation prompts based on real-world engagement math WITHOUT destroying the brand's static constraints or forcing duplicate A/B test posts.

## v1 Requirements

### Architecture & Security

- [ ] **SEC-01**: Initialize Next.js App Router workspace (`frontend-next`)
- [ ] **SEC-02**: Implement Supabase SSR Auth with HTTP-Only cookies
- [ ] **SEC-03**: Remove `AUTH_BYPASS` from all Python endpoints
- [ ] **SEC-04**: Define Zod validation schemas for all Python API endpoints
- [ ] **SEC-05**: Implement Upstash Rate Limiting via Next.js Middleware

### User Interface

- [x] **UI-01**: Build Studio layout (Left form, Right live canvas)
- [x] **UI-02**: Build Skeletons to mask LLM generation latency
- [ ] **UI-03**: Build Intelligence dashboard (Viral/Competitor)
- [ ] **UI-04**: Build Evolution dashboard with Tremor/Recharts visualizations
- [x] **UI-05**: Build Brand Identity manager (Persona, Directives, Palette)

### Auto-Evolution Data Engine

- [ ] **EVO-01**: Update Python scripts to dump `hook_template_used` and `cta_template_used` to Supabase `history`
- [ ] **EVO-02**: Build Manifest V3 Chrome Extension to scrape LinkedIn impressions
- [ ] **EVO-03**: Build backend API to fuzzy-match 100 char text against `history` table
- [ ] **EVO-04**: Write Python deterministic math script (Impressions/Comments = CTR)
- [ ] **EVO-05**: Write AI prompt (temp=0.0) to update `user_playbook` using strict JSON

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 1 | Pending |
| SEC-02 | Phase 1 | Pending |
| SEC-03 | Phase 1 | Pending |
| SEC-04 | Phase 1 | Pending |
| SEC-05 | Phase 1 | Pending |
| UI-01 | Phase 2 | Complete |
| UI-02 | Phase 2 | Complete |
| UI-03 | Phase 2 | Pending |
| UI-04 | Phase 2 | Pending |
| UI-05 | Phase 2 | Complete |
| EVO-01 | Phase 3 | Pending |
| EVO-02 | Phase 3 | Pending |
| EVO-03 | Phase 3 | Pending |
| EVO-04 | Phase 3 | Pending |
| EVO-05 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-22*