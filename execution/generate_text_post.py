"""
generate_text_post.py
------------------
Core content generation module supporting 128 distinct configurations.

Generation Flow (6 steps):
  1. Load directive — purpose-specific system prompt from directives/{purpose}_caption.md
  2. Load user context — tenant persona + brand from Supabase (via --user_id)
  3. Build visual parts — download images, transcribe videos, extract metadata
  4. Construct mega prompt — combine directive, persona, brand, visual context, aspect rules
  5. Call Gemini LLM — multimodal generation with structured output
  6. Generate image (optional) — if visual_aspect == "image", call Gemini image model

Outputs:
  - .tmp/final_plan.json — generated caption, single_point, image_prompt, asset_url
  - stdout markers — ">>>STAGE:text_start", ">>>STAGE:text_done", etc. for SSE streaming

Routing:
  - orchestrator.py routes here for all non-carousel generations
  - Purpose types: educational (Breakdown), storytelling (Announcement), authority (Money Math), promotional (ID-Challenge)
  - Visual aspects: none, image, video, carousel (carousel routes to generate_carousel.py)
"""

import os
import json
import argparse
import requests
import sys
import io
import re
import random
from typing import Any, Dict, List

def sanitize_untrusted_input(text: str, max_len: int = 50000) -> str:
    """Strip control characters and cap length for user-supplied text injected into prompts."""
    if not isinstance(text, str):
        return ""
    # Remove ASCII control chars except newline/tab
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return cleaned[:max_len]

def _configure_utf8_stdio() -> None:
    """Force UTF-8 stdio for Windows CLI runs without mutating import-time streams."""
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True, write_through=True)
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True, write_through=True)
    except Exception:
        # Keep existing stdio streams if wrapping is not possible.
        pass

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from google import genai
from google.genai import types


