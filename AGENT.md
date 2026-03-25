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

### 2. Top-Level Skills (`.agent/`)

These skills are located at the top level of the `.agent` folder and provide foundational capabilities.

- **Database Architect (`database-architect`)**: Design scalable, performant, and maintainable data layers. Use for greenfield architecture and re-architecture of existing systems. Covers technology selection, data modeling, indexing, query optimization, caching, scalability, migration planning, transaction design, security, cloud architecture, ORM integration, monitoring, and disaster recovery.

- **Performance Engineer (`performance-engineer`)**: Specialize in modern application optimization, observability, and scalable system performance. Use for diagnosing bottlenecks, designing load tests, setting up monitoring, and optimizing latency/throughput. Covers modern observability, advanced application profiling, load testing, multi-tier caching strategies, frontend/backend/distributed system performance optimization, cloud performance, and performance testing automation.

- **Prompt Engineering (`prompt-engineering`)**: Techniques to maximize LLM performance, reliability, and controllability. Use for optimizing prompts, designing template systems, and implementing system prompts. Covers few-shot learning, chain-of-thought prompting, prompt optimization, template systems, system prompt design, progressive disclosure, instruction hierarchy, best practices, common pitfalls, and when to use this skill.

### 3. Rules (`.agent/rules/`)

Rules provide guidelines for how the agent should operate in specific contexts.

- **Brainstorming (`brainstorming`)**: MUST be used before any creative work to explore user intent, requirements, and design. Use for checking project state, asking clarifying questions, proposing approaches with trade-offs, presenting designs in small sections, validating each section, and saving the validated design.

- **Doc Co-authoring (`doc-coauthoring`)**: Guides users through a structured workflow for collaboratively writing documentation. Consists of three stages: Context Gathering (user provides context, Claude asks clarifying questions), Refinement & Structure (iteratively building sections through brainstorming, curation, and refinement), and Reader Testing (testing the document with a fresh Claude instance to catch blind spots).

- **Error Handling Patterns (`error-handling-patterns`)**: Master error handling patterns across languages to build resilient applications. Use when implementing error handling, designing APIs, or debugging. Covers exceptions vs. result types, error categories (recoverable vs. unrecoverable), best practices (fail fast, preserve context, meaningful messages), common pitfalls, and language-specific and universal patterns.

- **Frontend Design (`frontend-design`)**: Create distinctive, production-grade frontend interfaces with high design quality. Emphasizes understanding context, committing to a bold aesthetic direction (e.g., brutally minimal, maximalist chaos), and implementing working code that is visually striking, cohesive, and meticulously refined. Provides guidelines on typography, color, motion, spatial composition, and backgrounds, while explicitly warning against generic AI aesthetics.

- **Gemini API Dev (`gemini-api-dev`)**: Use when building applications with Gemini models, Gemini API, working with multimodal content, or needing current model specifications. Covers working with multimodal content, implementing function calling, using structured outputs, and understanding current model specifications. Provides quick start guides for Python, JavaScript/TypeScript, Go, and Java SDKs.

- **Research Intelligence (`research-intelligence`)**: Expert LinkedIn Content Researcher that performs deep web research to extract real-time data, company information, logos, and news for intelligent content generation. Uses Jina AI for search and extraction and follows a 4-phase workflow: Entity Detection, Search, Content Extraction, and Analysis & Synthesis. Defines a structured JSON output schema for research data.

- **Skill Creator (`skill-creator`)**: Guide for creating effective skills that extend Claude's capabilities. Defines what skills provide (specialized workflows, tool integrations, domain expertise, bundled resources) and outlines core principles like conciseness and setting appropriate degrees of freedom. Details the anatomy of a skill (SKILL.md, scripts, references, assets), what not to include, and the progressive disclosure design principle.

- **Webapp Testing (`webapp-testing`)**: Toolkit for interacting with and testing local web applications using Playwright. Supports verifying frontend functionality, debugging UI behavior, capturing screenshots, and viewing browser logs. Provides guidance on choosing between static HTML and dynamic webapp testing approaches, with examples for using `scripts/with_server.py` to manage server lifecycles.

