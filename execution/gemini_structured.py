"""
gemini_structured.py
--------------------
Unified LLM client for Voice Engine + CRM Hub rebuild.

Strategy:
  1. OpenRouter (free models: Llama 3.3 70B, Gemma 3 27B) — primary
  2. Google Gemini (gemini-2.5-pro-exp or configured model) — fallback

All calls enforce structured JSON output with schema validation and retry logic.
Exponential backoff on rate limits. Structured logging throughout.
"""

import json
import os
import re
import time
import threading
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# Quota tracking (lazy import to avoid circular deps)
def _track(provider: str, success: bool, error: str = "", is_rate_limit: bool = False):
    try:
        from execution.quota_monitor import track_call
        track_call(provider, success, error, is_rate_limit)
    except Exception:
        pass  # Never let tracking break LLM calls

# ─── OpenRouter config ────────────────────────────────────────────────────────
try:
    from openai import OpenAI as _OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

_OR_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
_OR_PRIMARY = os.environ.get("OPENROUTER_PRIMARY_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
_OR_FALLBACK = os.environ.get("OPENROUTER_FALLBACK_MODEL", "google/gemma-3-27b-it:free")
_OR_BASE_URL = "https://openrouter.ai/api/v1"
_OR_MIN_INTERVAL = 4.0  # seconds between calls (stay under 16 RPM free tier)
_OR_RATE_LOCK = threading.Lock()
_OR_LAST_CALL: float = 0.0

# ─── Gemini config ────────────────────────────────────────────────────────────
try:
    from google import genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

_GEMINI_KEY = os.environ.get("GOOGLE_GEMINI_API_KEY", "")
_GEMINI_MODEL = os.environ.get("GEMINI_CRM_MODEL", "gemini-3.1-pro-preview")

# ─── Shared constants ─────────────────────────────────────────────────────────
_MAX_RETRIES = 3
_DEFAULT_MAX_TOKENS = 1200
_DEFAULT_TEMPERATURE = 0.2


# ═══════════════════════════════════════════════════════════════════════════════
# JSON extraction helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> Dict:
    """Extract the first JSON object from an LLM response string.

    Handles:
      - Direct JSON
      - Markdown code fences (```json ... ```)
      - JSON embedded in prose ({...} extraction)
    """
    if not text:
        return {}
    text = text.strip()
    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Find first {...} block
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _validate_schema(result: Dict, required_fields: List[str]) -> bool:
    """Check that all required_fields are present in result."""
    if not result:
        return False
    for field in required_fields:
        if field not in result:
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# OpenRouter path
# ═══════════════════════════════════════════════════════════════════════════════

def _or_rate_wait() -> None:
    """Enforce minimum interval between OpenRouter calls."""
    global _OR_LAST_CALL
    with _OR_RATE_LOCK:
        now = time.monotonic()
        elapsed = now - _OR_LAST_CALL
        if elapsed < _OR_MIN_INTERVAL:
            time.sleep(_OR_MIN_INTERVAL - elapsed)
        _OR_LAST_CALL = time.monotonic()


def _or_client() -> Optional[Any]:
    """Build OpenRouter client (OpenAI-compatible)."""
    if not _OPENAI_AVAILABLE:
        return None
    key = _OR_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return None
    return _OpenAI(api_key=key, base_url=_OR_BASE_URL)


def _call_openrouter(
    messages: List[Dict[str, str]],
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    temperature: float = _DEFAULT_TEMPERATURE,
    quick_fail: bool = False,
) -> Dict:
    """Call OpenRouter with retry. Returns parsed JSON dict or {}."""
    client = _or_client()
    if not client:
        return {}

    models = [_OR_PRIMARY]
    if _OR_PRIMARY != _OR_FALLBACK:
        models.append(_OR_FALLBACK)

    for model in models:
        for attempt in range(_MAX_RETRIES):
            try:
                _or_rate_wait()
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    extra_headers={
                        "HTTP-Referer": "https://tahir-70872--linkedin-post-generator-web.modal.run",
                        "X-Title": "LinkedIn CRM Analyzer",
                    },
                )
                content = response.choices[0].message.content or ""
                result = _extract_json(content)
                if result:
                    _track("openrouter", True)
                    return result
                print(f"[LLM:OR] Empty JSON from {model}, attempt {attempt + 1}/{_MAX_RETRIES}")
                continue

            except Exception as e:
                err = str(e)
                is_rate = any(x in err for x in ("429", "rate limit", "Rate limit", "RESOURCE_EXHAUSTED"))
                is_down = any(x in err for x in ("503", "502", "unavailable", "overloaded"))

                if is_rate:
                    _track("openrouter", False, err, is_rate_limit=True)
                    if quick_fail:
                        print(f"[LLM:OR] {model} rate-limited — quick_fail, skipping")
                        return {}
                    wait = 62.0
                    print(f"[LLM:OR] {model} rate-limited — waiting {wait:.0f}s")
                    time.sleep(wait)
                    continue

                _track("openrouter", False, err)
                if is_down and attempt < _MAX_RETRIES - 1:
                    print(f"[LLM:OR] {model} unavailable, retrying in 5s...")
                    time.sleep(5.0)
                    continue

                print(f"[LLM:OR] {model} error (attempt {attempt + 1}): {e}")
                break  # try fallback model

    _track("openrouter", False, "All OpenRouter models exhausted")
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# Gemini path
# ═══════════════════════════════════════════════════════════════════════════════

