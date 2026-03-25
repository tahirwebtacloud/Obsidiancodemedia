# Next.js Auto-Evolution System

## What This Is

A high-performance SaaS platform for LinkedIn content generation. It replaces the current Vanilla JS/FastAPI monolith with a strict Next.js App Router DMZ. It integrates a tag-based "Auto-Evolution" engine that mathematically analyzes LinkedIn post performance via a Chrome Extension to continuously refine the user's custom generation playbook.

## Core Value

The system must intelligently evolve generation prompts based on real-world engagement math WITHOUT destroying the brand's static constraints or forcing duplicate A/B test posts.

## Requirements

### Validated

- ✓ Text Post Generation — existing
- ✓ Carousel Generation — existing
- ✓ Image Generation (Nano Banana Pro) — existing
- ✓ Viral / Competitor Scraping — existing

### Active

- [ ] REQ-UI-01: Next.js App Router Foundation with Shadcn & Tailwind v4
- [ ] REQ-UI-02: Progressive Disclosure UI (Studio, Intelligence, Evolution, Identity tabs)
- [ ] REQ-UI-03: React Suspense Skeletons for generation loading states
- [ ] REQ-SEC-01: Zod schema validation on all inputs
- [ ] REQ-SEC-02: Supabase SSR Authentication (HTTP-only cookies)
- [ ] REQ-SEC-03: Next.js Middleware with Upstash Rate Limiting
- [ ] REQ-EVO-01: Extract Hook/CTA metadata from Gemini SOP
- [ ] REQ-EVO-02: Secure Chrome Extension for zero-friction impression scraping
- [ ] REQ-EVO-03: Fuzzy text matching to link Chrome data to `history_id`
- [ ] REQ-EVO-04: Deterministic Python math script for Hook/CTA conversions
- [ ] REQ-EVO-05: Non-destructive LLM playbook injection

### Out of Scope

- [Direct API posting to LinkedIn] — High ban risk. We rely on manual posting + Chrome Extension read-only scraping.
- [Strict Baseline/Challenger Post Duplication] — Destroys personal brand authenticity. We use Tag-Based Cohort Analysis instead.

## Context

We are migrating from a vulnerable, single-thread blocking Vanilla JS + FastAPI prototype. The FastAPI server (`server.py`) will remain intact as a private, heavily-guarded microservice. Next.js acts as the public-facing application. We just deployed the legacy version to Modal as a stable fallback for existing users.

## Constraints

- **Security**: Must eliminate the `AUTH_BYPASS` vulnerability immediately.
- **Tech Stack**: Must use Next.js App Router for server components and SEO.
- **AI Behavior**: The Evolution Engine must run at `temperature=0.0` and output strict JSON.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Next.js DMZ Architecture | Vanilla JS is insecure and blocks the Python event loop. | — Pending |
| Cohort Analysis over A/B Testing | Posting the same topic twice to test a Hook damages human brand trust. | — Pending |
| Fuzzy Text Matching | Links manual LinkedIn posts back to internal `history_id` seamlessly. | — Pending |

---
*Last updated: 2026-03-22 after initialization*