- **Writing Plans (`writing-plans`)**: Use when you have a spec or requirements for a multi-step task. Creates comprehensive implementation plans by breaking down features into bite-sized tasks (2-5 minutes each), specifying files to create/modify/test, test cases, implementation, and verification for each task. Emphasizes TDD, DRY, and YAGNI principles.

### 4. Skills (`.agent/skills/`)

Skills provide specialized capabilities for specific tasks.

- **Algorithmic Art (`algorithmic-art`)**: Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration. Use when users request creating art using code, generative art, algorithmic art, flow fields, or particle systems. Creates original algorithmic art rather than copying existing artists' work to avoid copyright violations.

- **Baseline UI (`baseline-ui`)**: Validates animation durations, enforces typography scale, checks component accessibility, and prevents layout anti-patterns in Tailwind CSS projects. Use when building UI components, reviewing CSS utilities, styling React views, or enforcing design consistency.

- **Blotato Publisher (`blotato_publisher`)**: Review-first LinkedIn publishing system with quality enforcement, scheduling intelligence, and content calendar sync. Use for publishing to LinkedIn, scheduling posts, quality checking, and content management.

- **Brand Identity (`brand-identity`)**: Serves as the single source of truth for Obsidian Logic AI's brand guidelines. Use for generating UI components, styling applications, writing copy, or creating user-facing assets to ensure consistent brand identity.

- **Canvas Design (`canvas-design`)**: Create beautiful visual art in .png and .pdf documents based on a design philosophy. Use for creating posters, pieces of art, designs, or other static pieces.

- **DOCX (`docx`)**: Use whenever the user wants to create, read, edit, or manipulate Word documents (.docx files). Triggers include: any mention of "Word doc", "word document", ".docx", or requests to produce professional documents with formatting like tables of contents, headings, page numbers, or letterheads.

- **Fixing Accessibility (`fixing-accessibility`)**: Audit and fix HTML accessibility issues including ARIA labels, keyboard navigation, focus management, color contrast, and form errors. Use when adding interactive controls, forms, dialogs, or reviewing WCAG compliance.

- **Fixing Metadata (`fixing-metadata`)**: Audit and fix HTML metadata including page titles, meta descriptions, canonical URLs, Open Graph tags, Twitter cards, favicons, JSON-LD structured data, and robots directives. Use when adding SEO metadata, fixing social share previews, reviewing Open Graph tags, setting up canonical URLs, or shipping new pages that need correct meta tags.

- **Fixing Motion Performance (`fixing-motion-performance`)**: Audit and fix animation performance issues including layout thrashing, compositor properties, scroll-linked motion, and blur effects. Use when animations stutter, transitions jank, or reviewing CSS/JS animation performance.

- **Internal Comms (`internal-comms`)**: Set of resources to help write all kinds of internal communications, using the formats that the company likes to use. Use when asked to write status reports, leadership updates, 3P updates, company newsletters, FAQs, incident reports, or project updates.

- **MCP Builder (`mcp-builder`)**: Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services. Covers deep research and planning, implementation, review and test, and create evaluations.

- **PPTX (`pptx`)**: Use when a .pptx file is involved in any way — as input, output, or both. This includes: creating slide decks, pitch decks, or presentations; reading, parsing, or extracting text from any .pptx file; editing, modifying, or updating existing presentations; combining or splitting slide files; working with templates, layouts, speaker notes, or comments.

- **Theme Factory (`theme-factory`)**: Toolkit for styling artifacts with a theme. These artifacts can be slides, docs, reportings, HTML landing pages, etc. There are 10 pre-set themes with colors/fonts that you can apply to any artifact that has been created, or can generate a new theme on-the-fly.

- **Web Artifacts Builder (`web-artifacts-builder`)**: Suite of tools for creating elaborate, multi-component Claude.ai HTML artifacts using modern frontend web technologies (React, Tailwind CSS, shadcn/ui). Use for complex artifacts requiring state management, routing, or shadcn/ui components - not for simple single-file HTML/JSX artifacts.

- **YouTube Scraping (`youtube-scraping`)**: Scrapes YouTube video metadata, transcripts, and performs advanced language detection. Use when the user needs to extract data (titles, views, likes), full transcripts/captions, analyze video language, or extract resource links from YouTube.