def _normalize_text_list(value: Any) -> List[str]:
    """Normalize unknown list-like values into clean string arrays."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if str(v).strip()]
            except Exception:
                pass
        parts = re.split(r"[\n,;]", raw)
        return [p.strip(" \t-•") for p in parts if p.strip(" \t-•")]
    return []


def _safe_text(value: Any, max_len: int = 2000) -> str:
    text = str(value or "").strip()
    return text[:max_len] if text else ""


# ═══════════════════════════════════════════════════════════════════════════════
# HOOK & CTA LIBRARIES — Index-Based Selection via Function Calling
# The generation LLM sees only the INDEX (category descriptions) in the prompt.
# It then calls get_hook_library / get_cta_library tools to load just the
# ONE best-fit file, keeping the prompt focused and token-efficient.
# Files live in directives/hooks/ and directives/ctas/.
# ═══════════════════════════════════════════════════════════════════════════════
def _discover_library_files(library_dir: str) -> List[str]:
    """Discover library markdown files dynamically (excluding INDEX.md)."""
    if not os.path.isdir(library_dir):
        return []

    discovered = []
    for name in os.listdir(library_dir):
        if not name.lower().endswith(".md"):
            continue
        if name.upper() == "INDEX.MD":
            continue
        discovered.append(os.path.splitext(name)[0])

    # Stable ordering avoids random enum order changes between runs.
    return sorted(discovered)


_HOOK_LIBRARY_FILES = _discover_library_files("directives/hooks")
_CTA_LIBRARY_FILES = _discover_library_files("directives/ctas")


def _load_library_indexes() -> str:
    """Load only the INDEX files for hooks and CTAs.

    The LLM sees category descriptions and uses function calling
    to load just the one file it needs. Saves ~20k tokens per request
    compared to loading all 15 library files.
    """
    sections = []

    hook_index_path = "directives/hooks/INDEX.md"
    if os.path.exists(hook_index_path):
        with open(hook_index_path, "r", encoding="utf-8") as f:
            hook_index = f.read().strip()
        hook_count = len(_HOOK_LIBRARY_FILES)
        sections.append(
            "## HOOKS LIBRARY — INDEX\n"
            f"You have access to {hook_count} hook category files via the `get_hook_library` tool.\n"
            "Your job:\n"
            "1. Read the index table below to understand what each category offers\n"
            "2. Based on the TOPIC, RESEARCH, and POST PURPOSE, identify the ONE "
            "best-fit category\n"
            "3. Call the `get_hook_library` tool with that filename to load the "
            "full templates\n"
            "4. Read ALL templates in the loaded file carefully.\n"
            "5. Select the ONE template that creates the strongest, most contextually relevant opening for this specific post. Do NOT just pick the first one blindly.\n\n"
            + hook_index
        )

    cta_index_path = "directives/ctas/INDEX.md"
    if os.path.exists(cta_index_path):
        with open(cta_index_path, "r", encoding="utf-8") as f:
            cta_index = f.read().strip()
        cta_count = len(_CTA_LIBRARY_FILES)
        sections.append(
            "## CTA LIBRARY — INDEX\n"
            f"You have access to {cta_count} CTA category files via the `get_cta_library` tool.\n"
            "Your job:\n"
            "1. Read the index table below to understand what each category offers\n"
            "2. AFTER deciding on the hook and body direction, identify the ONE "
            "best-fit CTA category for the post's goal\n"
            "3. Call the `get_cta_library` tool with that filename to load the "
            "full templates\n"
            "4. Read ALL templates in the loaded file carefully.\n"
            "5. Select the ONE template that forms the most natural, contextually appropriate conclusion for this specific post. Do NOT just pick the first one blindly.\n\n"
            + cta_index
        )

    return "\n\n---\n\n".join(sections)


def _handle_library_tool_call(fn_name: str, fn_args: dict) -> str:
    """Handle get_hook_library / get_cta_library tool calls from the LLM.

    Reads the requested library file and returns its full content so the
    LLM can pick and adapt a specific template.
    """
    filename = fn_args.get("filename", "")

    if fn_name == "get_hook_library":
        if filename not in _HOOK_LIBRARY_FILES:
            return f"Error: Unknown hook library '{filename}'. Valid: {_HOOK_LIBRARY_FILES}"
        fpath = f"directives/hooks/{filename}.md"
    elif fn_name == "get_cta_library":
        if filename not in _CTA_LIBRARY_FILES:
            return f"Error: Unknown CTA library '{filename}'. Valid: {_CTA_LIBRARY_FILES}"
        fpath = f"directives/ctas/{filename}.md"
    else:
        return f"Error: Unknown tool '{fn_name}'"

    if not os.path.exists(fpath):
        return f"Error: File not found: {fpath}"

    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read().strip()

    print(f">>> Tool call: {fn_name}('{filename}') — loaded {len(content)} chars")
    return content


def get_tool_declarations(include_lead_magnet=False):
    funcs = [
        types.FunctionDeclaration(
            name="get_hook_library",
            description="Load the full hook templates from a specific hook category.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "filename": {"type": "STRING", "enum": _HOOK_LIBRARY_FILES}
                },
                "required": ["filename"],
            },
        ),
        types.FunctionDeclaration(
            name="get_cta_library",
            description="Load the full CTA templates from a specific CTA category.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "filename": {"type": "STRING", "enum": _CTA_LIBRARY_FILES}
                },
                "required": ["filename"],
            },
        ),
        types.FunctionDeclaration(
            name="get_user_persona",
            description="Fetch the active user's professional bio, core skills, tone of voice, and writing rules.",
        ),
        types.FunctionDeclaration(
            name="get_user_brand",
            description="Fetch the active user's brand identity, products, colors, and tagline.",
        ),
        types.FunctionDeclaration(
            name="get_user_voice_samples",
            description="Fetch real examples of the user's past writing related to a topic.",
            parameters={"type": "OBJECT", "properties": {"topic": {"type": "STRING", "description": "Topic to search for"}}, "required": ["topic"]},
        ),
        types.FunctionDeclaration(
            name="get_brand_knowledge",
            description="Fetch technical product specs, case studies, or deeper knowledge related to a topic.",
            parameters={"type": "OBJECT", "properties": {"topic": {"type": "STRING", "description": "Topic to search for"}}, "required": ["topic"]},
        ),
    ]
    
    if include_lead_magnet:
        funcs.append(
            types.FunctionDeclaration(
                name="tavily_search",
                description="Search the web for tools, latest resources, and GitHub repos. Use this to find lead magnets.",
                parameters={"type": "OBJECT", "properties": {"query": {"type": "STRING", "description": "Search query"}}, "required": ["query"]},
            )
        )
        
    return types.Tool(function_declarations=funcs)



# ═══════════════════════════════════════════════════════════════════════════════
# Structured Output Parsers (SOPs) — Hardcoded per directive type
# These schemas are passed to Gemini's response_schema to enforce output
# structure at the API level. The LLM CANNOT deviate from these fields.
# ═══════════════════════════════════════════════════════════════════════════════

_QUALITY_GATE_DIMENSION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "score": {"type": "INTEGER", "description": "Score 0-7 for this dimension"},
        "note": {"type": "STRING", "description": "One sentence explaining the score"},
    },
    "required": ["score", "note"],
}

_QUALITY_GATE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "hook_power": _QUALITY_GATE_DIMENSION_SCHEMA,
        "vulnerability": _QUALITY_GATE_DIMENSION_SCHEMA,
        "framework": _QUALITY_GATE_DIMENSION_SCHEMA,
        "math_proof": _QUALITY_GATE_DIMENSION_SCHEMA,
        "cta": _QUALITY_GATE_DIMENSION_SCHEMA,
    },
    "required": ["hook_power", "vulnerability", "framework", "math_proof", "cta"],
}

CAPTION_SOP = {
    "type": "OBJECT",
    "description": "Structured Output Parser for LinkedIn caption generation",
    "properties": {
        "caption": {
            "type": "STRING",
            "description": "The full LinkedIn post, formatted exactly as it should appear when published. Single line breaks after every sentence, double line breaks for paragraph transitions. No Markdown, no bullets, no section headers.",
        },
        "word_count": {
            "type": "INTEGER",
            "description": "Integer count of words in caption. Must be 200 or fewer.",
        },
        "used_hook_template": {
            "type": "STRING",
            "description": "The name of the hook template used from the hook library. You MUST call `get_hook_library` to get this."
        },
        "used_cta_template": {
            "type": "STRING",
            "description": "The name of the CTA template used from the CTA library. You MUST call `get_cta_library` to get this."
        },
        "quality_gate": _QUALITY_GATE_SCHEMA,
        "total_score": {
            "type": "INTEGER",
            "description": "Sum of all five quality gate dimension scores (0-35).",
        },
        "publish_ready": {
            "type": "BOOLEAN",
            "description": "True if total_score is 18 or above, false if below.",
        },
        "revision_flags": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Dimension names scoring below 4 with improvement instruction. Empty array if none.",
        },
        "lead_magnets": {
            "type": "ARRAY",
            "description": "Array of resources, tools, or repos found via search and offered as lead magnets. Empty if none.",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING", "description": "The name of the resource (e.g. 'Claude Code GitHub Repo')"},
                    "url": {"type": "STRING", "description": "The URL to the resource"}
                },
                "required": ["name", "url"]
            }
        },
    },
    "required": [
        "caption", "word_count", "used_hook_template", "used_cta_template", "quality_gate", "total_score",
        "publish_ready", "revision_flags", "lead_magnets"
    ],
}

ARTICLE_SOP = {
    "type": "OBJECT",
    "description": "Structured Output Parser for LinkedIn article generation",
    "properties": {
        "caption": {
            "type": "STRING",
            "description": "The full LinkedIn article, formatted exactly as it should appear when published. Single line breaks after every sentence, double line breaks for paragraph transitions. No Markdown, no bullets, no ALL CAPS section labels.",
        },
        "word_count": {
            "type": "INTEGER",
            "description": "Integer count of words in caption. Target 800-1200 words for articles.",
        },
        "used_hook_template": {
            "type": "STRING",
            "description": "The name of the hook template used from the hook library. You MUST call `get_hook_library` to get this."
        },
        "used_cta_template": {
            "type": "STRING",
            "description": "The name of the CTA template used from the CTA library. You MUST call `get_cta_library` to get this."
        },
        "quality_gate": _QUALITY_GATE_SCHEMA,
        "total_score": {
            "type": "INTEGER",
            "description": "Sum of all five quality gate dimension scores (0-35).",
        },
        "publish_ready": {
            "type": "BOOLEAN",
            "description": "True if total_score is 18 or above, false if below.",
        },
        "revision_flags": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Dimension names scoring below 4 with improvement instruction. Empty array if none.",
        },
        "lead_magnets": {
            "type": "ARRAY",
            "description": "Array of resources, tools, or repos found via search and offered as lead magnets. Empty if none.",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING", "description": "The name of the resource (e.g. 'Claude Code GitHub Repo')"},
                    "url": {"type": "STRING", "description": "The URL to the resource"}
                },
                "required": ["name", "url"]
            }
        },
    },
    "required": [
        "caption", "word_count", "used_hook_template", "used_cta_template", "quality_gate", "total_score",
        "publish_ready", "revision_flags", "lead_magnets"
    ],
}

def _get_sop_for_post_type(post_type: str, include_lead_magnet: bool = True) -> dict:
    """Return the correct Structured Output Parser schema based on post type.
    When include_lead_magnet is False, strips the lead_magnets field from the schema."""
    import copy
    base = ARTICLE_SOP if post_type.lower() == "article" else CAPTION_SOP
    if include_lead_magnet:
        return base
    # Deep-copy and strip lead_magnets so the LLM doesn't try to generate them
    sop = copy.deepcopy(base)
    sop["properties"].pop("lead_magnets", None)
    sop["required"] = [r for r in sop.get("required", []) if r != "lead_magnets"]
    return sop


def _handle_tavily_search(query: str) -> str:
    """Search the web for tools, resources, and GitHub repos using the Tavily API."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY not found in environment."

    print(f"    [tavily] Searching web for: {query}")
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": False,
                "include_raw_content": False,
                "max_results": 3
            },
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if not results:
                return "No results found."

            output = []
            for r in results:
                output.append(f"Title: {r.get('title')}\nURL: {r.get('url')}\nContent: {r.get('content')}\n---")
            return "\n".join(output)
        else:
            return f"Error from Tavily API: {response.status_code} {response.text}"
    except Exception as e:
        return f"Exception calling Tavily: {str(e)}"

