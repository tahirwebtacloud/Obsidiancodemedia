"""
conversation_analyzer.py
------------------------
LLM-powered analysis of LinkedIn conversations and connections for CRM classification.

Two entry points:
  1. analyze_conversation() — For contacts WITH message threads
  2. analyze_connection() — For connection-only contacts (no messages)

Both return a structured CRM record dict with:
  - first_name, last_name, title, company, industry
  - years_of_experience, intent_points (3 bullets), score (0-100), tag

Uses OpenRouter (free) as primary, Gemini as fallback via gemini_structured.py.
Includes rule-based fallback when both LLM providers fail.
"""

import re
from typing import Dict, List, Optional

from execution.gemini_structured import call_llm_json


# ─── Schema fields required in every LLM response ─────────────────────────────
_REQUIRED_FIELDS = ["intent_points", "score", "tag"]

# ─── Valid tags ────────────────────────────────────────────────────────────────
_VALID_TAGS = {"warm", "cold", "hot", "ghosted", "referrer", "prospect", "client", "unanalyzed"}

# ─── System prompt for conversation analysis ──────────────────────────────────
_CONVERSATION_SYSTEM_PROMPT = """You are an expert B2B sales intelligence analyst. You analyze LinkedIn conversation threads to classify contacts for a CRM system.

Given:
- The user's profile summary and products/services
- The contact's profile information
- The full conversation thread between them

You MUST return a JSON object with EXACTLY these fields:
{
  "first_name": "string",
  "last_name": "string",
  "title": "string (job title)",
  "company": "string",
  "industry": "string",
  "years_of_experience": number,
  "intent_points": ["answer1", "answer2", "answer3"],
  "score": number (0-100, likelihood to buy/engage),
  "tag": "one of: warm|cold|hot|ghosted|referrer|prospect|client"
}

Tag definitions:
- hot: Actively discussing business, requesting proposals, showing buying signals
- warm: Engaged in meaningful conversation, showing interest in services
- cold: Initial outreach, no meaningful engagement yet
- ghosted: Was engaged but stopped responding (last 3+ messages unanswered)
- referrer: Refers others or makes introductions
- prospect: Connected but no business discussion yet
- client: Already doing business together

Score guidelines:
- 80-100: Active buying signals, requesting proposals/demos
- 60-79: Engaged, asking questions about services
- 40-59: Some interest, general conversation
- 20-39: Minimal engagement, cold outreach
- 0-19: No engagement, connection only

intent_points: EXACTLY 3 answers to these questions (one answer per question, be specific and reference actual conversation content or profile details):
1. "How is this lead a good fit for our product/service?" — Explain the alignment between the contact's role, company, or needs and what the user offers.
2. "Why should we contact this lead?" — Highlight the positive qualities, engagement signals, or opportunities visible in their LinkedIn profile or conversation.
3. "Should we ignore this lead, and why or why not?" — Give a clear recommendation with reasoning (e.g. high potential, low engagement, irrelevant industry, etc.).

Each answer should be 1-2 sentences, specific to this contact. Do NOT use generic phrases like "Mutual engagement" or "Potential opportunity". Reference actual details from the conversation or profile.

IMPORTANT: Return ONLY the JSON object, no markdown, no explanation."""

# ─── System prompt for connection-only analysis ───────────────────────────────
_CONNECTION_SYSTEM_PROMPT = """You are an expert B2B sales intelligence analyst. You analyze LinkedIn connection profiles to classify them for a CRM system.

Given:
- The user's profile summary and products/services
- The contact's profile information (name, title, company, industry)
- The connection date

You MUST return a JSON object with EXACTLY these fields:
{
  "first_name": "string",
  "last_name": "string",
  "title": "string (job title)",
  "company": "string",
  "industry": "string",
  "years_of_experience": number,
  "intent_points": ["answer1", "answer2", "answer3"],
  "score": number (0-100),
  "tag": "one of: warm|cold|hot|ghosted|referrer|prospect|client"
}

Since there is no conversation, score should be 10-30 (prospect/cold range).

intent_points: EXACTLY 3 answers to these questions (one answer per question, be specific and reference actual profile details):
1. "How is this lead a good fit for our product/service?" — Explain alignment between contact's role/company and user's offerings based on available profile info.
2. "Why should we contact this lead?" — Highlight positive qualities or opportunities visible from their LinkedIn profile (title, company, industry).
3. "Should we ignore this lead, and why or why not?" — Give a clear recommendation based on profile relevance and potential.

Each answer should be 1-2 sentences. Do NOT use generic phrases. Reference the contact's actual title, company, or industry.

IMPORTANT: Return ONLY the JSON object, no markdown, no explanation."""


def _format_thread(thread: List[Dict], max_messages: int = 30) -> str:
    """Format a conversation thread for the LLM prompt."""
    if not thread:
        return "(No messages)"

    # Take most recent messages if thread is very long
    messages = thread[-max_messages:] if len(thread) > max_messages else thread
    lines = []
    for msg in messages:
        sender = msg.get("from", "Unknown")
        date = msg.get("date", "")
        content = msg.get("content", "")
        if content:
            lines.append(f"[{date}] {sender}: {content}")
    return "\n".join(lines) if lines else "(No message content)"


