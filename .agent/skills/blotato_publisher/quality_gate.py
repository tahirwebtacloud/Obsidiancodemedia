"""
Quality Gate - Pre-publish checklist enforced from POST_PERFORMANCE_PLAYBOOK.md
Scores posts against the 7-dimension rubric and blocks publishing if below threshold.
"""

import json
import re
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config" / "publishing_rules.json"


def load_rules():
    """Load publishing rules."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


def count_words(text):
    """Count words in text."""
    return len(text.split())


def get_first_line(text):
    """Extract the hook (first non-empty line)."""
    for line in text.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def check_elements(text):
    """
    Detect which content elements are present.
    Returns dict of element -> bool.
    """
    text_lower = text.lower()

    elements = {
        "personal_story": False,
        "identity_challenge": False,
        "money_promise": False,
        "visual_asset": False,  # Can't detect from text alone, checked separately
        "named_framework": False,
        "specific_math": False,
        "cta_present": False,
        "quotable_closer": False,
    }

    # Personal story signals
    personal_signals = [
        r"\bi\s+(was|had|used|thought|realized|learned|tried|started|built|made|ran)\b",
        r"\bmy\s+(business|company|team|morning|list|workflow)\b",
        r"\byears?\s+(ago|later)\b",
        r"\bI've been\b",
    ]
    for sig in personal_signals:
        if re.search(sig, text_lower):
            elements["personal_story"] = True
            break

    # Identity challenge signals
    identity_signals = [
        r"\byou('re| are)\s+(not|still|probably)\b",
        r"\bmost (people|founders|ceos|leaders)\b",
        r"\bstop\s+(doing|thinking|being)\b",
        r"\bif you('re| are) still\b",
        r"\bthe (hardest|smartest|busiest)\b",
        r"\bhonest (question|truth)\b",
    ]
    for sig in identity_signals:
        if re.search(sig, text_lower):
            elements["identity_challenge"] = True
            break

    # Money/dollar promise
    if re.search(r"\$\d+[KkMm]?", text):
        elements["money_promise"] = True
    if re.search(r"\b\d+\s*(hours?|hrs?)\s*(saved|back|recovered|per)", text_lower):
        elements["money_promise"] = True

    # Named framework (numbered steps with bold or caps)
    if re.search(r"(1\.|step\s*1|#1)\s*.*\n.*(2\.|step\s*2|#2)", text_lower):
        elements["named_framework"] = True
    if re.search(r'the\s+\w+\s+(test|audit|method|framework|stack|rule|formula)', text_lower):
        elements["named_framework"] = True

    # Specific math
    if re.search(r"\$\d[\d,]*\s*(/|per)\s*(year|yr|month|mo|week|day|hour|hr)", text_lower):
        elements["specific_math"] = True
    if re.search(r"\d+\s*(hours?|minutes?|hrs?|mins?)\s*(saved|back|recovered)", text_lower):
        elements["specific_math"] = True
    if re.search(r"\d+\s*out\s*of\s*\d+", text_lower):
        elements["specific_math"] = True

    # CTA detection
    cta_signals = [
        r"\bcomment\b.*\b(below|if|your|what)\b",
        r"\bDM\s+me\b",
        r"\bwhat('s| is)\s+(the one|your)\b.*\?",
        r"\brepost\b",
        r"\bfollow\s+(along|me|for)\b",
        r"\bwhere\s+are\s+you\b",
        r"\bhonest\s+question\b",
    ]
    for sig in cta_signals:
        if re.search(sig, text_lower):
            elements["cta_present"] = True
            break

    # Quotable closer (short punchy last sentence)
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    # Find last non-CTA, non-hashtag line
    for line in reversed(lines):
        if line.startswith("#") or line.startswith("Comment") or "DM me" in line:
            continue
        if count_words(line) <= 15 and count_words(line) >= 4:
            elements["quotable_closer"] = True
        break

    return elements


def score_post(text, has_image=False, scheduled_optimal=True):
    """
    Score a post against the 7-dimension rubric.

    Returns:
        dict with scores, total, passed (bool), and feedback
    """
    rules = load_rules()
    rubric = rules["quality_gate"]["scoring_rubric"]
    min_score = rules["quality_gate"]["min_score"]
    elements = check_elements(text)
    hook = get_first_line(text)
    char_count = len(text)
    hook_words = count_words(hook)

    scores = {}
    feedback = []

    # 1. Hook Power (0-5)
    hook_score = 1  # Base: has a first line
    if elements["identity_challenge"]:
        hook_score += 2
    if elements["money_promise"] and re.search(r"\$", hook):
        hook_score += 1
    if hook_words <= 12:
        hook_score += 1
    else:
        feedback.append(f"Hook is {hook_words} words — aim for 12 or fewer")
    scores["hook_power"] = min(hook_score, 5)

    # 2. Vulnerability (0-5)
    vuln_score = 0
    if elements["personal_story"]:
        vuln_score += 3
    if re.search(r"\b(I thought|I was wrong|turns out|uncomfortable|hurts|guilt)\b", text.lower()):
        vuln_score += 2
    scores["vulnerability"] = min(vuln_score, 5)
    if vuln_score == 0:
        feedback.append("No personal story detected — add 'I was/I thought/I realized' element")

    # 3. Framework (0-5)
    fw_score = 0
    if elements["named_framework"]:
        fw_score += 4
    if re.search(r"(1\.|step\s*1).*(2\.|step\s*2).*(3\.|step\s*3)", text.lower(), re.DOTALL):
        fw_score += 1
    scores["framework"] = min(fw_score, 5)

    # 4. Math/Proof (0-5)
    math_score = 0
    if elements["money_promise"]:
        math_score += 2
    if elements["specific_math"]:
        math_score += 3
    scores["math_proof"] = min(math_score, 5)

    # 5. CTA (0-5)
    cta_score = 0
    if elements["cta_present"]:
        cta_score += 4
    if elements["quotable_closer"]:
        cta_score += 1
    scores["cta"] = min(cta_score, 5)
    if not elements["cta_present"]:
        feedback.append("No CTA detected — add a question, DM hook, or repost nudge")

    # 6. Visual (0-5)
    vis_score = 0
    if has_image:
        vis_score = 5
    else:
        feedback.append("No image attached — posts with images get 5-10x more reactions")
    scores["visual"] = vis_score

    # 7. Timing (0-5)
    scores["timing"] = 5 if scheduled_optimal else 2
    if not scheduled_optimal:
        feedback.append("Not scheduled for optimal window (Tue/Wed 4-5 PM ET)")

    # Total
    total = sum(scores.values())
    passed = total >= min_score

    # Anti-pattern check
    has_required = any([
        elements["personal_story"],
        elements["identity_challenge"],
        elements["money_promise"],
        has_image,
    ])
    if not has_required:
        passed = False
        feedback.insert(0, "BLOCKED: Post has none of: personal story, identity challenge, money promise, or visual. This matches the 'Generic Expert' anti-pattern.")

    # Character count check
    min_chars = rules["quality_gate"]["required_elements"]["min_character_count"]
    max_chars = rules["quality_gate"]["required_elements"]["max_character_count"]
    if char_count < min_chars:
        feedback.append(f"Post is only {char_count} chars — minimum {min_chars} for substance")
    if char_count > max_chars:
        feedback.append(f"Post is {char_count} chars — maximum {max_chars} for LinkedIn readability")

    return {
        "scores": scores,
        "total": total,
        "max_possible": 35,
        "threshold": min_score,
        "passed": passed,
        "elements_detected": elements,
        "feedback": feedback,
        "character_count": char_count,
    }


def format_scorecard(result):
    """Format score result as a readable report."""
    lines = []
    lines.append("=" * 50)
    lines.append("  PRE-PUBLISH QUALITY GATE")
    lines.append("=" * 50)
    lines.append("")

    for dim, score in result["scores"].items():
        bar = "#" * score + "." * (5 - score)
        label = dim.replace("_", " ").title()
        lines.append(f"  {label:<16} [{bar}] {score}/5")

    lines.append("")
    lines.append(f"  TOTAL: {result['total']}/{result['max_possible']}  (threshold: {result['threshold']})")
    lines.append(f"  STATUS: {'PASSED' if result['passed'] else 'BLOCKED'}")
    lines.append(f"  Characters: {result['character_count']}")
    lines.append("")

    if result["feedback"]:
        lines.append("  Feedback:")
        for fb in result["feedback"]:
            lines.append(f"    - {fb}")
        lines.append("")

    elements = result["elements_detected"]
    detected = [k for k, v in elements.items() if v]
    missing = [k for k, v in elements.items() if not v]
    lines.append(f"  Detected: {', '.join(detected) if detected else 'None'}")
    lines.append(f"  Missing:  {', '.join(missing) if missing else 'None'}")
    lines.append("")
    lines.append("=" * 50)

    return "\n".join(lines)


if __name__ == "__main__":
    # Test with the Task Audit post
    test_post = """17 tasks on a handwritten list. 13 done by end of day. And it exposed a $100K problem I didn't know I had.