def _handle_context_tool_call(fn_name: str, fn_args: dict, user_id: str) -> str:
    """Handle context tools: persona, brand, voice samples, brand knowledge."""
    safe_uid = (user_id or "default").strip() or "default"
    if safe_uid == "default":
        return "Error: No specific user context available (using default user_id)."
        
    try:
        if fn_name == "get_user_persona":
            from supabase_client import get_user_profile
            profile = get_user_profile(safe_uid)
            if not profile: return "No persona found."
            persona = profile.get("persona", {}) or profile
            skills = ", ".join(_normalize_text_list(persona.get("core_skills")))
            bio = _safe_text(persona.get("professional_bio"))
            tone = _safe_text(persona.get("tone_of_voice"))
            rules = "\n- ".join(_normalize_text_list(persona.get("writing_style_rules")))
            return f"Bio: {bio}\nSkills: {skills}\nTone: {tone}\nRules:\n- {rules}"

        elif fn_name == "get_user_brand":
            from supabase_client import get_user_brand
            brand = get_user_brand(safe_uid)
            if not brand: return "No brand found."
            name = _safe_text(brand.get("brand_name"))
            desc = _safe_text(brand.get("description"))
            tag = _safe_text(brand.get("tagline"))
            prods = ", ".join(_normalize_text_list(brand.get("products_services")))
            p_color = re.sub(r'#[0-9a-fA-F]{3,8}\b', '[Color Hidden]', brand.get('primary_color') or 'N/A')
            p_color = re.sub(r'\b[0-9a-fA-F]{6}\b', '[Color Hidden]', p_color)
            s_color = re.sub(r'#[0-9a-fA-F]{3,8}\b', '[Color Hidden]', brand.get('secondary_color') or 'N/A')
            s_color = re.sub(r'\b[0-9a-fA-F]{6}\b', '[Color Hidden]', s_color)
            a_color = re.sub(r'#[0-9a-fA-F]{3,8}\b', '[Color Hidden]', brand.get('accent_color') or 'N/A')
            a_color = re.sub(r'\b[0-9a-fA-F]{6}\b', '[Color Hidden]', a_color)
            colors = f"Primary: {p_color} | Secondary: {s_color} | Accent: {a_color}"
            return f"Brand: {name}\nTagline: {tag}\nDesc: {desc}\nProducts/Services: {prods}\nColors: {colors}"
            
        elif fn_name == "get_user_voice_samples":
            topic = fn_args.get("topic", "")
            if not topic: return "Error: topic required."
            from rag_manager import search_voice_context
            voice_text, voice_score = search_voice_context(safe_uid, topic)
            if voice_text and voice_score >= 0.5:
                return _safe_text(voice_text, 3000)
            return "No highly relevant voice samples found for this topic."
            
        elif fn_name == "get_brand_knowledge":
            topic = fn_args.get("topic", "")
            if not topic: return "Error: topic required."
            from rag_manager import RAGManager
            rag = RAGManager()
            brand_chunks = rag.search_similar(safe_uid, topic, top_k=5, threshold=0.45)
            brand_parts = [bc.content for bc in brand_chunks if bc.source_type in ("brand_product", "brand_overview", "brand_tone") and bc.content]
            if brand_parts:
                return _safe_text("\n".join(brand_parts), 2000)
            return "No relevant brand/product knowledge found."
            
        else:
            return f"Error: Unknown tool '{fn_name}'"
    except Exception as e:
        return f"Error executing {fn_name}: {e}"

def _load_user_generation_context(user_id: str = "default", topic: str = "") -> Dict[str, Any]:
    """Context is now loaded on-demand via tools by the LLM."""
    return {
        "user_id": (user_id or "default").strip() or "default",
        "has_persona": False,
        "has_brand": False
    }


