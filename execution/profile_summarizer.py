"""
profile_summarizer.py
---------------------
Generate structured profile summaries via LLM for LinkedIn profiles.

Used for:
  1. User's own profile (displayed on Voice Engine tab)
  2. Contact profiles (used as context for CRM analysis)

Output schema:
  {
    "executive_summary": "7-sentence professional summary",
    "key_points": ["point_1", ..., "point_10"],
    "experiences": [{"title","company","duration","description"}],
    "action_items": ["item_1", ...]
  }

Uses OpenRouter (free) as primary, Gemini as fallback.
"""

from typing import Dict, List, Optional

from execution.gemini_structured import call_llm_json


_REQUIRED_FIELDS = ["executive_summary", "key_points"]

_SYSTEM_PROMPT = """You are an expert professional profile analyst. Given a LinkedIn profile's raw data, produce a structured summary.

You MUST return a JSON object with EXACTLY these fields:
{
  "executive_summary": "A 5-7 sentence professional summary of this person. Include their current role, expertise areas, career trajectory, and notable achievements.",
  "key_points": ["point_1", "point_2", ..., "point_10"],
  "experiences": [
    {"title": "Job Title", "company": "Company Name", "duration": "Start - End", "description": "Brief role description"}
  ],
  "action_items": ["Potential collaboration area 1", "Potential collaboration area 2"]
}

Guidelines:
- executive_summary: 5-7 sentences, professional tone, no fluff
- key_points: 5-10 bullet points about expertise, skills, industry focus
- experiences: Extract from work history, most recent first, max 5
- action_items: 2-4 suggestions for how to engage/collaborate with this person

IMPORTANT: Return ONLY the JSON object, no markdown, no explanation."""

_BRIEF_SYSTEM_PROMPT = """You are an expert professional profile analyst. Given limited LinkedIn connection data, produce a brief structured summary.

Return a JSON object:
{
  "executive_summary": "2-3 sentence summary based on available info.",
  "key_points": ["point_1", "point_2", "point_3"],
  "experiences": [],
  "action_items": ["Potential area of engagement"]
}

IMPORTANT: Return ONLY the JSON object."""


def summarize_profile(raw_json: Dict, is_brief: bool = False) -> Dict:
    """Generate a structured summary from Apify scrape data or connection info.

    Args:
        raw_json: Full Apify profile response OR connection dict.
        is_brief: If True, use brief prompt (for connection-only contacts).

    Returns:
        Structured summary dict, or minimal fallback on failure.
    """
    # Build user prompt from available data
    parts = []

    name = str(raw_json.get("fullName") or raw_json.get("name") or
               f"{raw_json.get('firstName', '')} {raw_json.get('lastName', '')}").strip()
    if name:
        parts.append(f"Name: {name}")

    headline = str(raw_json.get("headline") or raw_json.get("jobTitle") or "").strip()
    if headline:
        parts.append(f"Headline: {headline}")

    summary_text = str(raw_json.get("summary") or raw_json.get("about") or "").strip()
    if summary_text:
        parts.append(f"About: {summary_text}")

    company = str(raw_json.get("currentCompany") or raw_json.get("company") or "").strip()
    if company:
        parts.append(f"Current Company: {company}")

    industry = str(raw_json.get("industry") or "").strip()
    if industry:
        parts.append(f"Industry: {industry}")

    location = str(raw_json.get("location") or raw_json.get("addressLocality") or "").strip()
    if location:
        parts.append(f"Location: {location}")

    # Work experiences
    experiences = raw_json.get("experiences") or raw_json.get("positions") or []
    if isinstance(experiences, list) and experiences:
        parts.append("\nWork Experience:")
        for i, exp in enumerate(experiences[:7]):
            if isinstance(exp, dict):
                title = exp.get("title") or exp.get("jobTitle") or ""
                comp = exp.get("companyName") or exp.get("company") or ""
                desc = exp.get("description") or ""
                duration = exp.get("timePeriod") or exp.get("dateRange") or ""
                parts.append(f"  {i+1}. {title} at {comp} ({duration})")
                if desc:
                    parts.append(f"     {desc[:200]}")

    # Education
    education = raw_json.get("education") or raw_json.get("schools") or []
    if isinstance(education, list) and education:
        parts.append("\nEducation:")
        for edu in education[:3]:
            if isinstance(edu, dict):
                school = edu.get("schoolName") or edu.get("school") or ""
                degree = edu.get("degree") or edu.get("degreeName") or ""
                parts.append(f"  - {degree} from {school}")

    # Skills
    skills = raw_json.get("skills") or []
    if isinstance(skills, list) and skills:
        skill_names = []
        for s in skills[:15]:
            if isinstance(s, dict):
                skill_names.append(s.get("name") or s.get("skill") or "")
            elif isinstance(s, str):
                skill_names.append(s)
        if skill_names:
            parts.append(f"\nSkills: {', '.join(filter(None, skill_names))}")

    user_prompt = "\n".join(parts) if parts else "Limited profile data available."

    system = _BRIEF_SYSTEM_PROMPT if is_brief else _SYSTEM_PROMPT
    result = call_llm_json(
        system_prompt=system,
        user_prompt=user_prompt,
        required_fields=_REQUIRED_FIELDS,
        max_tokens=2000,
        temperature=0.3,
        gemini_primary=True,
    )

    if result:
        # Ensure list fields
        if not isinstance(result.get("key_points"), list):
            result["key_points"] = []
        if not isinstance(result.get("experiences"), list):
            result["experiences"] = []
        if not isinstance(result.get("action_items"), list):
            result["action_items"] = []
        return result

    # Fallback: build minimal summary from raw data
    return {
        "executive_summary": f"{name} is a professional{f' at {company}' if company else ''}{f' in the {industry} industry' if industry else ''}. {headline}" if name else "Profile data unavailable.",
        "key_points": [headline] if headline else ["No profile details available"],
        "experiences": [],
        "action_items": ["Connect and explore collaboration opportunities"],
    }


def get_summary_text(summary: Dict) -> str:
    """Extract a plain text version of the summary for use in prompts."""
    if not summary:
        return ""
    parts = []
    exec_summary = summary.get("executive_summary", "")
    if exec_summary:
        parts.append(exec_summary)
    key_points = summary.get("key_points", [])
    if key_points:
        parts.append("Key points: " + "; ".join(key_points[:5]))
    return "\n".join(parts)
