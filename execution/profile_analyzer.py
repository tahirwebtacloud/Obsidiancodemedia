"""
profile_analyzer.py
-------------------
LLM-powered LinkedIn profile analysis.

Pipeline:
  1. Receives raw Apify scrape output
  2. Sends to LLM with structured prompt
  3. Returns clean structured profile data
  4. Creates vector DB chunks for RAG storage

Structured output schema:
  {
    "profile_picture_url": "...",
    "first_name": "...",
    "last_name": "...",
    "headline": "...",
    "bio": "Detailed professional bio...",
    "skills": ["skill1", "skill2", ...],
    "experiences": [
      {"title": "...", "company": "...", "duration": "...", "description": "...", "location": "..."}
    ],
    "current_company": "...",
    "followers": 0,
    "connections": 0,
    "linkedin_url": "..."
  }
"""

from typing import Dict, List, Optional

from execution.gemini_structured import call_llm_json


# ── Required fields in LLM response ──────────────────────────────────────────
_REQUIRED_FIELDS = ["first_name", "last_name", "headline", "bio"]

# ── System prompt for profile analysis ────────────────────────────────────────
_PROFILE_ANALYSIS_PROMPT = """You are an expert LinkedIn profile analyst. You will receive raw scraped data from a LinkedIn profile. Your job is to analyze all the information and produce a clean, structured profile summary.

You MUST return a JSON object with EXACTLY these fields:
{
  "first_name": "Person's first name",
  "last_name": "Person's last name",
  "headline": "Their professional headline/title exactly as shown",
  "bio": "A detailed 5-8 sentence professional biography. Synthesize their about section, experience, and achievements into a compelling narrative. Include their current role, expertise areas, career trajectory, key accomplishments, and professional focus areas.",
  "skills": ["skill1", "skill2", "skill3"],
  "experiences": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "duration": "Start Date - End Date",
      "description": "Brief description of the role and key responsibilities",
      "location": "City, Country"
    }
  ],
  "current_company": "Their current company name",
  "education": [
    {
      "school": "School Name",
      "degree": "Degree and Field",
      "dates": "Start - End"
    }
  ],
  "key_insights": ["insight1", "insight2", "insight3"]
}

Guidelines:
- bio: Write a rich, detailed professional biography (5-8 sentences). This is the MOST important field — make it comprehensive and engaging. Reference specific roles, companies, expertise areas, and achievements.
- skills: Extract up to 15 relevant skills from the profile. Include both stated skills and implied ones from experience.
- experiences: List up to 8 most recent/relevant positions, most recent first. Include description for each.
- current_company: The company where they currently work.
- education: Up to 3 educational entries.
- key_insights: 3-5 notable insights about this professional (unique expertise, industry focus, leadership style, etc.)

IMPORTANT: Return ONLY the JSON object, no markdown, no explanation."""