def _build_user_context_sections(user_ctx: Dict[str, Any], color_palette: str) -> Dict[str, str]:
    """Build prompt sections for dynamic tenant persona and brand injection."""
    if not user_ctx:
        return {"system": "", "runtime": ""}

    system_lines: List[str] = []
    runtime_lines: List[str] = []

    if user_ctx.get("has_persona"):
        skills = ", ".join(user_ctx.get("core_skills", [])[:12]) or "Not specified"
        expertise = ", ".join(user_ctx.get("expertise_areas", [])[:8]) or "Not specified"
        rules = user_ctx.get("writing_style_rules", [])[:8]
        rules_block = "\n".join(f"- {rule}" for rule in rules) if rules else "- Keep writing practical and specific"

        system_lines.append(
            "## ACTIVE USER PERSONA (HIGHEST PRIORITY)\n"
            f"- User ID: {user_ctx.get('user_id', 'default')}\n"
            f"- Professional Bio: {user_ctx.get('professional_bio') or 'Not provided'}\n"
            f"- Tone of Voice: {user_ctx.get('tone_of_voice') or 'Professional'}\n"
            f"- Core Skills: {skills}\n"
            f"- Expertise Areas: {expertise}\n"
            f"- Target ICP: {user_ctx.get('target_icp') or 'Not specified'}\n"
            "- Writing Rules (must reflect these):\n"
            f"{rules_block}\n"
            "- Write AS this person (first-person credibility, lived experience, and natural phrasing)."
        )

        runtime_lines.append(
            "## ACTIVE USER PERSONA CONTEXT\n"
            f"- Tone: {user_ctx.get('tone_of_voice') or 'Professional'}\n"
            f"- Core Skills: {skills}\n"
            f"- Expertise Areas: {expertise}\n"
            f"- Bio Snapshot: {user_ctx.get('professional_bio') or 'Not provided'}\n"
            "- Must mirror this user's writing style and domain depth in the generated caption."
        )

    if user_ctx.get("has_brand"):
        offerings = ", ".join(user_ctx.get("products_services", [])[:12]) or "Not specified"
        palette_mode = (color_palette or "brand").lower()
        color_rule = (
            "If selected color_palette is 'brand' (and no explicit brand-kit payload overrides it), anchor all visual color decisions to this active user brand palette."
            if palette_mode == "brand"
            else "Keep messaging/style aligned to this brand identity, while final image colors must still follow the selected palette rules below."
        )

        p_color = re.sub(r'#[0-9a-fA-F]{3,8}\b', '[Color Hidden]', user_ctx.get('primary_color') or 'Not specified')
        p_color = re.sub(r'\b[0-9a-fA-F]{6}\b', '[Color Hidden]', p_color)

        s_color = re.sub(r'#[0-9a-fA-F]{3,8}\b', '[Color Hidden]', user_ctx.get('secondary_color') or 'Not specified')
        s_color = re.sub(r'\b[0-9a-fA-F]{6}\b', '[Color Hidden]', s_color)

        a_color = re.sub(r'#[0-9a-fA-F]{3,8}\b', '[Color Hidden]', user_ctx.get('accent_color') or 'Not specified')
        a_color = re.sub(r'\b[0-9a-fA-F]{6}\b', '[Color Hidden]', a_color)

        system_lines.append(
            "## ACTIVE USER BRAND PROFILE\n"
            f"- Brand Name: {user_ctx.get('brand_name') or 'Not specified'}\n"
            f"- Primary Color: {p_color} (NEVER use raw hex codes in text generation)\n"
            f"- Secondary Color: {s_color} (NEVER use raw hex codes in text generation)\n"
            f"- Accent Color: {a_color} (NEVER use raw hex codes in text generation)\n"
            f"- Font Family: {user_ctx.get('font_family') or 'Not specified'}\n"
            f"- Visual Style: {user_ctx.get('visual_style') or 'Not specified'}\n"
            f"- Brand Tagline: {user_ctx.get('brand_tagline') or 'Not specified'}\n"
            f"- Products/Services: {offerings}\n"
            f"- Brand Description: {user_ctx.get('brand_description') or 'Not specified'}\n"
            f"- Color Rule: {color_rule} - WARNING: Do NOT use explicit hex codes in any output placeholders or captions, as the image generator will render them literally as text."
        )

        runtime_lines.append(
            "## ACTIVE USER BRAND CONTEXT\n"
            f"- Brand: {user_ctx.get('brand_name') or 'Not specified'}\n"
            f"- Colors: Primary {p_color}, Secondary {s_color}, Accent {a_color}\n"
            f"- Visual Style: {user_ctx.get('visual_style') or 'Not specified'}\n"
            f"- Offerings: {offerings}\n"
            f"- {color_rule}"
        )

    return {
        "system": "\n\n".join(system_lines).strip(),
        "runtime": "\n\n".join(runtime_lines).strip(),
    }


def _download_image_bytes(url, timeout=10):
    """Download an image URL and return (bytes, mime_type) or (None, None)."""
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "image/jpeg")
            mime = ct.split(";")[0].strip()
            return resp.content, mime
    except Exception as e:
        print(f"    [visual] Failed to download {url[:60]}: {e}")
    return None, None


def _build_visual_parts(visual_context_path):
    """Build Gemini multimodal parts from visual context JSON.
    Returns (list_of_parts, text_description) for injection into the LLM prompt."""
    if not visual_context_path or not os.path.exists(visual_context_path):
        return [], ""
    
    try:
        with open(visual_context_path, "r", encoding="utf-8") as f:
            ctx = json.load(f)
    except Exception:
        return [], ""
    
    post_type = ctx.get("source_post_type", "")
    parts = []
    desc_parts = []

    # --- Handle images/carousel (for image, carousel, or mixed types) ---
    has_images = post_type in ("image", "carousel", "mixed")
    if has_images:
        urls = ctx.get("source_carousel_slides", [])
        if not urls:
            urls = ctx.get("source_image_urls", [])
        if isinstance(urls, str):
            urls = [u.strip() for u in urls.split(",") if u.strip()]
        
        # Limit to 8 images to avoid token overload
        urls = [u for u in urls if u and u.startswith("http")][:8]
        
        downloaded = 0
        for url in urls:
            img_bytes, mime = _download_image_bytes(url)
            if img_bytes:
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))
                downloaded += 1
        
        if downloaded > 0:
            desc_parts.append(f"""[VISUAL CONTEXT: {downloaded} source image(s)/slides are attached above as visual input.]
MANDATORY VISUAL ANALYSIS — Before writing, carefully study every attached image and extract:
1. HOOK: What text/headline grabs attention first? What makes it stop-the-scroll?
2. CONTENT STRUCTURE: How is information organized? (numbered steps, before/after, comparison, data visualization, quote highlight, etc.)
3. KEY MESSAGE: What is the core insight, stat, or claim being communicated visually?
4. TYPOGRAPHY & LAYOUT: Text hierarchy, font sizes, color usage, whitespace strategy.
5. VISUAL STYLE: Photography vs illustration vs infographic vs text-heavy slide.
6. RE-HOOK / CTA: How does the visual encourage continued reading or engagement?
Use ALL of these observations to deeply inform the repurposed post content — the caption should reflect the same insights, structure, and persuasive techniques found in the source visuals.""")
            print(f"    [visual] Attached {downloaded} image(s)/slides to LLM prompt")

    # --- Handle video(s) (for video or mixed types) ---
    has_video = post_type in ("video", "mixed")
    if has_video:
        video_urls = ctx.get("source_video_urls", [])
        if not video_urls:
            single = ctx.get("source_video_url", "")
            if single:
                video_urls = [single]
        video_urls = [u for u in video_urls if u and u.startswith("http")]
        
        for i, vurl in enumerate(video_urls[:3]):  # Limit to 3 videos
            label = f" #{i+1}" if len(video_urls) > 1 else ""
            transcript = _transcribe_video(vurl)
            if transcript:
                desc_parts.append(f"[VIDEO TRANSCRIPTION{label} FROM SOURCE POST]:\n{transcript}\n[END TRANSCRIPTION]")
                print(f"    [visual] Video{label} transcribed: {len(transcript)} chars")
            else:
                desc_parts.append(f"[VIDEO{label} CONTEXT: Video was present but could not be transcribed. Use the text caption as the primary source.]")
        
        if any("TRANSCRIPTION" in d for d in desc_parts):
            desc_parts.append("""MANDATORY TRANSCRIPTION ANALYSIS — Before writing, analyze the video transcription(s) and extract:
1. HOOK: What opening line/statement grabs attention? How does the speaker draw you in?
2. KEY ARGUMENTS: What are the main points, claims, or insights presented?
3. STORYTELLING STRUCTURE: How does the speaker build their narrative? (problem→solution, chronological, contrast, etc.)
4. MEMORABLE QUOTES: Any standout phrases, one-liners, or data points worth preserving.
5. RE-HOOK / CTA: How does the speaker close? What call-to-action or takeaway do they leave?
6. TONE & VOICE: Casual, authoritative, humorous, urgent? Mirror this in the repurposed post.
Use the transcription as the PRIMARY content source — the text caption is secondary context.""")
    
    desc = "\n\n".join(desc_parts) if desc_parts else ""
    return parts, desc


