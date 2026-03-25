# 🎙️ The Journalist Workflow (Interview-to-Content)

**Goal:** Turn your daily experience ("What I did") into thought leadership ("What I learned") without staring at a blank screen.
**Method:** You don't write. You *answer*.

---

## 📅 The Daily Download (5 Minutes)
Every day (or once a week), answer these 3 questions using a **Voice Note** (Otter.ai) or **Bullet Points**.

### 1. The "Trenches" Question
> *"What specific AI optimization or automation did I run today? What tools did I chain together?"*
> *(e.g., Connected Clay to Instantly to automated 50 emails.)*

### 2. The "Friction" Question
> *"Where did I get stuck? What broke? What was harder than expected?"*
> *(e.g., The Apify actor failed because of a cookie issue.)*

### 3. The "Epiphany" Question
> *"What is the 'Meta-Lesson' here for other Founders/Ops Leaders?"*
> *(e.g., You can't rely on 'No-Code' completely; you need a fallback script.)*

---

## 🤖 The "Ghostwriter" Prompt
Paste your raw notes/transcript into ChatGPT/Claude with this System Prompt. It will format them into your "Obsidian Voice".

```text
ROLE: You are an expert Ghostwriter for a specialized AI Consultancy. 
TONE: "Obsidian". Analytical, Direct, High-Value. No fluff. No emoji overload.
FORMAT: LinkedIn Post (SLAY Framework).

INPUT: I will give you my raw notes from today's work.

TASK: 
1. Extract the core "Story" (The specific problem/workflow).
2. Extract the "Lesson" (The technical insight).
3. Draft a LinkedIn post following this structure:
   - HEADLINE: A 1-line hook about the problem (e.g., "Why 90% of scrapers fail.").
   - STORY: 2-3 sentences max on what I tried to do.
   - INSIGHT: The technical breakdown of the solution.
   - TAKEAWAY: The strategic advice for leaders.
   - CTA: A comments question.

CONSTRAINT: 
- Use short paragraphs (1-2 lines). 
- Focus on "Show, Don't Tell". 
- Mention the specific tools (Apify, Clay, etc.) to build authority.

Here is the context:
[PASTE YOUR NOTES HERE]
```

---

## 🚀 Phase 2 Automation (The Vision)
**How we build this as a tool in the future:**
1.  **Input:** You send a Voice Note to a specialized Telegram Bot.
2.  **Process:** 
    *   Bot sends audio to **OpenAI Whisper** (Transcription).
    *   Script sends transcript to **LLM (Claude/GPT-4)** with the prompt above.
3.  **Output:** You get a notification: *"Draft Ready: 'Why Apify Fails'. Link to Notion."*

**Verdict:** This converts "Day-to-Day Operations" into "Marketing Assets" automatically.