def _call_gemini(
    prompt: str,
    system_instruction: str = "",
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    temperature: float = _DEFAULT_TEMPERATURE,
) -> Dict:
    """Call Google Gemini and parse JSON response. Returns {} on failure."""
    if not _GENAI_AVAILABLE or not _GEMINI_KEY:
        print("[LLM:Gemini] SDK or API key not available")
        return {}

    client = genai.Client(api_key=_GEMINI_KEY)

    for attempt in range(_MAX_RETRIES):
        try:
            config = genai.types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            )
            if system_instruction:
                config.system_instruction = system_instruction

            response = client.models.generate_content(
                model=_GEMINI_MODEL,
                contents=prompt,
                config=config,
            )
            text = response.text or ""
            result = _extract_json(text)
            if result:
                _track("gemini", True)
                return result
            print(f"[LLM:Gemini] Empty JSON, attempt {attempt + 1}/{_MAX_RETRIES}. Raw text: {repr(text)}")

        except Exception as e:
            err = str(e)
            is_rate = any(x in err for x in ("429", "RESOURCE_EXHAUSTED", "rate"))
            if is_rate:
                _track("gemini", False, err, is_rate_limit=True)
                if attempt < _MAX_RETRIES - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"[LLM:Gemini] Rate limited — backoff {wait}s")
                    time.sleep(wait)
                    continue
            else:
                _track("gemini", False, err)
            print(f"[LLM:Gemini] Error (attempt {attempt + 1}): {e}")
            if attempt >= _MAX_RETRIES - 1:
                break
            time.sleep(2 ** attempt)

    _track("gemini", False, "All Gemini retries exhausted")
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    required_fields: Optional[List[str]] = None,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    temperature: float = _DEFAULT_TEMPERATURE,
    quick_fail: bool = False,
    gemini_primary: bool = False,
) -> Dict:
    """Call LLM with structured JSON enforcement.

    Strategy: OpenRouter first (free), Gemini fallback.
    When gemini_primary=True, skips OpenRouter and uses Gemini directly
    (use for high-value single calls like profile analysis).

    Args:
        system_prompt: System instruction for the LLM.
        user_prompt: User message / data to analyze.
        required_fields: List of keys that MUST exist in response JSON.
        max_tokens: Max output tokens.
        temperature: Sampling temperature (0.0-1.0).
        quick_fail: If True, skip waits on rate limit (for bulk ingestion).
        gemini_primary: If True, skip OpenRouter and use Gemini directly.

    Returns:
        Validated dict with structured output, or {} on complete failure.
    """
    required = required_fields or []

    # ── Maintenance mode check ────────────────────────────────────────────
    try:
        from execution.quota_monitor import is_maintenance_mode
        if is_maintenance_mode():
            print("[LLM] Maintenance mode active — skipping LLM call")
            return {}
    except Exception:
        pass

    # ── Attempt 1: OpenRouter (skipped when gemini_primary=True) ────────────
    or_available = _OPENAI_AVAILABLE and bool(_OR_API_KEY) and not gemini_primary
    if or_available:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = _call_openrouter(messages, max_tokens, temperature, quick_fail)
        if result and _validate_schema(result, required):
            return result
        if result and required:
            print(f"[LLM] OpenRouter response missing required fields: {[f for f in required if f not in result]}")

    # ── Attempt 2: Gemini fallback ─────────────────────────────────────────
    gemini_available = _GENAI_AVAILABLE and bool(_GEMINI_KEY)
    if gemini_available:
        result = _call_gemini(user_prompt, system_prompt, max_tokens, temperature)
        if result and _validate_schema(result, required):
            return result
        if result and required:
            print(f"[LLM] Gemini response missing required fields: {[f for f in required if f not in result]}")

    # ── Both failed ────────────────────────────────────────────────────────
    print("[LLM] All providers exhausted — returning empty dict")
    return {}


def call_llm_text(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2000,
    temperature: float = 0.4,
) -> str:
    """Call LLM and return raw text (for message drafting, not JSON).

    Strategy: OpenRouter first, Gemini fallback.
    Returns plain text string, or "" on failure.
    """
    # ── OpenRouter ─────────────────────────────────────────────────────────
    or_available = _OPENAI_AVAILABLE and bool(_OR_API_KEY)
    if or_available:
        client = _or_client()
        if client:
            try:
                _or_rate_wait()
                response = client.chat.completions.create(
                    model=_OR_PRIMARY,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    extra_headers={
                        "HTTP-Referer": "https://tahir-70872--linkedin-post-generator-web.modal.run",
                        "X-Title": "LinkedIn CRM Analyzer",
                    },
                )
                text = (response.choices[0].message.content or "").strip()
                if text:
                    return text
            except Exception as e:
                print(f"[LLM:OR] text call error: {e}")

    # ── Gemini ─────────────────────────────────────────────────────────────
    gemini_available = _GENAI_AVAILABLE and bool(_GEMINI_KEY)
    if gemini_available:
        try:
            client = genai.Client(api_key=_GEMINI_KEY)
            config = genai.types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_prompt,
            )
            response = client.models.generate_content(
                model=_GEMINI_MODEL,
                contents=user_prompt,
                config=config,
            )
            return (response.text or "").strip()
        except Exception as e:
            print(f"[LLM:Gemini] text call error: {e}")

    return ""


def is_openrouter_available() -> bool:
    """Check if OpenRouter is configured."""
    return _OPENAI_AVAILABLE and bool(_OR_API_KEY)


def is_gemini_available() -> bool:
    """Check if Gemini is configured."""
    return _GENAI_AVAILABLE and bool(_GEMINI_KEY)