def _transcribe_video(video_url, max_size_mb=20):
    """Download a video and transcribe it using Gemini's multimodal capabilities."""
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")
    if not api_key:
        return None
    
    try:
        print(f"    [video] Downloading video for transcription: {video_url[:80]}")
        resp = requests.get(video_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
        if resp.status_code != 200:
            print(f"    [video] Download failed: HTTP {resp.status_code}")
            return None
        
        # Read up to max_size_mb
        chunks = []
        total = 0
        limit = max_size_mb * 1024 * 1024
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            chunks.append(chunk)
            total += len(chunk)
            if total > limit:
                print(f"    [video] Truncated at {max_size_mb}MB")
                break
        
        video_bytes = b"".join(chunks)
        if len(video_bytes) < 1000:
            print(f"    [video] Video too small ({len(video_bytes)} bytes), skipping")
            return None
        
        ct = resp.headers.get("content-type", "video/mp4")
        mime = ct.split(";")[0].strip()
        if "video" not in mime:
            mime = "video/mp4"
        
        print(f"    [video] Transcribing {len(video_bytes) / 1024 / 1024:.1f}MB video via Gemini...")
        
        client = genai.Client(api_key=api_key)
        video_part = types.Part.from_bytes(data=video_bytes, mime_type=mime)
        
        response = client.models.generate_content(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction="You are a transcription assistant. Transcribe the spoken content in this video accurately. Include speaker descriptions if multiple speakers are present. Output ONLY the transcription text, nothing else.",
                temperature=0.1,
            ),
            contents=[video_part, "Transcribe all spoken content in this video. Be thorough and accurate."]
        )
        
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tracker = CostTracker()
            tracker.add_gemini_cost("Video Transcription", response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count, model=model_name)
        
        transcript = response.text.strip()
        if transcript and len(transcript) > 20:
            return transcript
        return None
    except Exception as e:
        print(f"    [video] Transcription error: {e}")
        return None


from cost_tracker import CostTracker

def call_llm(system_prompt, user_content, json_mode=False, response_schema=None, tools=None, user_id="default"):
    """
    Calls the Google Gemini API using the latest google-genai SDK.
    When response_schema is provided, Gemini enforces structured output at the API level.
    When tools are provided, supports a function-calling loop so the LLM can
    request specific library files before generating the final response.
    """
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")
    if not api_key:
        print("Error: GOOGLE_GEMINI_API_KEY not found in environment.")
        return "Error: Missing API Key. Please add GOOGLE_GEMINI_API_KEY to your .env file."

    try:
        client = genai.Client(api_key=api_key)

        config_params = {
            "system_instruction": system_prompt,
            "temperature": 0.7,
        }
        if json_mode:
            config_params["response_mime_type"] = "application/json"
        if response_schema:
            config_params["response_mime_type"] = "application/json"
            config_params["response_schema"] = response_schema
            print(f">>> SOP enforced: {len(response_schema.get('required', []))} required fields")
        if tools:
            # Check if tools already contains GoogleSearch, if not add it
            has_search = any(hasattr(t, 'google_search') and t.google_search for t in tools)
            if not has_search:
                tools.append(types.Tool(google_search=types.GoogleSearch()))
            config_params["tools"] = tools
            # Required when mixing custom functions and Google Search
            config_params["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO"),
                include_server_side_tool_invocations=True
            )
        else:
            config_params["tools"] = [types.Tool(google_search=types.GoogleSearch())]

        config = types.GenerateContentConfig(**config_params)

        # Use stateful chat for function-calling loops so Gemini-managed
        # metadata (e.g. thought signatures) remains intact across turns.
        chat = client.chats.create(model=model_name, config=config)

        # user_content can be a plain string OR a list of Parts (multimodal)
        if isinstance(user_content, list):
            initial_parts = []
            for item in user_content:
                if isinstance(item, str):
                    initial_parts.append(types.Part.from_text(text=item))
                else:
                    initial_parts.append(item)  # Already a Part (image bytes etc.)
            response = chat.send_message(initial_parts)
        else:
            response = chat.send_message(str(user_content))

        # ── Function-calling loop (max 8 rounds) ────────────────────────
        max_tool_rounds = 8
        for tool_round in range(max_tool_rounds):

            candidate = response.candidates[0]

            # Check if model wants to call functions (robust extraction)
            function_calls = getattr(candidate, "function_calls", [])
            if not function_calls and hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                function_calls = [p.function_call for p in candidate.content.parts if getattr(p, "function_call", None)]

            if not function_calls:
                # Final text response — exit the loop
                break

            # Process function calls
            print(f">>> Function calling round {tool_round + 1}: {len(function_calls)} call(s)")

            fn_response_parts = []
            for call in function_calls:
                fn_name = getattr(call, "name", "")
                fn_args = dict(call.args) if getattr(call, "args", None) else {}
                if fn_name in ["get_user_persona", "get_user_brand", "get_user_voice_samples", "get_brand_knowledge"]:
                    result = _handle_context_tool_call(fn_name, fn_args, user_id)
                elif fn_name == "tavily_search":
                    result = _handle_tavily_search(fn_args.get("query", ""))
                else:
                    result = _handle_library_tool_call(fn_name, fn_args)
                fn_response_parts.append(
                    types.Part.from_function_response(
                        name=fn_name,
                        response={"content": result},
                    )
                )

            # Important: Send fn_response_parts, suppressing Google SDK warnings if we accidentally check response.text elsewhere
            response = chat.send_message(fn_response_parts)

        # ── Extract final text from response ─────────────────────────────
        final_text = ""
        if response and response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    final_text += part.text
        final_text = final_text.strip()

        # ── Track cost ───────────────────────────────────────────────────
        if response and hasattr(response, "usage_metadata") and response.usage_metadata:
            tracker = CostTracker()
            tracker.add_gemini_cost(
                "Text Generation",
                response.usage_metadata.prompt_token_count,
                response.usage_metadata.candidates_token_count,
                model=model_name,
            )

        return final_text if final_text else "Error: No response from Gemini"
    except Exception as e:
        print(f"Error calling Gemini: {str(e)}")
        return f"Error: Failed to generate content via Gemini. {str(e)}"