def analyze_profile(raw_json: Dict, linkedin_url: str = "") -> Dict:
    """Analyze a raw Apify profile and return structured profile data.

    Args:
        raw_json: Raw Apify scrape response dict.
        linkedin_url: The LinkedIn profile URL.

    Returns:
        Structured profile dict with all fields populated.
    """
    if not raw_json or not isinstance(raw_json, dict):
        return _build_fallback(raw_json or {}, linkedin_url)

    # ── Build the user prompt from raw data ───────────────────────────────────
    parts = []

    name = str(raw_json.get("fullName") or raw_json.get("name") or
               f"{raw_json.get('firstName', '')} {raw_json.get('lastName', '')}").strip()
    if name:
        parts.append(f"Full Name: {name}")

    headline = str(raw_json.get("headline") or raw_json.get("jobTitle") or "").strip()
    if headline:
        parts.append(f"Headline: {headline}")

    about = str(raw_json.get("summary") or raw_json.get("about") or
                raw_json.get("description") or "").strip()
    if about:
        parts.append(f"About/Summary: {about}")

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
        for i, exp in enumerate(experiences[:10]):
            if isinstance(exp, dict):
                title = exp.get("title") or exp.get("jobTitle") or ""
                comp = exp.get("companyName") or exp.get("company") or ""
                desc = exp.get("description") or ""
                duration = exp.get("timePeriod") or exp.get("dateRange") or ""
                loc = exp.get("location") or ""
                parts.append(f"  {i+1}. {title} at {comp} ({duration}){f' - {loc}' if loc else ''}")
                if desc:
                    parts.append(f"     {desc[:300]}")

    # Education
    education = raw_json.get("education") or raw_json.get("schools") or []
    if isinstance(education, list) and education:
        parts.append("\nEducation:")
        for edu in education[:5]:
            if isinstance(edu, dict):
                school = edu.get("schoolName") or edu.get("school") or ""
                degree = edu.get("degree") or edu.get("degreeName") or ""
                field = edu.get("fieldOfStudy") or edu.get("field") or ""
                parts.append(f"  - {degree} {field} from {school}".strip())

    # Skills
    skills = raw_json.get("skills") or []
    if isinstance(skills, list) and skills:
        skill_names = []
        for s in skills[:20]:
            if isinstance(s, dict):
                skill_names.append(s.get("name") or s.get("skill") or "")
            elif isinstance(s, str):
                skill_names.append(s)
        if skill_names:
            parts.append(f"\nSkills: {', '.join(filter(None, skill_names))}")

    # Certifications
    certs = raw_json.get("certifications") or raw_json.get("certificates") or []
    if isinstance(certs, list) and certs:
        parts.append("\nCertifications:")
        for c in certs[:5]:
            if isinstance(c, dict):
                parts.append(f"  - {c.get('name', '')} ({c.get('authority', '')})")

    # Connections/followers
    connections = raw_json.get("connections") or raw_json.get("connectionsCount") or 0
    followers = raw_json.get("followers") or raw_json.get("followersCount") or 0
    if connections:
        parts.append(f"\nConnections: {connections}")
    if followers:
        parts.append(f"Followers: {followers}")

    user_prompt = "\n".join(parts) if parts else "Limited profile data available."

    # ── Call LLM ──────────────────────────────────────────────────────────────
    llm_result = call_llm_json(
        system_prompt=_PROFILE_ANALYSIS_PROMPT,
        user_prompt=user_prompt,
        required_fields=_REQUIRED_FIELDS,
        max_tokens=4000,
        temperature=0.3,
        gemini_primary=True,
    )

    if not llm_result:
        print("[ProfileAnalyzer] LLM returned no result, using fallback")
        return _build_fallback(raw_json, linkedin_url)

    # ── Merge LLM result with raw data (LLM may miss direct fields) ──────────
    profile = _merge_with_raw(llm_result, raw_json, linkedin_url)
    return profile


def _merge_with_raw(llm: Dict, raw: Dict, linkedin_url: str) -> Dict:
    """Merge LLM structured output with raw Apify fields that are direct values."""
    profile = {}

    # Identity — prefer LLM but fall back to raw
    profile["first_name"] = llm.get("first_name") or raw.get("firstName") or ""
    profile["last_name"] = llm.get("last_name") or raw.get("lastName") or ""
    profile["headline"] = llm.get("headline") or raw.get("headline") or raw.get("jobTitle") or ""
    profile["bio"] = llm.get("bio") or raw.get("summary") or raw.get("about") or ""

    # Direct from raw (LLM doesn't generate these)
    profile["profile_picture_url"] = (
        raw.get("profilePic") or raw.get("profilePicture") or raw.get("photo") or
        raw.get("profilePictureUrl") or raw.get("profilePicUrl") or ""
    )
    profile["followers"] = int(raw.get("followers") or raw.get("followersCount") or 0)
    profile["connections"] = int(raw.get("connections") or raw.get("connectionsCount") or 0)
    profile["linkedin_url"] = linkedin_url or raw.get("linkedInUrl") or raw.get("profileUrl") or ""
    profile["location"] = raw.get("location") or raw.get("addressLocality") or ""
    profile["industry"] = raw.get("industry") or ""

    # LLM-enriched fields
    profile["current_company"] = (
        llm.get("current_company") or raw.get("currentCompany") or raw.get("company") or ""
    )
    profile["skills"] = llm.get("skills") if isinstance(llm.get("skills"), list) else []
    profile["experiences"] = llm.get("experiences") if isinstance(llm.get("experiences"), list) else []
    profile["education"] = llm.get("education") if isinstance(llm.get("education"), list) else []
    profile["key_insights"] = llm.get("key_insights") if isinstance(llm.get("key_insights"), list) else []

    return profile


