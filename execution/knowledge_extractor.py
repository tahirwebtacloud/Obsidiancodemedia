"""
Knowledge Extractor Module
Structured extraction of persona, brand, and product knowledge from LinkedIn data + Brand Assets.
"""

import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


def _safe_text(value: Any, max_len: int = 1200) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    if max_len and len(text) > max_len:
        return text[:max_len].rstrip() + "..."
    return text


def _safe_list(value: Any, max_items: int = 12) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    cleaned = []
    for item in value:
        item_text = _safe_text(item, max_len=200)
        if item_text:
            cleaned.append(item_text)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _summarize_linkedin(linkedin_data: Dict[str, Any]) -> Dict[str, Any]:
    profile = linkedin_data.get("profile")
    positions = linkedin_data.get("positions") or []
    shares = linkedin_data.get("shares") or []

    profile_summary = {}
    if profile:
        profile_summary = {
            "full_name": _safe_text(getattr(profile, "full_name", ""), 120),
            "headline": _safe_text(getattr(profile, "headline", ""), 200),
            "summary": _safe_text(getattr(profile, "summary", ""), 1000),
            "industry": _safe_text(getattr(profile, "industry", ""), 120),
            "location": _safe_text(getattr(profile, "location", ""), 120),
        }

    positions_summary = []
    for pos in positions[:6]:
        positions_summary.append({
            "title": _safe_text(getattr(pos, "title", ""), 120),
            "company": _safe_text(getattr(pos, "company", ""), 120),
            "description": _safe_text(getattr(pos, "description", ""), 600),
            "is_current": bool(getattr(pos, "is_current", False)),
        })

    shares_summary = []
    for share in shares[:8]:
        content = _safe_text(getattr(share, "content", ""), 600)
        if content:
            shares_summary.append({
                "date": _safe_text(getattr(share, "date", ""), 60),
                "content": content,
                "engagement": getattr(share, "engagement_count", 0),
            })

    return {
        "profile": profile_summary,
        "career_summary": _safe_text(linkedin_data.get("career_summary", ""), 600),
        "positions": positions_summary,
        "shares": shares_summary,
    }


def extract_structured_knowledge(
    linkedin_data: Dict[str, Any],
    brand_assets: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Use Gemini to extract structured persona/brand/product knowledge.
    Returns a JSON-compatible dictionary with keys:
    - persona
    - brand
    - products_services
    - knowledge_chunks
    """
    api_key = api_key or os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        return {}

    brand_assets = brand_assets or {}
    linkedin_summary = _summarize_linkedin(linkedin_data)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")

        prompt = f"""You are a senior brand strategist and knowledge extractor.
Return ONLY valid JSON using this exact schema:

{{
  "persona": {{
    "professional_bio": "",
    "tone_of_voice": "",
    "writing_style_rules": [""],
    "core_skills": [""],
    "expertise_areas": [""],
    "target_icp": "",
    "mission": "",
    "values": [""],
    "credibility_points": [""]
  }},
  "brand": {{
    "brand_name": "",
    "tagline": "",
    "description": "",
    "tone_of_voice": "",
    "visual_style": "",
    "positioning": "",
    "value_props": [""],
    "target_audience": ""
  }},
  "products_services": [
    {{"name": "", "description": "", "benefit": "", "target_user": ""}}
  ],
  "knowledge_chunks": [
    {{"category": "persona_story|brand_knowledge|product_knowledge|audience_pain|positioning", "title": "", "content": "", "source": "linkedin|brand_assets"}}
  ]
}}

Rules:
- Keep writing_style_rules to 6 items max.
- Keep core_skills/expertise_areas/values/credibility_points/value_props to 10 items max.
- knowledge_chunks: 8-20 items, each 1-3 sentences max.
- If data is missing, return empty strings/arrays (no hallucinated facts).

LINKEDIN DATA SUMMARY:
{json.dumps(linkedin_summary, ensure_ascii=False, indent=2)}

BRAND ASSETS (if available):
{json.dumps(brand_assets, ensure_ascii=False, indent=2)}
"""

        response = client.models.generate_content(
            model=model,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            ),
            contents=prompt,
        )

        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
            text = text.replace("json\n", "", 1).strip()

        data = {}
        if text:
            try:
                data = json.loads(text)
            except Exception:
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    try:
                        data = json.loads(text[start:end + 1])
                    except Exception:
                        data = {}
        if not isinstance(data, dict):
            return {}
        return data

    except Exception as e:
        if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
            return {"_quota_exhausted": True}
        print(f"[KnowledgeExtractor] Error: {e}")
        return {}
