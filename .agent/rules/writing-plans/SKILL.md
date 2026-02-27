---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code. Writes comprehensive implementation plans.
---

# Writing Plans

## When to use this skill
- When you have a clear design or spec (e.g., from `brainstorming`).
- Before writing any code for a complex task.
- To break down a feature into bite-sized, testable tasks.

## Workflow
[ ] Create a new plan file at `docs/plans/YYYY-MM-DD-<feature-name>.md`.
[ ] Write the Plan Header (Goal, Architecture, Tech Stack).
[ ] Break down the feature into "Bite-Sized Tasks" (2-5 mins each).
[ ] For each task, specify: Files to Create/Modify/Test, Test Case, Implementation, Verification.
[ ] Review the plan for DRY, YAGNI, and TDD principles.
[ ] Save the plan and offer execution options.

## Instructions

**1. Mindset**
- Assume the implementer has zero context and questionable taste.
- Be extremely specific (exact file paths, exact commands).
- **YAGNI** (You Ain't Gonna Need It) & **DRY** (Don't Repeat Yourself).
- **TDD** (Test Driven Development) is mandatory.

**2. Bite-Sized Granularity**
Each step should be 2-5 minutes of work:
- Write failing test.
- Run test (fail).
- Minimal implementation.
- Run test (pass).
- Commit.

**3. Plan Structure**
Plans **MUST** start with this header:
```markdown
# [Feature Name] Implementation Plan
**Goal:** [One sentence]
**Architecture:** [2-3 sentences]
**Tech Stack:** [Keywords]
---
```

**4. Task Structure**
Use this template for every task:
```markdown
### Task N: [Component Name]
**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Step 1: Write the failing test**
[Code block]

**Step 2: Run test to verify it fails**
Run: [Command]
Expected: [Error message]

**Step 3: Write minimal implementation**
[Code block]

**Step 4: Run test to verify it passes**
Run: [Command]
Expected: PASS

**Step 5: Commit**
[Git commands]
```

**5. Handoff**
After saving the plan, offer execution options (e.g., Subagent-Driven or Parallel Session).

## Resources
- [See SKILL.md for original source logic]
