"""
Brand Extractor Module
Extracts brand elements (colors, fonts, logo, visual style) from website URLs.

Strategy:
  Phase 1 — Single Firecrawl call with formats=["branding", "markdown"]:
    - `branding`: CSS-parsed design system (colors, logo, fonts). Deterministic, no AI.
    - `markdown` + onlyMainContent: Clean page text for LLM analysis.
  Phase 2 — Gemini LLM call on the markdown:
    - Extracts: brand_name, products_services, tone_of_voice, tagline, description.
    - AI is ONLY used here, never for colors/logo/fonts.
  Results cached per URL for 24 hours.
"""

import os
import re
import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_API_URL = "https://api.firecrawl.dev/v2/scrape"

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE_FILE = os.path.join(_PROJECT_ROOT, ".tmp", "brand_cache.json")
_CACHE_TTL_HOURS = 24


# ─────────────────────────────────────────────────────────────
# URL Cache helpers
# ─────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _get_cached(url: str) -> Optional[dict]:
    cache = _load_cache()
    entry = cache.get(url)
    if entry and (time.time() - entry.get("ts", 0)) < _CACHE_TTL_HOURS * 3600:
        print(f"[Brand] Cache hit for {url}")
        return entry.get("data")
    return None


def _set_cached(url: str, data: dict):
    os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
    
    try:
        from execution.file_locker import FileLock
    except ImportError:
        try:
            from file_locker import FileLock
        except ImportError:
            FileLock = None

    def _do_set():
        cache = _load_cache()
        cache[url] = {"data": data, "ts": time.time()}
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)

    if FileLock:
        try:
            with FileLock(_CACHE_FILE):
                _do_set()
        except Exception as e:
            print(f"[Brand] Cache lock error: {e}")
            _do_set()
    else:
        _do_set()


# ─────────────────────────────────────────────────────────────
# Default UI theme (Obsidian Logic defaults for reset)
# ─────────────────────────────────────────────────────────────

DEFAULT_UI_THEME = {
    "brand_primary":       "#F9C74F",
    "brand_primary_hover":  "#f0b829",
    "brand_primary_light":  "rgba(249,199,79,0.15)",
    "brand_obsidian":       "#0E0E0E",
    "brand_obsidian_soft":  "#1a1a1a",
    "bg_main":              "#1a1a1a",
    "bg_paper":             "#111111",
    "bg_elevated":          "#252525",
    "bg_sidebar":           "#0E0E0E",
    "text_primary":         "#F0F0F0",
    "text_secondary":       "#A0A0A0",
    "text_tertiary":        "#6B6B6B",
    "text_muted":           "#4B4B4B",
    "text_inverse":         "#FCF0D5",
    "border":               "rgba(255,255,255,0.1)",
    "border_hover":         "rgba(255,255,255,0.2)",
    "border_focus":         "#F9C74F",
    "shadow_glow":          "0 0 20px rgba(249,199,79,0.3)",
    "shadow_glow_strong":   "0 0 30px rgba(249,199,79,0.5)",
    "brand_gradient":       "linear-gradient(135deg, #F9C74F 0%, #F59E0B 100%)",
    "brand_gradient_dark":  "linear-gradient(135deg, #0E0E0E 0%, #1a1a1a 100%)",
    "brand_gradient_hover": "linear-gradient(135deg, #f0b829 0%, #e5a608 100%)",
}


# ─────────────────────────────────────────────────────────────
# Gemini LLM — UI theme generation from brand colors
# ─────────────────────────────────────────────────────────────

