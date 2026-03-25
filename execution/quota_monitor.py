"""
quota_monitor.py
----------------
Tracks LLM API usage, detects quota issues, and sends email alerts.

Counters are module-level (in-memory per container). Reset on container restart.
Email alerts use Gmail SMTP with App Password.

Usage:
    from execution.quota_monitor import track_call, get_health, check_and_alert
"""

import os
import time
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional

from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────
_ALERT_EMAIL = os.environ.get("ALERT_EMAIL_TO", "shahbazh8542@gmail.com")
_SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "")
_SMTP_PASSWORD = os.environ.get("SMTP_APP_PASSWORD", "")
_SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
_SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

# Thresholds
_FAILURE_RATE_THRESHOLD = 0.5   # Alert if >50% of recent calls fail
_CONSECUTIVE_FAIL_THRESHOLD = 5  # Alert after 5 consecutive failures
_RATE_LIMIT_THRESHOLD = 3       # Alert after 3 rate limits in a window

# ─── Counters (thread-safe) ──────────────────────────────────────────────────
_lock = threading.Lock()

_stats = {
    "total_calls": 0,
    "successful_calls": 0,
    "failed_calls": 0,
    "rate_limited_calls": 0,
    "consecutive_failures": 0,
    "last_success_time": None,
    "last_failure_time": None,
    "last_failure_error": "",
    "last_alert_time": 0,
    "alerts_sent": 0,
    "started_at": time.time(),
    # Per-provider breakdown
    "openrouter_calls": 0,
    "openrouter_failures": 0,
    "openrouter_rate_limits": 0,
    "gemini_calls": 0,
    "gemini_failures": 0,
    "gemini_rate_limits": 0,
}

# Rolling window for failure rate calculation (last N calls)
_WINDOW_SIZE = 20
_recent_results = []  # list of booleans: True=success, False=failure

# ─── Maintenance mode ────────────────────────────────────────────────────────
_maintenance_mode = False
_maintenance_reason = ""
_maintenance_resume_time = ""


def is_maintenance_mode() -> bool:
    """Check if system is in maintenance mode."""
    return _maintenance_mode


def get_maintenance_info() -> Dict:
    """Get maintenance mode details."""
    return {
        "active": _maintenance_mode,
        "reason": _maintenance_reason,
        "resume_time": _maintenance_resume_time,
    }


def set_maintenance_mode(active: bool, reason: str = "", resume_time: str = ""):
    """Toggle maintenance mode."""
    global _maintenance_mode, _maintenance_reason, _maintenance_resume_time
    _maintenance_mode = active
    _maintenance_reason = reason
    _maintenance_resume_time = resume_time
    action = "ACTIVATED" if active else "DEACTIVATED"
    print(f"[QuotaMonitor] Maintenance mode {action}: {reason}")
    if active:
        _send_alert(
            subject="🔧 Maintenance Mode ACTIVATED",
            body=f"Maintenance mode has been activated.\n\nReason: {reason}\nEstimated resume: {resume_time or 'TBD'}\n\nAll LLM calls are now blocked. Toggle off via /api/admin/maintenance when ready.",
        )


# ─── Tracking ────────────────────────────────────────────────────────────────

def track_call(
    provider: str,
    success: bool,
    error: str = "",
    is_rate_limit: bool = False,
):
    """Record an LLM call result. Called from gemini_structured.py.

    Args:
        provider: 'openrouter' or 'gemini'
        success: Whether the call produced a valid result
        error: Error message if failed
        is_rate_limit: Whether the failure was a rate limit
    """
    with _lock:
        _stats["total_calls"] += 1

        if provider == "openrouter":
            _stats["openrouter_calls"] += 1
        elif provider == "gemini":
            _stats["gemini_calls"] += 1

        if success:
            _stats["successful_calls"] += 1
            _stats["consecutive_failures"] = 0
            _stats["last_success_time"] = time.time()
        else:
            _stats["failed_calls"] += 1
            _stats["consecutive_failures"] += 1
            _stats["last_failure_time"] = time.time()
            _stats["last_failure_error"] = error[:200]

            if provider == "openrouter":
                _stats["openrouter_failures"] += 1
            elif provider == "gemini":
                _stats["gemini_failures"] += 1

        if is_rate_limit:
            _stats["rate_limited_calls"] += 1
            if provider == "openrouter":
                _stats["openrouter_rate_limits"] += 1
            elif provider == "gemini":
                _stats["gemini_rate_limits"] += 1

        # Update rolling window
        _recent_results.append(success)
        if len(_recent_results) > _WINDOW_SIZE:
            _recent_results.pop(0)

    # Check for alert conditions (non-blocking)
    _check_alert_conditions(error)


def _check_alert_conditions(latest_error: str = ""):
    """Evaluate whether to send an alert email."""
    now = time.time()

    # Rate limit: max 1 alert per 10 minutes
    if now - _stats["last_alert_time"] < 600:
        return

    alert_reason = None

    # Condition 1: Too many consecutive failures
    if _stats["consecutive_failures"] >= _CONSECUTIVE_FAIL_THRESHOLD:
        alert_reason = f"🚨 {_stats['consecutive_failures']} consecutive LLM failures"

    # Condition 2: High failure rate in recent window
    if len(_recent_results) >= 10:
        fail_count = sum(1 for r in _recent_results if not r)
        fail_rate = fail_count / len(_recent_results)
        if fail_rate >= _FAILURE_RATE_THRESHOLD:
            alert_reason = f"🚨 High failure rate: {fail_rate:.0%} of last {len(_recent_results)} calls failed"

    # Condition 3: Multiple rate limits
    if _stats["rate_limited_calls"] >= _RATE_LIMIT_THRESHOLD:
        or_rl = _stats["openrouter_rate_limits"]
        gem_rl = _stats["gemini_rate_limits"]
        alert_reason = f"⚠️ Rate limit threshold reached — OpenRouter: {or_rl}, Gemini: {gem_rl}"

    if alert_reason:
        body = _build_alert_body(alert_reason, latest_error)
        _send_alert(
            subject=f"LLM Quota Alert — {alert_reason[:60]}",
            body=body,
        )
        with _lock:
            _stats["last_alert_time"] = now
            _stats["alerts_sent"] += 1