I've been running task lists the same way for 20 years. Write it down. Stare at it. Cherry-pick the easy ones. Push the hard ones to tomorrow. Repeat until guilt kicks in. I thought that was discipline. Turns out it was the most expensive habit in my business.

Yesterday I handed my entire 17-item list to an AI co-worker. Not to "automate" it. To expose where I was wasting the most money by doing things manually.

Here's what came back — and this is where it gets uncomfortable:

1. The Sort Nobody Wants to See
I asked the AI to categorize every task by: Can it do 80% of this? Or am I the bottleneck?
11 of 17 came back as "AI can handle most of this." I'd been hoarding work that didn't need me.

2. The $200/hr Test
For each task I was doing manually, I ran the math. A custom analytics tool I'd been avoiding? Built in 2.5 hours with AI — plain language, no framework debates. A server security review? AI wrote the hardening scripts AND tested them. Time I would have spent: 8+ hours. Time it actually took: 90 minutes.

3. The Handoff That Hurts
The real insight wasn't what got done. It was what I'd been protecting. Research I could have delegated weeks ago. Workflows I was "going to get to." The list didn't show me 17 tasks — it showed me 17 decisions I'd been avoiding.

Back of the napkin:
6 hours saved in one day. Conservatively.
That's 30 hours/week if I commit to this workflow.
1,500 hours/year.
At $200/hr, that's $300K in recovered capacity.
Even at half that, it's more than most people's salary.

The real reason I tried this? The tasks just keep getting added to the list and I had to knock some of them out. I'm very pleased with the outcome.

Your task list isn't a to-do list. It's a P&L statement you've been ignoring.

What's the one task you keep pushing to tomorrow that you'd want AI to handle today?"""

    result = score_post(test_post, has_image=True, scheduled_optimal=True)
    print(format_scorecard(result))
