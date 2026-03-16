---
name: Blotato Publisher
version: 1.0.0
type: skill
layer: execution
dependencies: [content_strategist, network_intelligence]
tags: [publishing, scheduling, linkedin, blotato, quality-gate, media]
---

# Blotato Publisher

Review-first LinkedIn publishing system with quality enforcement, scheduling intelligence, and content calendar sync.

## Architecture

```
Draft Post → Quality Gate → Review → Upload Media → Schedule → Confirm → Ledger Update
```

**Nothing publishes without passing the quality gate and explicit confirmation.**

## Workflow: DRAFT → REVIEW → APPROVE → SCHEDULE → CONFIRM

### Step 1: Preview & Score
```bash
python3 SKILLS/blotato_publisher/publish.py preview --image task_audit_final.png
```
Runs the 7-dimension quality gate (hook, vulnerability, framework, math, CTA, visual, timing). Shows score, detected elements, and feedback. Blocks at 18/35 threshold.

### Step 2: Check Schedule
```bash
python3 SKILLS/blotato_publisher/publish.py status
```
Shows upcoming scheduled posts, recent posts, current theme, and next optimal slot. Prevents double-posting and theme drift.

### Step 3: Schedule (with confirmation)
```bash
python3 SKILLS/blotato_publisher/publish.py schedule --image task_audit_final.png
```
Uploads image, shows full confirmation prompt (platform, time, character count, quality score), waits for explicit "yes" before submitting.

## Commands

| Command | Description |
|---------|-------------|
| `preview` | Score post against quality gate without publishing |
| `schedule` | Schedule post (requires confirmation) |
| `schedule --now` | Publish immediately |
| `schedule --time "2026-02-18T16:30:00-05:00"` | Schedule at specific time |
| `status` | View content schedule dashboard |
| `status --detailed` | Full schedule with post previews |
| `accounts` | List connected Blotato accounts |
| `upload <image>` | Upload image, get public URL |
| `theme <week> [month]` | Set content theme |
| `test` | Test API connection |

## Quality Gate (7 Dimensions)

| Dimension | Max | What It Checks |
|-----------|-----|----------------|
| Hook Power | 5 | Identity challenge, dollar specificity, word count |
| Vulnerability | 5 | Personal story, confession, real experience |
| Framework | 5 | Named framework with numbered steps |
| Math/Proof | 5 | Specific dollar calculation or data point |
| CTA | 5 | Open question, DM magnet, or repost nudge |
| Visual | 5 | Image attached (5-10x engagement multiplier) |
| Timing | 5 | Optimal day/time (Tue/Wed 4-5 PM ET) |

**Threshold: 18/35 to publish. Below = BLOCKED.**

Anti-pattern auto-block: Posts with NONE of (personal story, identity challenge, money promise, visual) are blocked regardless of score.

## Scheduling Rules

- **Optimal:** Tuesday or Wednesday, 4:30 PM ET
- **Fallback:** Thursday, 4:00 PM ET
- **Blackout:** Saturday, Sunday
- **Min gap:** 48 hours between posts
- **Max:** 3 posts per week
- **Conflicts:** Auto-detected against schedule ledger

## Media Upload Options

| Method | How It Works | Needs |
|--------|-------------|-------|
| `blotato` | Upload to Blotato's servers via base64 | BLOTATO_API_KEY |
| `imgbb` | Free image hosting via ImgBB API | IMGBB_API_KEY (free) |
| `url` | Pass existing public URL directly | URL already public |

## Files

| File | Purpose |
|------|---------|
| `publish.py` | Main CLI orchestrator |
| `api_client.py` | Blotato API wrapper |
| `quality_gate.py` | 7-dimension post scoring |
| `schedule_ledger.py` | Local scheduling source of truth |
| `media_handler.py` | Image upload with multiple backends |
| `config/publishing_rules.json` | All rules, thresholds, and timing |
| `config/schedule_ledger.json` | Persistent schedule state |

## Configuration

Set in `.env`:
```
BLOTATO_API_KEY=your_key_here
IMGBB_API_KEY=your_key_here  # optional, for imgbb upload method
```

## Integration with Other Skills

- **Content Strategist** → Drafts posts using proven formulas
- **Network Intelligence** → Audience segments inform content targeting
- **POST_PERFORMANCE_PLAYBOOK.md** → Quality gate rules derived from playbook data
- **MASTER_CONTENT_CALENDAR.csv** → Schedule ledger syncs with master calendar