def _build_alert_body(reason: str, latest_error: str) -> str:
    """Build a detailed alert email body."""
    uptime = time.time() - _stats["started_at"]
    uptime_str = f"{uptime / 3600:.1f} hours" if uptime > 3600 else f"{uptime / 60:.1f} minutes"

    return f"""LLM Quota Health Alert
═══════════════════════

{reason}

── Current Stats ──────────────────────
Total calls:          {_stats['total_calls']}
Successful:           {_stats['successful_calls']}
Failed:               {_stats['failed_calls']}
Rate limited:         {_stats['rate_limited_calls']}
Consecutive failures: {_stats['consecutive_failures']}
Uptime:               {uptime_str}

── Per Provider ───────────────────────
OpenRouter:  {_stats['openrouter_calls']} calls, {_stats['openrouter_failures']} fails, {_stats['openrouter_rate_limits']} rate limits
Gemini:      {_stats['gemini_calls']} calls, {_stats['gemini_failures']} fails, {_stats['gemini_rate_limits']} rate limits

── Latest Error ───────────────────────
{latest_error or 'N/A'}

── Actions ────────────────────────────
1. FIX NOW: Check API keys and quotas, then the system will auto-recover.
2. PAUSE:   POST /api/admin/maintenance with {{"active": true, "reason": "...", "resume_time": "..."}}
            This shows a maintenance page to users and blocks all LLM calls.
3. RESUME:  POST /api/admin/maintenance with {{"active": false}}

Dashboard: https://tahir-70872--linkedin-post-generator-web.modal.run
"""


def _send_alert(subject: str, body: str):
    """Send an email alert via SMTP."""
    if not _SMTP_EMAIL or not _SMTP_PASSWORD:
        print(f"[QuotaMonitor] ALERT (email not configured): {subject}")
        print(f"[QuotaMonitor] {body[:300]}")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = _SMTP_EMAIL
        msg["To"] = _ALERT_EMAIL
        msg["Subject"] = f"[Obsidian Logic] {subject}"
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
            server.starttls()
            server.login(_SMTP_EMAIL, _SMTP_PASSWORD)
            server.send_message(msg)

        print(f"[QuotaMonitor] Alert email sent: {subject}")
    except Exception as e:
        print(f"[QuotaMonitor] Failed to send alert email: {e}")
        print(f"[QuotaMonitor] Alert content: {subject} — {body[:200]}")


# ─── Health API ──────────────────────────────────────────────────────────────

def get_health() -> Dict:
    """Return current LLM quota health status."""
    with _lock:
        total = _stats["total_calls"]
        failed = _stats["failed_calls"]
        success_rate = (_stats["successful_calls"] / total * 100) if total > 0 else 100.0

        # Determine status
        if _maintenance_mode:
            status = "maintenance"
        elif _stats["consecutive_failures"] >= _CONSECUTIVE_FAIL_THRESHOLD:
            status = "critical"
        elif success_rate < 50 and total >= 10:
            status = "degraded"
        elif _stats["rate_limited_calls"] >= _RATE_LIMIT_THRESHOLD:
            status = "warning"
        else:
            status = "healthy"

        uptime = time.time() - _stats["started_at"]

        return {
            "status": status,
            "maintenance_mode": get_maintenance_info(),
            "total_calls": total,
            "successful_calls": _stats["successful_calls"],
            "failed_calls": failed,
            "rate_limited_calls": _stats["rate_limited_calls"],
            "consecutive_failures": _stats["consecutive_failures"],
            "success_rate_percent": round(success_rate, 1),
            "last_success": _stats["last_success_time"],
            "last_failure": _stats["last_failure_time"],
            "last_error": _stats["last_failure_error"],
            "alerts_sent": _stats["alerts_sent"],
            "uptime_seconds": round(uptime),
            "providers": {
                "openrouter": {
                    "calls": _stats["openrouter_calls"],
                    "failures": _stats["openrouter_failures"],
                    "rate_limits": _stats["openrouter_rate_limits"],
                },
                "gemini": {
                    "calls": _stats["gemini_calls"],
                    "failures": _stats["gemini_failures"],
                    "rate_limits": _stats["gemini_rate_limits"],
                },
            },
            "email_configured": bool(_SMTP_EMAIL and _SMTP_PASSWORD),
            "alert_recipient": _ALERT_EMAIL[:3] + "***" + _ALERT_EMAIL[_ALERT_EMAIL.index("@"):] if "@" in _ALERT_EMAIL else "***",
        }


def reset_stats():
    """Reset all counters (for testing or after fixing issues)."""
    with _lock:
        for key in _stats:
            if isinstance(_stats[key], int):
                _stats[key] = 0
            elif isinstance(_stats[key], float):
                _stats[key] = 0.0
            elif _stats[key] is None or isinstance(_stats[key], str):
                _stats[key] = _stats[key]  # keep as-is
        _stats["started_at"] = time.time()
        _recent_results.clear()
    print("[QuotaMonitor] Stats reset")