def _build_fallback(raw: Dict, linkedin_url: str) -> Dict:
    """Build a minimal structured profile from raw data when LLM fails."""
    first = str(raw.get("firstName") or "").strip()
    last = str(raw.get("lastName") or "").strip()
    full = str(raw.get("fullName") or f"{first} {last}").strip()
    headline = str(raw.get("headline") or raw.get("jobTitle") or "").strip()
    company = str(raw.get("currentCompany") or raw.get("company") or "").strip()

    bio = str(raw.get("summary") or raw.get("about") or "").strip()
    if not bio and full:
        bio = f"{full} is a professional{f' at {company}' if company else ''}. {headline}"

    # Extract experiences from raw
    raw_exp = raw.get("experiences") or raw.get("positions") or []
    experiences = []
    for exp in raw_exp[:8]:
        if isinstance(exp, dict):
            experiences.append({
                "title": exp.get("title") or exp.get("jobTitle") or "",
                "company": exp.get("companyName") or exp.get("company") or "",
                "duration": exp.get("timePeriod") or exp.get("dateRange") or "",
                "description": exp.get("description") or "",
                "location": exp.get("location") or "",
            })

    # Extract skills from raw
    raw_skills = raw.get("skills") or []
    skills = []
    for s in raw_skills[:15]:
        if isinstance(s, dict):
            skills.append(s.get("name") or s.get("skill") or "")
        elif isinstance(s, str):
            skills.append(s)
    skills = [s for s in skills if s]

    return {
        "first_name": first,
        "last_name": last,
        "headline": headline,
        "bio": bio,
        "profile_picture_url": raw.get("profilePicture") or raw.get("photo") or "",
        "skills": skills,
        "experiences": experiences,
        "current_company": company,
        "followers": int(raw.get("followers") or raw.get("followersCount") or 0),
        "connections": int(raw.get("connections") or raw.get("connectionsCount") or 0),
        "linkedin_url": linkedin_url,
        "location": raw.get("location") or "",
        "industry": raw.get("industry") or "",
        "education": [],
        "key_insights": [],
    }


def create_profile_chunks(profile: Dict) -> List[Dict]:
    """Create vector DB-ready chunks from a structured profile.

    Returns a list of dicts with {content, source_type, metadata} for RAG storage.
    """
    chunks = []
    full_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()

    # Chunk 1: Bio
    bio = profile.get("bio", "")
    if bio:
        chunks.append({
            "content": f"{full_name} - Professional Bio:\n{bio}",
            "source_type": "profile_bio",
            "metadata": {"section": "bio", "name": full_name},
        })

    # Chunk 2: Headline + current role summary
    headline = profile.get("headline", "")
    company = profile.get("current_company", "")
    if headline or company:
        summary_text = f"{full_name} — {headline}"
        if company:
            summary_text += f"\nCurrently at {company}"
        if profile.get("location"):
            summary_text += f"\nBased in {profile['location']}"
        if profile.get("industry"):
            summary_text += f"\nIndustry: {profile['industry']}"
        chunks.append({
            "content": summary_text,
            "source_type": "profile_identity",
            "metadata": {"section": "identity", "name": full_name},
        })

    # Chunk 3-N: Each experience as a separate chunk
    for exp in profile.get("experiences", []):
        if isinstance(exp, dict):
            title = exp.get("title", "")
            comp = exp.get("company", "")
            dur = exp.get("duration", "")
            desc = exp.get("description", "")
            loc = exp.get("location", "")
            exp_text = f"{full_name} — Work Experience:\n{title} at {comp}"
            if dur:
                exp_text += f" ({dur})"
            if loc:
                exp_text += f" — {loc}"
            if desc:
                exp_text += f"\n{desc}"
            chunks.append({
                "content": exp_text,
                "source_type": "profile_experience",
                "metadata": {
                    "section": "experience",
                    "company": comp,
                    "title": title,
                    "name": full_name,
                },
            })

    # Chunk N+1: Skills
    skills = profile.get("skills", [])
    if skills:
        chunks.append({
            "content": f"{full_name} — Professional Skills:\n{', '.join(skills)}",
            "source_type": "profile_skills",
            "metadata": {"section": "skills", "name": full_name},
        })

    # Chunk N+2: Key insights
    insights = profile.get("key_insights", [])
    if insights:
        chunks.append({
            "content": f"{full_name} — Key Professional Insights:\n" + "\n".join(f"• {i}" for i in insights),
            "source_type": "profile_insights",
            "metadata": {"section": "insights", "name": full_name},
        })

    # Chunk N+3: Education
    for edu in profile.get("education", []):
        if isinstance(edu, dict):
            school = edu.get("school", "")
            degree = edu.get("degree", "")
            if school:
                chunks.append({
                    "content": f"{full_name} — Education: {degree} from {school}",
                    "source_type": "profile_education",
                    "metadata": {"section": "education", "school": school, "name": full_name},
                })

    return chunks