- **NotebookLM Online Anonymity (`notebooklm-online-anonymity`)**: Triggers automatic queries to the 'Beyond the Ghost' NotebookLM instance to extract highly technical OPSEC advice, automated Gmail account creation, user-agent rotation, and threat modeling strategies.

- **NotebookLM Python AI Workflows (`notebooklm-python-ai-workflows`)**: Consults the Python NotebookLM instance for deep insights into programmatic agent architectures, preventing token bloat with SQLite Context Mode MCP, and writing robust automation pipelines.

- **NotebookLM Frontend Training (`notebooklm-frontend-training`)**: Queries the Frontend Training NotebookLM instance for state-of-the-art Web UX patterns involving Stitch 2.0, Stripe integrations, dynamic GSAP cinematic animations, and premium React layouts.

- **NotebookLM Agentic AI Architecture (`notebooklm-agentic-ai-architecture`)**: Accesses the 'Architecting Agentic AI' NotebookLM to retrieve authoritative guidance on complex AI SaaS builds (Ad Snap Studio), reinforcement learning models in PyTorch, and prompt engineering.

- **NotebookLM Supermemory Context (`notebooklm-supermemory-context`)**: Retrieves documentation from the Supermemory NotebookLM instance regarding long-term contextual engines, semantic graphs, user profiling, and AI proxy routing across diverse sessions.

### 5. Systematic Debugging (`.agent/systematic-debugging/`)

- **Systematic Debugging (`systematic-debugging`)**: Outlines a structured approach to debugging any technical issue. Emphasizes finding the root cause before attempting fixes and is divided into four phases: Root Cause Investigation (reading errors, reproducing, checking changes, gathering evidence, tracing data flow), Pattern Analysis (finding working examples, comparing against references, identifying differences, understanding dependencies), Hypothesis and Testing (forming a single hypothesis, testing minimally, verifying), and Implementation (creating a failing test case, implementing a single fix, verifying).

### 6. Trail of Bits Marketplace Skills (`.agent/skills/skills/plugins/`)

These are additional skills from the Trail of Bits skills marketplace, categorized by function.

#### Security Auditing & Vulnerability Detection

- **Agentic Actions Auditor (`agentic-actions-auditor`)**: Audits GitHub Actions workflows for security vulnerabilities in AI agent integrations including Claude Code Action, Gemini CLI, OpenAI Codex, and GitHub AI Inference. Detects attack vectors where attacker-controlled input reaches AI agents running in CI/CD pipelines.

- **Audit Context Building (`audit-context-building`)**: Enables ultra-granular, line-by-line code analysis to build deep architectural context before vulnerability or bug finding. Performs bottom-up analysis with First Principles, 5 Whys, and 5 Hows at micro scale.

- **Constant-Time Analysis (`constant-time-analysis`)**: Detects timing side-channel vulnerabilities in cryptographic code. Use when implementing or reviewing crypto code, encountering division on secrets, or secret-dependent branches in C, C++, Go, Rust, Swift, Java, Kotlin, C#, PHP, JavaScript, TypeScript, Python, or Ruby.

- **Differential Review (`differential-review`)**: Performs security-focused differential review of code changes (PRs, commits, diffs). Adapts analysis depth to codebase size, uses git history for context, calculates blast radius, checks test coverage, and generates comprehensive markdown reports.

- **Entry Point Analyzer (`entry-point-analyzer`)**: Analyzes smart contract codebases to identify state-changing entry points for security auditing. Detects externally callable functions that modify state, categorizes them by access level (public, admin, role-restricted, contract-only), and generates structured audit reports.

- **Insecure Defaults (`insecure-defaults`)**: Detects fail-open insecure defaults (hardcoded secrets, weak auth, permissive security) that allow apps to run insecurely in production. Use when auditing security, reviewing config management, or analyzing environment variable handling.

- **Sharp Edges (`sharp-edges`)**: Identifies error-prone APIs, dangerous configurations, and footgun designs that enable security mistakes. Use when reviewing API designs, configuration schemas, cryptographic library ergonomics, or evaluating whether code follows 'secure by default' and 'pit of success' principles.

