# Agent Instructions

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

## The 3-Layer Architecture

### Layer 1: Directive (What to do)

- Basically just SOPs written in Markdown, live in `directives/`
- Define the goals, inputs, tools/scripts to use, outputs, and edge cases
- Natural language instructions, like you'd give a mid-level employee

### Layer 2: Orchestration (Decision making)

- This is you. Your job: intelligent routing.
- Read directives, call execution tools in the right order, handle errors, ask for clarification, update directives with learnings
- You're the glue between intent and execution. E.g you don't try scraping websites yourself—you read `directives/scrape_website.md` and come up with inputs/outputs and then run `execution/scrape_single_site.py`

### Layer 3: Execution (Doing the work)

- Deterministic Python scripts in `execution/`
- Environment variables, api tokens, etc are stored in `.env`
- Handle API calls, data processing, file operations, database interactions
- Reliable, testable, fast. Use scripts instead of manual work.
- **Model Standards**:
  - Image Generation: `gemini-3-pro-image-preview` (Internal name: Nano Banana Pro)
  - Text Generation: `gemini-3-pro-preview` (or latest available)

**Why this works:** if you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

## Operating Principles

### 1. Check for tools first

Before writing a script, check `execution/` per your directive. Only create new scripts if none exist.

### 2. Self-anneal when things break

- Read error message and stack trace
- Fix the script and test it again (unless it uses paid tokens/credits/etc—in which case you check w user first)
- Update the directive with what you learned (API limits, timing, edge cases)
- Example: you hit an API rate limit → you then look into API → find a batch endpoint that would fix → rewrite script to accommodate → test → update directive.

### 3. Update directives as you learn

Directives are living documents. When you discover API constraints, better approaches, common errors, or timing expectations—update the directive. But don't create or overwrite directives without asking unless explicitly told to. Directives are your instruction set and must be preserved (and improved upon over time, not extemporaneously used and then discarded).

## Self-annealing loop

Errors are learning opportunities. When something breaks:

1. Fix it
2. Update the tool
3. Test tool, make sure it works
4. Update directive to include new flow
5. System is now stronger

## File Organization

### Deliverables vs Intermediates

- **Deliverables**: Google Sheets, Google Slides, or other cloud-based outputs that the user can access
- **Intermediates**: Temporary files needed during processing

### Directory structure

- `.tmp/` - All intermediate files (dossiers, scraped data, temp exports). Never commit, always regenerated.
- `execution/` - Python scripts (the deterministic tools)
- `directives/` - SOPs in Markdown (the instruction set)
- `frontend/` - Web UI (HTML/CSS/JS single-page app)
  - `index.html` - App shell with sidebar controls + output console
  - `script.js` - All UI logic, API calls, system logging, audio alerts
  - `style.css` - Brand design system (Obsidian Logic theme)
- `.env` - Environment variables and API keys
- `credentials.json`, `token.json` - Google OAuth credentials (required files, in `.gitignore`)

**Key principle:** Local files are only for processing. Deliverables live in cloud services (Google Sheets, Slides, etc.) where the user can access them. Everything in `.tmp/` can be deleted and regenerated.

## Frontend Architecture

The frontend is a single-page app served by `server.py`. Key features:

### Layout

- **Sidebar (400px, dark):** Generate tab, Competitor Hub (Viral/Competitor/YouTube sub-tabs), System Status log panel
- **Main Content (light):** Output Console with results, research expansion, history view

### System Status Log (`log-card`)

- Fixed-height panel (120px) at bottom of sidebar with `flex: none` to prevent growth
- Shows timestamped system events with color-coded type labels (SYS, EXEC, OK, ERR, HTTP, PROC, AI)
- Includes "mad science" fake log stream during processing for dramatic effect

### Audio Alerts (Speech Synthesis)

- Uses browser `SpeechSynthesis` API to announce system events
- **Success logs:** Speaks "Task Completed Successfully" (normal pitch)
- **Error logs:** Speaks "Error. Error." (low pitch 0.3, slow rate 0.8 — robotic voice)
- Triggered automatically from `addSystemLog()` when type is `success` or `error`

### Visual Aspect System

- Supports: Text, Image, Video, Carousel generation
- Dynamic visual style dropdowns based on selected aspect
- Carousel locks purpose to Breakdown/Money Math and forces 4:5 aspect ratio

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Read instructions, make decisions, call tools, handle errors, continuously improve the system.

Be pragmatic. Be reliable. Self-anneal.

## Agent Skills & Rules System

### 1. Mandatory Global Rules (ALWAYS APPLY)

These rules must be followed whenever the context applies, without exception.

- **Brand Identity (`brand-identity`)**: All generated UI, copy, and assets must align with *Obsidian Logic AI* guidelines (Modern, medium energy). **Strict Palette**: Obsidian Black (`#0E0E0E`) & Signal Yellow (`#F9C74F`).
- **Visuals (`visual-engine`)**: PRIORITIZE Authenticity & Visual Proof. Reject generic AI abstract art. Use "Real" photos or high-contrast diagrams.
- **Frontend Design (`frontend-design`)**: STRICTLY AVOID "AI Slop" (generic layouts, purple gradients, Inter font). Use bold, distinct aesthetics.
- **Brainstorming (`brainstorming`)**: MUST be used *before* any new feature, component, or complex logic.
- **Writing Plans (`writing-plans`)**: MUST be used *before* writing code for complex tasks (post-brainstorming).
- **Error Handling (`error-handling-patterns`)**: Apply rigorous error handling patterns (Fail fast, Result types) in all code.
- **Research Intelligence (`research-intelligence`)**: Use for ALL factual queries. Do not guess/hallucinate.

### 2. Skill Triggers (Context Dependent)

Specific triggers for when to activate specialized skills.

- **Web Artifacts (`web-artifacts-builder`)**: Complex, multi-component React/Tailwind/Shadcn apps.
- **Algorithmic Art (`algorithmic-art`)**: Generative art, code art, p5.js.
- **Canvas Design (`canvas-design`)**: Static visual art, posters, ".png", ".pdf".
- **Presentations (`pptx`)**: Slide decks, pitch decks.
- **Word Docs (`docx`)**: Reports, proposals, .docx files.
- **Internal Comms (`internal-comms`)**: Status reports, newsletters, team updates.
- **YouTube (`youtube-scraping`)**: Video data, transcripts, summaries.
- **Testing (`webapp-testing`)**: Verifying local web apps via Playwright.
- **MCP (`mcp-builder`)**: Creating new MCP servers.
- **Styling (`theme-factory`)**: Applying themes to slides/docs.
- **Co-authoring (`doc-coauthoring`)**: Collaborative document writing workflow.
- **Skill Creation (`skill-creator`)**: Creating or updating agent skills.
- **Gemini API Dev (`gemini-api-dev`)**: Use this skill when building applications with Gemini models, Gemini API, working with multimodal content, or needing current model specifications.