def generate_text_post(post_type, purpose, topic, source="topic", style="minimal", source_content=None, visual_aspect="none", visual_context_path=None, custom_topic=None, user_id="default", raw_notes=None, include_lead_magnet=False):
    """
    Mega-Generation: Caption + Image Prompt + Nano Banana Pro in one pass.
    """
    print(f">>> generate_text_post called with visual_aspect={visual_aspect}")

    output_path = ".tmp/final_plan.json"
    user_context = _load_user_generation_context(user_id, topic=topic)
    user_context_sections = _build_user_context_sections(user_context, "brand")
    if user_context.get("has_persona") or user_context.get("has_brand"):
        print(
            ">>> Loaded tenant generation context "
            f"for user={user_context.get('user_id')} "
            f"(persona={user_context.get('has_persona')}, brand={user_context.get('has_brand')})"
        )

    # Route to article directives for article post type, caption directives for text posts
    if post_type.lower() == "article":
        directive_path = f"directives/{purpose}_article.md"
        print(f">>> Article mode: using {directive_path}")
    else:
        directive_path = f"directives/{purpose}_caption.md"
    image_sop_path = "directives/image_prompt_design.md"
    
    # --- LOAD CONTEXT DATA ---
    analysis = {}
    input_path = ".tmp/analysis.json"
    analysis_context = ""
    if os.path.exists(input_path):
        with open(input_path, "r") as f:
            analysis = json.load(f)
            analysis_context = f"Common Patterns Analysis:\n{json.dumps(analysis.get('common_patterns', {}))}\n"

    # Load Miro Board Strategy (Section 1 of Guidelines)
    strategy_context = ""
    try:
        guidelines_path = "LinkedIn guidelines/ULTIMATE TOP PERFORMING LINKEDIN POST GUIDELINES.txt"
        if os.path.exists(guidelines_path):
            with open(guidelines_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Extract Section 1
                start_marker = "SECTION 1: THE 4-STEP LINKEDIN CONTENT PLAYBOOK"
                end_marker = "SECTION 2:"
                if start_marker in content:
                    start_idx = content.find(start_marker)
                    end_idx = content.find(end_marker)
                    if end_idx == -1:
                        end_idx = len(content)
                    strategy_context = content[start_idx:end_idx]
    except Exception as e:
        print(f"Warning: Could not load strategy context: {e}")

    # Check for Viral Reference context
    viral_ref_path = ".tmp/viral_trends.json"
    viral_context = ""
    if os.path.exists(viral_ref_path):
        with open(viral_ref_path, "r") as f:
            viral_trends = json.load(f)
            if viral_trends:
                viral_anchor = viral_trends[0]
                viral_context = f"\nViral Anchor Reference (structural template):\nURL: {viral_anchor['url']}\nOriginal Text: {viral_anchor['text']}\n"

    # Check for Deep Research context first, fallback to Jina Search context
    synthesized_path = ".tmp/synthesized_research.md"
    jina_context_path = ".tmp/source_content.md"
    jina_content = ""
    
    if os.path.exists(synthesized_path):
        with open(synthesized_path, "r", encoding="utf-8") as f:
            jina_content = f.read() # Use the full synthesized clean data
    elif os.path.exists(jina_context_path):
        with open(jina_context_path, "r", encoding="utf-8") as f:
            jina_content = f.read()[:4000] # Limit raw data to avoid token issues

    # Check for YouTube research context
    yt_research_path = ".tmp/youtube_research.json"
    yt_context = ""
    if os.path.exists(yt_research_path):
        with open(yt_research_path, "r") as f:
            yt_data = json.load(f)
            if yt_data:
                yt_context = f"\nYouTube Research Insights:\n{json.dumps(yt_data[:3])}\n"

    # NOTE: Static voice-tone.md and brand_knowledge.md removed.
    # Each user's voice/tone and brand data now flows exclusively from
    # their Supabase profile via _load_user_generation_context() and
    # _build_user_context_sections() to prevent cross-user data leaks.

    # Load Caption Directive
    if not os.path.exists(directive_path):
        system_prompt = "You are an expert LinkedIn copywriter. Write a post about the given topic."
    else:
        with open(directive_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()

    # Inject Hook & CTA library INDEXES only — LLM uses function calling to load specific files
    library_indexes = _load_library_indexes()
    if library_indexes:
        system_prompt += f"\n\n---\n{library_indexes}\n---\n"

    # Apply Surveillance Playbook Rules if source is surveillance
    if source.lower() == "surveillance":
        playbook_path = "Antigravity_Linkedin_Assessment  clean/strategy/POST_PERFORMANCE_PLAYBOOK.md"
        if os.path.exists(playbook_path):
            with open(playbook_path, "r", encoding="utf-8") as f:
                playbook_content = f.read()
            system_prompt += f"\n\n---\n## SURVEILLANCE PLAYBOOK FOR REPURPOSING\nThe user wants to repurpose a top-performing post. Read and strictly apply the formulas from this playbook to extract the exact structural DNA of the source post, and generate a new post following that exact formula, but centered around the New Topic:\n\n{playbook_content}\n\n---\n"
            print(">>> Loaded POST_PERFORMANCE_PLAYBOOK.md for surveillance repurposing")

    # Prepend dynamic user persona/brand context so it governs all output
    fact_checking_block = (
        "## FACT CHECKING & GROUNDING\n"
        "You MUST use the built-in Google Search tool to verify all product names, AI model versions (e.g., 'Gemini 3.5' vs 'Gemini 1.5'), release dates, and technical capabilities before writing the post.\n"
        "If you mention a tool or version, verify it exists. Do NOT hallucinate versions or features. If a claim from the provided context (e.g., Tavily or Jina) seems incorrect or refers to non-existent models, search the web to correct it before drafting."
    )
    system_blocks = [fact_checking_block]

    # --- LEAD MAGNET HUNTING (separate LLM — gemini-2.5-pro) ---
    _verified_lead_magnets = []
    if include_lead_magnet:
        try:
            from lead_magnet_hunter import hunt_lead_magnets
            _verified_lead_magnets = hunt_lead_magnets(
                topic,
                research_context=(jina_content or "")[:2000],
            )
        except Exception as e:
            print(f">>> Lead magnet hunter error: {e}")

        if _verified_lead_magnets:
            magnets_desc = "\n".join(
                [f"- **{m['name']}**: {m['url']} — {m.get('description', '')[:100]}" for m in _verified_lead_magnets]
            )
            system_blocks.append(
                "## VERIFIED LEAD MAGNETS (PRE-SEARCHED & URL-VERIFIED)\n"
                "A separate research agent has already found and verified these resources are live and relevant.\n"
                "You MUST integrate the BEST one organically into your CTA. Use the `get_cta_library` tool to find a lead-magnet CTA template.\n"
                "Do NOT invent your own URLs. Only use the verified URLs below.\n"
                "Include ALL used lead magnets in the `lead_magnets` JSON array.\n\n"
                f"{magnets_desc}"
            )
            print(f">>> Injected {len(_verified_lead_magnets)} verified lead magnets into prompt")
        else:
            system_blocks.append(
                "## LEAD MAGNET NOTE\n"
                "The lead magnet hunter could not find any verified resources for this topic. "
                "Do NOT invent or hallucinate any resource URLs. Skip the lead magnet CTA "
                "and use a standard engagement CTA instead. Set lead_magnets to an empty array."
            )
            print(">>> Lead magnet hunter found 0 verified resources — skipping")
    else:
        print(">>> Lead magnet toggle OFF — skipping lead magnet hunter prompt block")
    if user_context_sections.get("system"):
        system_blocks.append(user_context_sections["system"])
    if system_blocks:
        system_prompt = "\n\n---\n\n".join(system_blocks + [system_prompt])

    # Inject raw weekly notes for Journalist Workflow (storytelling)
    if raw_notes and raw_notes.strip() and purpose == "storytelling":
        raw_notes_block = (
            "\n\n---\n\n"
            "## RAW WEEKLY NOTES (Journalist Workflow Input)\n"
            "The user has provided their raw weekly notes below. Extract the strongest story elements:\n"
            "- What happened in the trenches this week?\n"
            "- Where was the friction or frustration?\n"
            "- What was the epiphany or lesson learned?\n"
            "Use these raw notes as the PRIMARY source material for the storytelling post. "
            "Transform them into a compelling narrative using the SLAY Framework.\n\n"
            f"{raw_notes.strip()}\n\n---"
        )
        system_prompt += raw_notes_block
        print(f">>> Injected raw weekly notes ({len(raw_notes)} chars) into storytelling prompt")

    # --- BUILD VISUAL CONTEXT (must happen before prompt construction) ---
    visual_parts, visual_desc = _build_visual_parts(visual_context_path)

    # --- INJECT USER REFERENCE IMAGE (if provided) ---
    reference_image_desc = ""

    # --- PREPARE THE MEGA PROMPT ---
    custom_topic_sanitized = sanitize_untrusted_input(custom_topic) if custom_topic else ""
    custom_topic_str = f"## NEW TOPIC OVERRIDE\nThe user has requested to repurpose the original structure and hook style from the source content, but change the subject matter entirely. Generate the post tightly aligned with this new topic:\n{custom_topic_sanitized}\n" if custom_topic else ""
    
    user_content = f"""# TASK: Generate LinkedIn Post Assets
Topic: {sanitize_untrusted_input(topic)}
Post Type: {post_type}
Purpose: {purpose}
Visual Aspect: {visual_aspect}


## CONTEXT DATA
{sanitize_untrusted_input(jina_content) if jina_content else "No web search data available."}
{sanitize_untrusted_input(viral_context) if viral_context else ""}
{sanitize_untrusted_input(yt_context) if yt_context else ""}
{sanitize_untrusted_input(analysis_context) if analysis_context else ""}

## ACTIVE USER CONTEXT (PERSONA + BRAND)
{user_context_sections.get("runtime") if user_context_sections.get("runtime") else "No tenant profile found. Use the base system directives."}

## DIRECT REPURPOSE SOURCE (PRIORITY)
{sanitize_untrusted_input(source_content) if source_content else "No direct content provided."}

{custom_topic_str}

{visual_desc}



## INSTRUCTIONS

### TOPIC GROUNDING RULE (CRITICAL)
If the topic names a specific product, tool, person, company, or technology (e.g. "Claude Code", "Tesla", "Sam Altman"), the generated post MUST be explicitly and specifically about that entity. Do NOT generalize to the broader category (e.g. do NOT write a generic "AI tools" post when the topic is "Claude Code"). The named entity must appear in the hook, body, and conclusion. Use the research data to ground the post in real, specific details about that entity. If the provided research data is empty or lacks specific details, rely on your internal knowledge to provide accurate facts about the entity. DO NOT invent or hallucinate features, updates, or events that did not happen.

### STEP 1: DEEP SOURCE ANALYSIS (MANDATORY)
Before writing ANYTHING, analyze ALL provided source material:
- **Text Caption / Source Post**: Identify the exact formula used from the Surveillance Playbook (e.g. Identity Challenge, Money Math). Extract the hook (first 1-2 lines), the body structure (how ideas flow), the re-hook (mid-post attention recapture), and the CTA/close.
- **Visual Context** (if images/slides attached above): Follow the MANDATORY VISUAL ANALYSIS instructions in the visual context section. Extract hooks, content structure, key messages, typography patterns, and persuasive techniques from every image.
- **Video Transcription** (if provided above): Follow the MANDATORY TRANSCRIPTION ANALYSIS instructions. Extract the speaker's hook, key arguments, storytelling arc, memorable quotes, and closing CTA.
- **Cross-Reference**: Combine insights from text + visuals + transcription to understand the FULL message, not just the caption text.

### STEP 2: GENERATE REPURPOSED POST
Using your deep analysis from Step 1, generate a LinkedIn post that:
- Preserves the core insights, data points, and persuasive techniques from the source
- Adapts the content to the requested Post Type ({post_type}) and Purpose ({purpose})
- Follows the system instructions (caption directive) for tone, structure, and formatting
- If source had strong hooks/rehooks, create equally strong ones for the new format
- If source had specific data/stats/quotes (from images or transcription), incorporate them

**POST TYPE ADAPTATION ({post_type}):**
- **If "text"**: Generate a standard LinkedIn post (150-250 words max). Concise, punchy, scroll-stopping. Single cohesive message.
- **If "article"**: Generate a detailed LinkedIn article (800-1200 words). Follow the article directive structure closely. Multi-paragraph with clear sections, real depth, case studies, and proof points. Use line breaks for structure, NOT markdown headers. This is a FULL article, not an extended post.

**VISUAL ASPECT ADAPTATION ({visual_aspect}):**
- **If "none"**: Generate a standalone text post. The caption must be complete and self-contained. No visual asset needed.
- **If "image"**: Generate a text caption + image prompt. The caption should reference or complement the visual. The image amplifies one core insight from the post.
- **If "video"**: Generate a text caption + video concept. The caption should tease the video content. Include a brief video script/concept in your thinking (though only caption is returned in JSON).
- **If "carousel"**: This is handled by a separate generator, but if you receive this, treat it as a multi-slide concept where each slide builds on the previous one.

## OUTPUT
Return a JSON object. The output schema is enforced by the API — populate every field.
For quality_gate, use these exact keys: hook_power, vulnerability, framework, math_proof, cta.
Each quality_gate dimension must have a "score" (integer 0-7) and "note" (one sentence).
If Visual Aspect is not "image", set single_point, image_prompt to empty strings and image_palette to empty array.
"""

    # Select the correct Structured Output Parser (SOP) for this post type
    active_sop = _get_sop_for_post_type(post_type, include_lead_magnet=include_lead_magnet)

    # Build final contents: image parts first (if any), then text prompt
    if visual_parts:
        contents = visual_parts + [user_content]
        print(f">>> Requesting multimodal assets from LLM ({len(visual_parts)} visual parts + text)...")
    else:
        contents = user_content
        print(">>> Requesting combined assets from LLM (Simplified Flow)...")
    
    # Use function-calling tools (hook/CTA library, persona, brand) but NOT tavily
    # Lead magnets are already pre-verified and injected into the prompt
    generation_tools = get_tool_declarations(include_lead_magnet=False)
    raw_response = call_llm(system_prompt, contents, json_mode=True, response_schema=active_sop, tools=[generation_tools], user_id=user_id)
    print(">>>STAGE:text_done", flush=True)

    if not raw_response:
        print("Error: Received empty response from LLM.")
        raw_response = '{"caption": "Error: Failed to generate content.", "single_point": ""}'

    try:
        # Sometimes Gemini wraps JSON in markdown blocks even with response_mime_type set
        import re
        cleaned_response = raw_response.strip()
        cleaned_response = re.sub(r'^```[a-zA-Z]*\s*\n', '', cleaned_response)
        cleaned_response = re.sub(r'\n\s*```$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        response_data = json.loads(cleaned_response)
    except Exception as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Raw output was:\n{raw_response[:500]}...")
        # Fallback to a basic structure if LLM fails JSON
        # Attempt to extract just the caption using regex if json failed
        fallback_caption = raw_response
        import re
        # More robust regex that matches the caption value until the next expected key
        match = re.search(r'"caption"\s*:\s*"(.*?)"\s*,\s*"(?:word_count|used_hook_template|quality_gate|publish_ready|total_score)"', raw_response, re.DOTALL)
        if match:
            fallback_caption = match.group(1)
            # unescape common JSON escapes
            fallback_caption = fallback_caption.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
        else:
            # Ultimate fallback if keys are out of order
            match = re.search(r'"caption"\s*:\s*"([^"]+)"', raw_response, re.DOTALL)
            if match:
                 fallback_caption = match.group(1).replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')

        response_data = {
            "caption": fallback_caption.strip(),
            "single_point": topic,
            "lead_magnets": []
        }

    caption = response_data.get("caption", "") or response_data.get("post_text", "")

    # Prepare final plan object
    # Merge pre-verified lead magnets with any the LLM added
    llm_magnets = response_data.get("lead_magnets", [])
    # Prefer pre-verified magnets (URLs confirmed alive)
    final_magnets = _verified_lead_magnets if _verified_lead_magnets else llm_magnets

    plan = {
        "caption": caption,
        "source": source,
        "analysis": analysis,
        "lead_magnets": final_magnets,
        "asset_prompts": {}
    }

    if post_type.lower() == "image":
        plan["asset_prompts"]["nano_banana_pro"] = {
            "scene": {
                "location": "modern corporate office",
                "environment": "clean, tech-focused workspace",
                "palette": "brand"
            },
            "technical_settings": {
                "aspect_ratio": "16:9",
                "quality": "high resolution",
                "style": "Authentic iPhone photo"
            }
        }
    elif post_type.lower() == "video":
        plan["asset_prompts"]["sora_veo"] = f"A cinematic drone shot through a neon-lit city of the future, showing integrated AI systems, seamless transitions."
    elif post_type.lower() == "article":
        plan["article_outline"] = [
            f"Introduction: The shift towards {topic}",
            "Key discoveries from our research",
            "Practical applications for businesses",
            "Conclusion and next steps"
        ]


    with open(output_path, "w") as f:
        json.dump(plan, f, indent=4)

    print(f"Final plan saved to {output_path}")

if __name__ == "__main__":
    print(">>> generate_text_post.py script started", flush=True)
    _configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Generate post assets and captions.")
    parser.add_argument("--type", required=True, help="Post type (image, video, article, etc).")
    parser.add_argument("--purpose", default="storytelling", help="Post goal.")
    parser.add_argument("--topic", default="Modern AI", help="Topic of the post.")
    parser.add_argument("--source", default="topic", help="Content source.")
    parser.add_argument("--source_content", help="Direct text content to repurpose.")
    parser.add_argument("--visual_aspect", default="none", help="Visual aspect.")
    parser.add_argument("--visual_context", help="Path to JSON file with visual context.")
    parser.add_argument("--custom_topic", default=None, help="User-provided custom topic for repurposing.")
    parser.add_argument("--user_id", default="default", help="Active user ID for tenant-scoped persona/brand injection.")
    parser.add_argument("--raw_notes", default=None, help="Path to raw weekly notes file for Journalist Workflow (storytelling).")
    parser.add_argument("--include_lead_magnet", action="store_true", help="Allow LLM to search web for lead magnets.")

    args = parser.parse_args()

    if args.source_content and os.path.exists(args.source_content) and os.path.isfile(args.source_content):
        with open(args.source_content, "r", encoding="utf-8") as f:
            args.source_content = f.read()

    _raw_notes = None
    if args.raw_notes and os.path.exists(args.raw_notes) and os.path.isfile(args.raw_notes):
        with open(args.raw_notes, "r", encoding="utf-8") as f:
            _raw_notes = f.read()
        print(f">>> Loaded raw weekly notes ({len(_raw_notes)} chars)")

    generate_text_post(
        post_type=args.type,
        purpose=args.purpose,
        topic=args.topic,
        source=args.source,
        source_content=args.source_content,
        visual_aspect=args.visual_aspect,
        visual_context_path=args.visual_context,
        custom_topic=args.custom_topic,
        user_id=args.user_id,
        raw_notes=_raw_notes,
        include_lead_magnet=args.include_lead_magnet
    )