- **Supply Chain Risk Auditor (`supply-chain-risk-auditor`)**: Identifies dependencies at heightened risk of exploitation or takeover. Use when assessing supply chain attack surface, evaluating dependency health, or scoping security engagements.

- **Variant Analysis (`variant-analysis`)**: Finds similar vulnerabilities and bugs across codebases using pattern-based analysis. Use when hunting bug variants, building CodeQL/Semgrep queries, analyzing security vulnerabilities, or performing systematic code audits after finding an initial issue.

- **Zeroize Audit (`zeroize-audit`)**: Detects missing zeroization of sensitive data in source code and identifies zeroization removed by compiler optimizations, with assembly-level analysis and control-flow verification. Use for auditing C/C++/Rust code handling secrets, keys, passwords, or other sensitive data.

#### Smart Contract Security

- **Audit Prep Assistant (`audit-prep-assistant`)**: Prepares codebases for security review using Trail of Bits' checklist. Helps set review goals, runs static analysis tools, increases test coverage, removes dead code, ensures accessibility, and generates documentation (flowcharts, user stories, inline comments).

- **Guidelines Advisor (`guidelines-advisor`)**: Smart contract development advisor based on Trail of Bits' best practices. Analyzes codebase to generate documentation/specifications, review architecture, check upgradeability patterns, assess implementation quality, identify pitfalls, review dependencies, and evaluate testing.

#### Static Analysis & Code Review

- **Semgrep (`semgrep`)**: Runs Semgrep static analysis scan on a codebase using parallel subagents. Supports two scan modes — "run all" (full ruleset coverage) and "important only" (high-confidence security vulnerabilities). Automatically detects and uses Semgrep Pro for cross-file taint analysis when available.

- **Semgrep Rule Creator (`semgrep-rule-creator`)**: Creates custom Semgrep rules for detecting security vulnerabilities, bug patterns, and code patterns. Use when writing Semgrep rules or building custom static analysis detections.

- **Semgrep Rule Variant Creator (`semgrep-rule-variant-creator`)**: Creates language variants of existing Semgrep rules. Use when porting a Semgrep rule to specified target languages. Takes an existing rule and target languages as input, produces independent rule+test directories for each language.

- **Spec-to-Code Compliance (`spec-to-code-compliance`)**: Verifies code implements exactly what documentation specifies for blockchain audits. Use when comparing code against whitepapers, finding gaps between specs and implementation, or performing compliance checks for protocol implementations.

#### Malware Detection & YARA

- **YARA Rule Authoring (`yara-authoring`)**: Guides authoring of high-quality YARA-X detection rules for malware identification. Use when writing, reviewing, or optimizing YARA rules. Covers naming conventions, string selection, performance optimization, migration from legacy YARA, and false positive reduction.

#### Mobile & Platform Security

- **Firebase APK Scanner (`firebase-apk-scanner`)**: Scans Android APKs for Firebase security misconfigurations including open databases, storage buckets, authentication issues, and exposed cloud functions. Use when analyzing APK files for Firebase vulnerabilities, performing mobile app security audits, or testing Firebase endpoint security. For authorized security research only.

#### Development & Tooling

- **Modern Python (`modern-python`)**: Configures Python projects with modern tooling (uv, ruff, ty). Use when creating projects, writing standalone scripts, or migrating from pip/Poetry/mypy/black. Covers uv (package/dependency management), ruff (linting AND formatting), ty (type checking), pytest (testing with coverage), and prek (pre-commit hooks).

- **Property-Based Testing (`property-based-testing`)**: Provides guidance for property-based testing across multiple languages and smart contracts. Use when writing tests, reviewing code with serialization/validation/parsing patterns, designing features, or when property-based testing would provide stronger coverage than example-based tests.

- **Devcontainer Setup (`devcontainer-setup`)**: Creates devcontainers with Claude Code, language-specific tooling (Python/Node/Rust/Go), and persistent volumes. Use when adding devcontainer support to a project, setting up isolated development environments, or configuring sandboxed Claude Code workspaces.

- **Using GH CLI (`gh-cli`)**: Guides usage of the GitHub CLI (gh) for interacting with GitHub repositories, PRs, issues, and API. Use when working with GitHub resources instead of WebFetch or curl.

