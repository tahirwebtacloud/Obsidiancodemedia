"""
OpenRouter Client
Wraps the OpenAI-compatible OpenRouter API for LLM inference.
Primary model: meta-llama/llama-3.3-70b-instruct:free  (70B, 128K ctx, free)
Fallback model: google/gemma-3-27b-it:free              (27B, 131K ctx, free)

No quota issues — OpenRouter free tier is rate-limited per-minute but not per-day.
Built-in retry with exponential backoff for transient failures.
"""

import json
import os
import re
import time
import threading
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False


_PRIMARY_MODEL = os.environ.get(
    "OPENROUTER_PRIMARY_MODEL", "meta-llama/llama-3.3-70b-instruct:free"
)
_FALLBACK_MODEL = os.environ.get(
    "OPENROUTER_FALLBACK_MODEL", "google/gemma-3-27b-it:free"
)
_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
_BASE_URL = "https://openrouter.ai/api/v1"

# Free tier limits: 8 RPM per model, 16 RPM globally across all free models
_DEFAULT_MAX_TOKENS = 800
_MAX_RETRIES = 3
_MIN_CALL_INTERVAL = 4.0   # seconds — keeps us under 16 RPM global limit (15 RPM effective)
_RATE_LIMIT_WAIT = 62.0    # seconds to wait on 429 before retrying (full 1-min window reset)

# Global rate limiter shared across all calls in this process
_rate_lock = threading.Lock()
_last_call_time: float = 0.0


def _rate_limit_wait() -> None:
    """Block until the minimum interval since the last call has elapsed."""
    global _last_call_time
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_call_time
        if elapsed < _MIN_CALL_INTERVAL:
            time.sleep(_MIN_CALL_INTERVAL - elapsed)
        _last_call_time = time.monotonic()


def _parse_reset_wait(err_str: str) -> float:
    """Extract X-RateLimit-Reset (ms epoch) from error string and return seconds to wait."""
    try:
        match = re.search(r"X-RateLimit-Reset['\"]:\s*['\"]?(\d+)", err_str)
        if match:
            reset_ms = int(match.group(1))
            now_ms = int(time.time() * 1000)
            wait_s = max(0.0, (reset_ms - now_ms) / 1000.0)
            return min(wait_s + 2.0, 70.0)  # clamp: never wait more than 70s
    except Exception:
        pass
    return _RATE_LIMIT_WAIT


def _build_client() -> Optional[Any]:
    """Build an OpenAI-compatible client pointed at OpenRouter."""
    if not _OPENAI_AVAILABLE:
        print("[OpenRouter] openai package not installed — run: pip install openai>=1.30.0")
        return None
    key = _API_KEY or os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        print("[OpenRouter] OPENROUTER_API_KEY not set in environment")
        return None
    return OpenAI(
        api_key=key,
        base_url=_BASE_URL,
    )


def _extract_json(text: str) -> Dict:
    """Extract the first JSON object from a model response."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try stripping markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Try finding the first {...} block
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def chat_completion_json(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    temperature: float = 0.2,
    quick_fail: bool = False,
) -> Dict:
    """
    Call OpenRouter and parse the response as JSON.

    Tries primary model first, falls back to fallback model on failure.
    When quick_fail=True (bulk ingestion), returns {} immediately on rate limit
    instead of waiting 60s, so callers can use rule-based fallback.

    Returns: parsed dict, or {} on complete failure.
    """
    client = _build_client()
    if not client:
        return {}

    target_model = model or _PRIMARY_MODEL
    models_to_try = [target_model]
    if target_model != _FALLBACK_MODEL:
        models_to_try.append(_FALLBACK_MODEL)

    for attempt_model in models_to_try:
        for attempt in range(_MAX_RETRIES):
            try:
                _rate_limit_wait()  # enforce minimum interval before every call
                response = client.chat.completions.create(
                    model=attempt_model,
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
                    return result
                print(f"[OpenRouter] Empty JSON from {attempt_model}, attempt {attempt + 1}")
                continue

            except Exception as e:
                err_str = str(e)
                is_rate_limit = any(x in err_str for x in ("429", "rate limit", "Rate limit", "RESOURCE_EXHAUSTED"))
                is_unavailable = any(x in err_str for x in ("503", "502", "unavailable", "overloaded"))

                if is_rate_limit:
                    if quick_fail:
                        print(f"[OpenRouter] {attempt_model} rate-limited — quick_fail mode, skipping to rule-based")
                        return {}
                    wait_s = _parse_reset_wait(err_str)
                    print(f"[OpenRouter] {attempt_model} rate-limited — waiting {wait_s:.0f}s for reset...")
                    time.sleep(wait_s)
                    continue

                if is_unavailable and attempt < _MAX_RETRIES - 1:
                    print(f"[OpenRouter] {attempt_model} unavailable, retrying in 5s...")
                    time.sleep(5.0)
                    continue

                print(f"[OpenRouter] {attempt_model} error (attempt {attempt + 1}): {e}")
                break  # Try fallback model

    print("[OpenRouter] All models and retries exhausted, returning empty dict")
    return {}


def is_available() -> bool:
    """Check if OpenRouter is configured and the openai package is installed."""
    return _OPENAI_AVAILABLE and bool(_API_KEY or os.environ.get("OPENROUTER_API_KEY", ""))
