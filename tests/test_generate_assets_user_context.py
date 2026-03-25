import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

EXEC_DIR = os.path.join(ROOT_DIR, "execution")
if EXEC_DIR not in sys.path:
    sys.path.append(EXEC_DIR)

_ORIG_STDOUT = sys.stdout
_ORIG_STDERR = sys.stderr

from execution import generate_assets as _generate_assets

# generate_assets wraps stdio streams at import; restore for pytest stability
sys.stdout = _ORIG_STDOUT
sys.stderr = _ORIG_STDERR

_normalize_text_list = _generate_assets._normalize_text_list
_build_user_context_sections = _generate_assets._build_user_context_sections
_load_user_generation_context = _generate_assets._load_user_generation_context


def test_normalize_text_list_handles_json_and_delimited_text():
    assert _normalize_text_list('["alpha", "beta"]') == ["alpha", "beta"]
    assert _normalize_text_list("alpha, beta; gamma\n- delta") == ["alpha", "beta", "gamma", "delta"]


def test_build_user_context_sections_includes_persona_and_brand_blocks():
    context = {
        "user_id": "uid-123",
        "has_persona": True,
        "has_brand": True,
        "professional_bio": "Founder and operator in B2B SaaS.",
        "tone_of_voice": "Direct and practical",
        "core_skills": ["Growth", "Product", "Positioning"],
        "writing_style_rules": ["Start with a sharp hook", "Use short punchy lines"],
        "expertise_areas": ["SaaS", "Go-to-market"],
        "target_icp": "Founders",
        "brand_name": "Obsidian Logic AI",
        "primary_color": "#F9C74F",
        "secondary_color": "#0E0E0E",
        "accent_color": "#FCF0D5",
        "font_family": "Outfit",
        "visual_style": "Minimal modern",
        "brand_tagline": "Build signal, not noise",
        "brand_description": "A growth system for serious operators.",
        "products_services": ["LinkedIn ghostwriting", "Content systems"],
    }

    sections = _build_user_context_sections(context, color_palette="brand")

    assert "ACTIVE USER PERSONA" in sections["system"]
    assert "ACTIVE USER BRAND PROFILE" in sections["system"]
    assert "Obsidian Logic AI" in sections["runtime"]
    assert "anchor all visual color decisions" in sections["runtime"]


def test_load_user_generation_context_default_user_is_safe_noop():
    context = _load_user_generation_context("default")
    assert context["user_id"] == "default"
    assert context["has_persona"] is False
    assert context["has_brand"] is False
