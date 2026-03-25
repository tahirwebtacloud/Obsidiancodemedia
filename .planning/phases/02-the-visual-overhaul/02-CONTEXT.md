# Phase 2: The Visual Overhaul - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Rebuild the Studio, Intelligence, and Identity tabs using Progressive Disclosure, React Suspense, and Shadcn components. The layout must match a split-screen design, skeletons must mask loading latency instantly, and the Brand Identity must be centralized.

</domain>

<decisions>
## Implementation Decisions

### Loading States & Latency
- Keep the existing Server-Sent Events (SSE) pipeline.
- Enhance the SSE pipeline to strictly align with the visual generation, providing real-time text streaming rather than just abstract skeletons.

### Tab Navigation Strategy
- Progressive Disclosure (Single-Page App feel).
- **Crucial requirement:** State must be preserved between tab switches (e.g., if a user types a form on the Studio tab, switches to Identity, and switches back, the form data MUST still be there).

### Color Theme & Brand Consistency
- Default theme is the existing Obsidian Logic (Obsidian Black `#0E0E0E` / Signal Yellow `#F9C74F`).
- **Dynamic Theming Support:** The UI must be architected to accept dynamic CSS variables injected from the backend (when Firecrawl extracts a user's organization color palette).

### Split-Screen Responsiveness (Studio)
- Desktop: Side-by-side (Left: Form, Right: Canvas).
- Mobile: Form first. Upon submission, the view slides or switches to the Canvas view.

### Identity Tab Representation
- Structured / Technical View.
- Use strict cards or JSON-like visual blocks that clearly separate Persona, Brand Knowledge, and Output Directives so the user can easily see the "code/constraints" behind the AI.

### Evolution Dashboard Visuals
- Use modern charts (Recharts/Tremor) to show Impression growth.
- Include explicit, highly-visible callout boxes underneath for "Winning Hook" and "Winning CTA".

### Form Inputs
- Use standard, clean Shadcn text inputs and dropdowns. Prioritize speed and predictability over overly complex "smart" inputs.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Shadcn UI foundation initialized in Phase 1 (button, etc. available via `components/ui`).
- Tailwind v4 configured.

### Established Patterns
- We are using Next.js App Router (`app/` directory).
- Client-side interactivity requires `"use client"` directives.

### Integration Points
- Frontend UI components must hook into the proxy API route established in Phase 1 (`/api/generate`).

</code_context>

<specifics>
## Specific Ideas

- "Please! Don't mess or ruin anything at all" — strict adherence to non-destructive visual updates.
- State preservation across tabs is non-negotiable for UX.
- The use of Google's Stitch MCP is authorized *only* for designing React visual component code (no logic rewrites).

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed tightly within phase scope.

</deferred>

---

*Phase: 02-the-visual-overhaul*
*Context gathered: 2026-03-23*