- **Git Cleanup (`git-cleanup`)**: Safely analyzes and cleans up local git branches and worktrees by categorizing them as merged, squash-merged, superseded, or active work.

#### Testing & Fuzzing

- **Testing Handbook Generator (`testing-handbook-generator`)**: Meta-skill that analyzes the Trail of Bits Testing Handbook (appsec.guide) and generates Claude Code skills for security testing tools and techniques. Use when creating new skills based on handbook content.

#### Debugging & Troubleshooting

- **Debug Buttercup (`debug-buttercup`)**: Debugs the Buttercup CRS (Cyber Reasoning System) running on Kubernetes. Use when diagnosing pod crashes, restart loops, Redis failures, resource pressure, disk saturation, DinD issues, or any service misbehavior in the crs namespace.

- **Claude in Chrome Troubleshooting (`claude-in-chrome-troubleshooting`)**: Diagnose and fix Claude in Chrome MCP extension connectivity issues. Use when mcp__claude-in-chrome__* tools fail, return "Browser extension is not connected", or behave erratically.

#### Code Review & Collaboration

- **Ask Questions If Underspecified (`ask-questions-if-underspecified`)**: Clarify requirements before implementing. Use when serious doubts arise. Asks 1-5 must-have questions in a scannable, answerable format (multiple choice + defaults), pauses before acting until required answers are provided, and restates confirmed requirements before starting work.

- **Second Opinion (`second-opinion`)**: Runs external LLM code reviews (OpenAI Codex or Google Gemini CLI) on uncommitted changes, branch diffs, or specific commits. Use when the user asks for a second opinion, external review, codex review, gemini review, or mentions /second-opinion.

- **Skill Improver (`skill-improver`)**: Iteratively reviews and fixes Claude Code skill quality issues until they meet standards. Runs automated fix-review cycles using the skill-reviewer agent. Use to fix skill quality issues, improve skill descriptions, run automated skill review loops, or iteratively refine a skill.

#### Specialized Tools

- **Burpsuite Project Parser (`burpsuite-project-parser`)**: Searches and explores Burp Suite project files (.burp) from the command line. Use when searching response headers or bodies with regex patterns, extracting security audit findings, dumping proxy history or site map data, or analyzing HTTP traffic captured in a Burp project.

- **DWARF Expert (`dwarf-expert`)**: Provides expertise for analyzing DWARF debug files and understanding the DWARF debug format/standard (v3-v5). Triggers when understanding DWARF information, interacting with DWARF files, answering DWARF-related questions, or working with code that parses DWARF data.

- **Seatbelt Sandboxer (`seatbelt-sandboxer`)**: Generates minimal macOS Seatbelt sandbox configurations. Use when sandboxing, isolating, or restricting macOS applications with allowlist-based profiles.

- **Let Fate Decide (`let-fate-decide`)**: Draws 4 Tarot cards using os.urandom() to inject entropy into planning when prompts are vague or underspecified. Interprets the spread to guide next steps. Use when the user is nonchalant, feeling lucky, says 'let fate decide', makes Yu-Gi-Oh references ('heart of the cards'), demonstrates indifference about approach, or says 'try again' on a system with no changes.

- **Interpreting Culture Index (`interpreting-culture-index`)**: Interprets Culture Index (CI) surveys, behavioral profiles, and personality assessment data. Supports individual profile interpretation, team composition analysis (gas/brake/glue), burnout detection, profile comparison, hiring profiles, manager coaching, interview transcript analysis for trait prediction, candidate debrief, onboarding planning, and conflict mediation.

### 7. GStack Skills (`gstack`)

- **Web Browsing**: You MUST use the `/browse` skill from gstack for all web browsing tasks.
- **Chrome Tools**: NEVER use `mcp__claude-in-chrome__*` tools.

#### Available GStack Skills

- `/office-hours`
- `/plan-ceo-review`
- `/plan-eng-review`
- `/plan-design-review`
- `/design-consultation`
- `/review`
- `/ship`
- `/browse`
- `/qa`
- `/qa-only`
- `/design-review`
- `/setup-browser-cookies`
- `/retro`
- `/investigate`
- `/document-release`
- `/codex`
- `/careful`
- `/freeze`
- `/guard`
- `/unfreeze`
- `/gstack-upgrade`