def _generate_ui_theme(colors: dict, color_scheme: str = "light") -> dict:
    """
    Send ALL Firecrawl brand colors to Gemini. Returns a complete dark-UI
    CSS variable mapping. The LLM decides which brand color suits which
    UI surface (sidebar, console, buttons, glows, text, borders, etc.).
    """
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key or not colors:
        return dict(DEFAULT_UI_THEME)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")

        primary_hex = colors.get("primary") or "#F9C74F"
        accent_hex  = colors.get("accent") or colors.get("link") or primary_hex

        colors_desc = json.dumps(colors, indent=2)
        prompt = f"""You are a senior UI/UX designer. Given these brand colors extracted from a website, generate a COMPLETE dark-theme dashboard color system.

BRAND COLORS (from CSS analysis):
{colors_desc}
Color scheme detected: {color_scheme}

CRITICAL: brand_primary MUST be exactly {primary_hex}. Do NOT change it.
CRITICAL: border_focus MUST be exactly {primary_hex}. Do NOT change it.

Generate a JSON object that maps CSS variable names to values. This is for a dark professional dashboard UI. Rules:
1. The UI MUST be dark-themed (dark backgrounds, light text).
2. Use {primary_hex} EXACTLY as brand_primary for interactive elements: buttons, links, active states, focus rings, glows.
3. Derive dark backgrounds that are subtly tinted with the brand hue (not pure black — add a hint of {primary_hex}).
4. The sidebar and console/taskbar should also reflect the brand — use very dark tinted versions.
5. Ensure WCAG AA contrast for all text on their backgrounds.
6. Borders and shadows should carry a subtle brand tint using the primary hue.
7. Gradients should flow between {primary_hex} and {accent_hex}.

Return ONLY valid JSON with these EXACT keys (no extras, no missing keys):
{{
  "brand_primary":        "MUST be {primary_hex}",
  "brand_primary_hover":  "Slightly darker primary for hover",
  "brand_primary_light":  "rgba() — primary at ~15% opacity for subtle tinted backgrounds",
  "brand_obsidian":       "Darkest surface (header bar) — brand-tinted near-black",
  "brand_obsidian_soft":  "Slightly lighter than obsidian — for sidebar",
  "bg_main":              "Main content area — dark, brand-tinted",
  "bg_paper":             "Card/panel — darker than bg_main",
  "bg_elevated":          "Dropdowns/tooltips/modals — lighter than bg_main",
  "bg_sidebar":           "Sidebar background — very dark, brand-tinted",
  "text_primary":         "Main text — high contrast on dark backgrounds",
  "text_secondary":       "Secondary text — medium contrast",
  "text_tertiary":        "Labels/hints — low contrast",
  "text_muted":           "Disabled/placeholder text",
  "text_inverse":         "Text color when placed ON the brand_primary background",
  "border":               "rgba() — subtle brand-tinted border",
  "border_hover":         "rgba() — slightly brighter border on hover",
  "border_focus":         "MUST be {primary_hex}",
  "shadow_glow":          "CSS box-shadow — subtle brand glow (e.g. 0 0 20px rgba(...))",
  "shadow_glow_strong":   "CSS box-shadow — strong brand glow",
  "brand_gradient":       "CSS linear-gradient using {primary_hex} and {accent_hex}",
  "brand_gradient_dark":  "CSS linear-gradient for dark surfaces",
  "brand_gradient_hover": "CSS linear-gradient for hover states"
}}

Return raw JSON only. Every value must be a valid CSS color/gradient/shadow value."""

        response = client.models.generate_content(
            model=model,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
            contents=prompt
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```[a-z]*\n?', '', text).rstrip('`').strip()
        theme = json.loads(text)

        # Validate: every key in DEFAULT_UI_THEME must be present
        for key in DEFAULT_UI_THEME:
            if key not in theme or not theme[key]:
                theme[key] = DEFAULT_UI_THEME[key]

        # Hard-override: brand_primary and border_focus MUST match Firecrawl exactly
        theme["brand_primary"] = primary_hex
        theme["border_focus"]  = primary_hex

        return theme

    except Exception as e:
        print(f"[Brand] UI theme generation error: {e}")
        return dict(DEFAULT_UI_THEME)


# ─────────────────────────────────────────────────────────────
# Gemini LLM — content analysis (products/services/tone)
# ─────────────────────────────────────────────────────────────

def _analyze_content_with_gemini(markdown: str, brand_name_hint: str = "") -> dict:
    """
    Send clean page markdown to Gemini to extract text-based brand attributes.
    Returns a dict with: brand_name, products_services, tone_of_voice, tagline, description.
    """
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key or not markdown.strip():
        return {}

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")

        hint = f' (hint: the site appears to be "{brand_name_hint}")' if brand_name_hint else ""
        prompt = f"""You are a brand analyst. Analyze this website content{hint} and return ONLY valid JSON with these exact keys:

{{
  "brand_name": "Company or product name",
  "tone_of_voice": "2-sentence description of brand voice and communication style",
  "tagline": "Company tagline or slogan, empty string if none",
  "description": "1-2 sentence company description",
  "products_services": [
    {{"name": "Product/Service Name", "description": "One sentence description"}}
  ]
}}

Rules:
- products_services: list up to 8 items, only real offerings (not features/benefits)
- Return raw JSON only, no markdown wrappers, no explanation

WEBSITE CONTENT:
{markdown[:5000]}"""

        response = client.models.generate_content(
            model=model,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
            contents=prompt
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```[a-z]*\n?', '', text).rstrip('`').strip()
        return json.loads(text)

    except Exception as e:
        print(f"[Brand] Gemini analysis error: {e}")
        return {}


@dataclass
class BrandAssets:
    """Data class representing extracted brand assets."""
    brand_name: str = ""
    primary_color: str = "#F9C74F"
    secondary_color: str = "#0E0E0E"
    accent_color: str = "#FCF0D5"
    font_family: str = "Inter"
    logo_url: str = ""
    visual_style: str = ""
    tone_of_voice: str = ""
    tagline: str = ""
    description: str = ""
    products_services: list = field(default_factory=list)
    extracted_colors: list = field(default_factory=list)
    extracted_fonts: list = field(default_factory=list)
    extraction_schema_version: int = 2
    ui_theme: dict = field(default_factory=lambda: dict(DEFAULT_UI_THEME))

    def to_dict(self) -> Dict:
        return {
            "brand_name": self.brand_name,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "accent_color": self.accent_color,
            "font_family": self.font_family,
            "logo_url": self.logo_url,
            "visual_style": self.visual_style,
            "tone_of_voice": self.tone_of_voice,
            "tagline": self.tagline,
            "description": self.description,
            "products_services": self.products_services or [],
            "extracted_colors": self.extracted_colors or [],
            "extracted_fonts": self.extracted_fonts or [],
            "extraction_schema_version": self.extraction_schema_version or 2,
            "ui_theme": self.ui_theme or dict(DEFAULT_UI_THEME)
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "BrandAssets":
        return cls(
            brand_name=data.get("brand_name", ""),
            primary_color=data.get("primary_color", "#F9C74F"),
            secondary_color=data.get("secondary_color", "#0E0E0E"),
            accent_color=data.get("accent_color", "#FCF0D5"),
            font_family=data.get("font_family", "Inter"),
            logo_url=data.get("logo_url", ""),
            visual_style=data.get("visual_style", ""),
            tone_of_voice=data.get("tone_of_voice", ""),
            tagline=data.get("tagline", ""),
            description=data.get("description", ""),
            products_services=data.get("products_services", []) or [],
            extracted_colors=data.get("extracted_colors", []) or [],
            extracted_fonts=data.get("extracted_fonts", []) or [],
            extraction_schema_version=int(data.get("extraction_schema_version", 1) or 1),
            ui_theme=data.get("ui_theme") or dict(DEFAULT_UI_THEME)
        )


class BrandValidationError(Exception):
    """Exception raised for brand validation errors."""
    pass


class BrandExtractor:
    """Extracts brand assets from website URLs using Firecrawl."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the brand extractor.
        
        Args:
            api_key: Firecrawl API key. If not provided, uses FIRECRAWL_API_KEY env var.
        """
        self.api_key = api_key or FIRECRAWL_API_KEY
        if not self.api_key:
            raise ValueError("Firecrawl API key is required. Set FIRECRAWL_API_KEY environment variable.")
    
    def extract_brand_from_url(self, url: str, force_refresh: bool = False) -> BrandAssets:
        """
        Extract brand assets from a website URL.

        Phase 1 — Firecrawl (branding + markdown in one call):
          - branding: CSS design system → colors, logo, fonts. Deterministic.
          - markdown (onlyMainContent): clean text for LLM.
        Phase 2 — Gemini on markdown:
          - Extracts brand_name, products_services, tone_of_voice, tagline, description.
        """
        if not self._is_valid_url(url):
            raise BrandValidationError(f"Invalid URL: {url}")

        if not force_refresh:
            cached = _get_cached(url)
            if cached:
                palette = cached.get("extracted_colors") if isinstance(cached, dict) else None
                schema_version = int(cached.get("extraction_schema_version", 1) or 1) if isinstance(cached, dict) else 1
                # Backward compatibility: old cache entries were saved before extracted_colors existed
                if isinstance(palette, list) and len(palette) > 0 and schema_version >= 2:
                    return BrandAssets.from_dict(cached)

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Single call: branding (CSS-based) + markdown (for LLM)
            payload = {
                "url": url,
                "formats": ["branding", "markdown"],
                "onlyMainContent": True
            }

            print(f"[Brand] Scraping {url} ...")
            response = requests.post(FIRECRAWL_API_URL, headers=headers, json=payload, timeout=90)
            response.raise_for_status()

            result = response.json()
            if not result.get("success"):
                raise BrandValidationError(f"Firecrawl failed: {result.get('error', 'Unknown error')}")

            data       = result.get("data", {}) or {}
            branding   = data.get("branding", {}) or {}
            markdown   = data.get("markdown", "") or ""
            metadata   = data.get("metadata", {}) or {}

            # ── Phase 1: Colors from Firecrawl branding (CSS-parsed, deterministic) ──
            colors    = branding.get("colors", {}) or {}
            primary   = self._validate_hex_color(colors.get("primary")   or "#F9C74F")
            secondary = self._validate_hex_color(
                colors.get("secondary") or colors.get("textPrimary") or "#0E0E0E")
            accent    = self._validate_hex_color(colors.get("accent")    or "#FCF0D5")

            # ── Logo (images.logo is the reliable field from v2 branding) ──
            images   = branding.get("images", {}) or {}
            logo_url = (images.get("logo") or branding.get("logo") or
                        images.get("favicon") or metadata.get("ogImage") or "")

            # ── Font ──
            typography    = branding.get("typography", {}) or {}
            font_families = typography.get("fontFamilies", {}) or {}
            fonts_list    = branding.get("fonts", []) or []
            raw_font      = (font_families.get("primary") or font_families.get("heading") or
                             (fonts_list[0].get("family") if fonts_list else "") or "Inter")
            font_family   = self._sanitize_font_family(raw_font)

            # Keep full extracted fonts list for frontend display
            extracted_fonts = []
            for f in font_families.values():
                if isinstance(f, str) and f.strip():
                    extracted_fonts.append(self._sanitize_font_family(f.strip()))
            for f in fonts_list:
                fam = f.get("family") if isinstance(f, dict) else None
                if isinstance(fam, str) and fam.strip():
                    extracted_fonts.append(self._sanitize_font_family(fam.strip()))
            if font_family:
                extracted_fonts.append(font_family)
            extracted_fonts = [x for x in dict.fromkeys([f for f in extracted_fonts if f])]

            # ── Visual style hint from color scheme ──
            color_scheme = branding.get("colorScheme", "")

            # ── Brand name hint from metadata ──
            brand_name_hint = (metadata.get("ogSiteName") or
                               metadata.get("title", "").split(" - ")[0].strip() or
                               self._extract_domain_name(url))

            # ── Phase 2a: Gemini LLM on markdown for content-based attributes ──
            print(f"[Brand] Analyzing content with Gemini ...")
            llm = _analyze_content_with_gemini(markdown, brand_name_hint)

            # ── Phase 2b: Gemini generates full UI theme from ALL brand colors ──
            print(f"[Brand] Generating UI theme from {len(colors)} brand colors ...")
            ui_theme = _generate_ui_theme(colors, color_scheme)

            # Keep the full extracted site palette for frontend display (not just 3 core colors)
            extracted_palette = [primary, secondary, accent]
            hex_or_rgb = re.compile(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$|^rgb\(\d+,\s*\d+,\s*\d+\)$')
            for val in colors.values():
                if not isinstance(val, str):
                    continue
                v = val.strip()
                if not hex_or_rgb.match(v):
                    continue
                normalized = self._validate_hex_color(v)
                if normalized and normalized not in extracted_palette:
                    extracted_palette.append(normalized)

            brand_assets = BrandAssets(
                brand_name      = llm.get("brand_name") or brand_name_hint,
                primary_color   = primary,
                secondary_color = secondary,
                accent_color    = accent,
                font_family     = font_family,
                logo_url        = logo_url,
                visual_style    = color_scheme,
                tone_of_voice   = llm.get("tone_of_voice", ""),
                tagline         = llm.get("tagline", ""),
                description     = llm.get("description", ""),
                products_services = llm.get("products_services", []) or [],
                extracted_colors = extracted_palette,
                extracted_fonts  = extracted_fonts,
                extraction_schema_version = 2,
                ui_theme        = ui_theme
            )

            _set_cached(url, brand_assets.to_dict())
            return brand_assets

        except requests.RequestException as e:
            raise BrandValidationError(f"Failed to connect to Firecrawl API: {str(e)}")
        except BrandValidationError:
            raise
        except Exception as e:
            raise BrandValidationError(f"Extraction failed: {str(e)}")
    
    def preview_brand(self, url: str) -> Dict:
        """
        Preview brand extraction without saving. Returns raw extraction data.
        
        Args:
            url: The website URL to analyze
            
        Returns:
            Dictionary with brand assets and metadata
        """
        brand_assets = self.extract_brand_from_url(url)
        
        return {
            "success": True,
            "url": url,
            "brand_assets": brand_assets.to_dict(),
            "preview_mode": True
        }
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except Exception:
            return False
    
    def _validate_hex_color(self, color: str) -> str:
        """Validate and normalize hex color code."""
        if not color:
            return "#F9C74F"
        
        # Remove whitespace
        color = color.strip()
        
        # Check if valid hex
        pattern = r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
        if re.match(pattern, color):
            return color.upper()
        
        # Try to convert rgb() to hex
        rgb_pattern = r'rgb\((\d+),\s*(\d+),\s*(\d+)\)'
        match = re.match(rgb_pattern, color)
        if match:
            r, g, b = map(int, match.groups())
            return f"#{r:02x}{g:02x}{b:02x}".upper()
        
        # Return default if invalid
        return "#F9C74F"
    
    def _sanitize_font_family(self, font: str) -> str:
        """Sanitize font family name."""
        if not font:
            return "Inter"
        
        # Remove dangerous characters
        font = re.sub(r'[<>"\']', '', font)
        
        # Common font fallbacks
        common_fonts = ["Inter", "Roboto", "Open Sans", "Helvetica", "Arial", "Segoe UI"]
        
        # Check if it's a common font
        font_clean = font.split(',')[0].strip()
        if any(common.lower() in font_clean.lower() for common in common_fonts):
            return font_clean
        
        return font.strip()
    
    def _extract_domain_name(self, url: str) -> str:
        """Extract domain name from URL for brand name fallback."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            # Remove TLD
            name = domain.split('.')[0]
            return name.capitalize()
        except Exception:
            return "Unknown Brand"


def validate_brand_assets(assets: Dict) -> Tuple[bool, list]:
    """
    Validate brand assets dictionary.
    
    Args:
        assets: Dictionary containing brand assets
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Validate colors (if provided)
    hex_pattern = r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
    for color_field in ["primary_color", "secondary_color", "accent_color"]:
        color = assets.get(color_field, "")
        if color and not re.match(hex_pattern, color):
            errors.append(f"Invalid hex color format for {color_field}: {color}")
    
    # Validate logo URL if provided
    logo_url = assets.get("logo_url", "")
    if logo_url:
        try:
            result = urlparse(logo_url)
            if not all([result.scheme in ['http', 'https'], result.netloc]):
                errors.append("Invalid logo URL format")
        except Exception:
            errors.append("Invalid logo URL")
    
    # Validate products_services structure if provided
    ps = assets.get("products_services")
    if ps is not None and not isinstance(ps, list):
        errors.append("products_services must be a list")
    
    return len(errors) == 0, errors


# Convenience function for direct usage
def extract_brand(url: str, api_key: Optional[str] = None) -> Dict:
    """
    Convenience function to extract brand from URL.
    
    Args:
        url: Website URL to analyze
        api_key: Optional Firecrawl API key
        
    Returns:
        Dictionary with brand assets or error
    """
    try:
        extractor = BrandExtractor(api_key)
        brand = extractor.extract_brand_from_url(url)
        return {
            "success": True,
            "brand_assets": brand.to_dict()
        }
    except BrandValidationError as e:
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


if __name__ == "__main__":
    # Test the extractor
    test_url = "https://obsidianlogic.ai"
    
    print(f"Testing brand extraction for: {test_url}")
    print("-" * 50)
    
    result = extract_brand(test_url)
    
    if result["success"]:
        assets = result["brand_assets"]
        print(f"✓ Brand Name: {assets['brand_name']}")
        print(f"✓ Primary Color: {assets['primary_color']}")
        print(f"✓ Secondary Color: {assets['secondary_color']}")
        print(f"✓ Font Family: {assets['font_family']}")
        print(f"✓ Visual Style: {assets['visual_style']}")
    else:
        print(f"✗ Error: {result['error']}")