def _validate_and_fix(result: Dict, contact_info: Dict) -> Dict:
    """Validate and fix the LLM output, filling in missing fields."""
    # Ensure tag is valid
    tag = str(result.get("tag", "prospect")).lower().strip()
    if tag not in _VALID_TAGS:
        tag = "prospect"
    result["tag"] = tag

    # Clamp score
    try:
        score = int(result.get("score", 0))
    except (ValueError, TypeError):
        score = 0
    result["score"] = max(0, min(100, score))

    # Ensure intent_points is a list of 3
    points = result.get("intent_points", [])
    if not isinstance(points, list):
        points = [str(points)] if points else []
    while len(points) < 3:
        points.append("No additional intent detected")
    result["intent_points"] = points[:3]

    # Fill identity fields from contact_info if LLM missed them
    for field in ("first_name", "last_name", "title", "company", "industry"):
        if not result.get(field):
            result[field] = contact_info.get(field, "")

    # Years of experience
    try:
        result["years_of_experience"] = int(result.get("years_of_experience", 0))
    except (ValueError, TypeError):
        result["years_of_experience"] = 0

    return result


def _unanalyzed_record(contact_info: Dict, reason: str = "LLM unavailable") -> Dict:
    """Return a placeholder record when all LLM providers fail.

    The contact is saved with tag='unanalyzed' and score=0 so it can be
    identified and re-analyzed later when LLM capacity is restored.
    """
    return {
        "first_name": contact_info.get("first_name", ""),
        "last_name": contact_info.get("last_name", ""),
        "title": contact_info.get("title", ""),
        "company": contact_info.get("company", ""),
        "industry": contact_info.get("industry", ""),
        "years_of_experience": contact_info.get("years_of_experience", 0),
        "intent_points": [
            f"Pending AI analysis — {reason}.",
            "This contact will be automatically re-analyzed when LLM capacity is restored.",
            "No scoring or classification has been performed yet.",
        ],
        "score": 0,
        "tag": "unanalyzed",
    }


def analyze_conversation(
    user_summary: str,
    user_products: str,
    contact_info: Dict,
    thread: List[Dict],
    quick_fail: bool = False,
) -> Dict:
    """Analyze a LinkedIn conversation thread via LLM.

    Args:
        user_summary: User's own profile summary text.
        user_products: User's products/services description.
        contact_info: Dict with first_name, last_name, title, company, etc.
        thread: List of message dicts [{from, to, date, content}, ...].
        quick_fail: If True, skip LLM waits on rate limit (bulk mode).

    Returns:
        Validated CRM record dict.
    """
    # Build user prompt
    contact_desc = (
        f"Name: {contact_info.get('first_name', '')} {contact_info.get('last_name', '')}\n"
        f"Title: {contact_info.get('title', '')}\n"
        f"Company: {contact_info.get('company', '')}\n"
        f"Industry: {contact_info.get('industry', '')}"
    )

    user_prompt = (
        f"## User Profile\n{user_summary}\n\n"
        f"## User Products/Services\n{user_products}\n\n"
        f"## Contact Profile\n{contact_desc}\n\n"
        f"## Conversation Thread ({len(thread)} messages)\n{_format_thread(thread)}"
    )

    result = call_llm_json(
        system_prompt=_CONVERSATION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        required_fields=_REQUIRED_FIELDS,
        max_tokens=800,
        temperature=0.2,
        quick_fail=quick_fail,
    )

    if result:
        return _validate_and_fix(result, contact_info)

    # LLM failed — mark as unanalyzed for later retry
    print(f"[Analyzer] LLM failed for conversation — marking as unanalyzed")
    return _unanalyzed_record(contact_info, reason="All LLM providers failed during conversation analysis")


def analyze_connection(
    user_summary: str,
    user_products: str,
    contact_info: Dict,
    quick_fail: bool = False,
) -> Dict:
    """Analyze a connection-only contact (no messages) via LLM.

    Args:
        user_summary: User's own profile summary text.
        user_products: User's products/services description.
        contact_info: Dict with first_name, last_name, title, company, connected_on.
        quick_fail: If True, skip LLM waits on rate limit (bulk mode).

    Returns:
        Validated CRM record dict.
    """
    contact_desc = (
        f"Name: {contact_info.get('first_name', '')} {contact_info.get('last_name', '')}\n"
        f"Title: {contact_info.get('title', '')}\n"
        f"Company: {contact_info.get('company', '')}\n"
        f"Industry: {contact_info.get('industry', '')}\n"
        f"Connected On: {contact_info.get('connected_on', '')}"
    )

    user_prompt = (
        f"## User Profile\n{user_summary}\n\n"
        f"## User Products/Services\n{user_products}\n\n"
        f"## Contact Profile (Connection Only — No Messages)\n{contact_desc}"
    )

    result = call_llm_json(
        system_prompt=_CONNECTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        required_fields=_REQUIRED_FIELDS,
        max_tokens=600,
        temperature=0.2,
        quick_fail=quick_fail,
    )

    if result:
        return _validate_and_fix(result, contact_info)

    # LLM failed — mark as unanalyzed for later retry
    print(f"[Analyzer] LLM failed for connection — marking as unanalyzed")
    return _unanalyzed_record(contact_info, reason="All LLM providers failed during connection analysis")
