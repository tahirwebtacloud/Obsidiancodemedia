"""
Schedule Ledger - Local source of truth for content calendar.
Prevents double-posting, tracks themes, and syncs with MASTER_CONTENT_CALENDAR.csv.
"""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CALENDAR_PATH = PROJECT_ROOT / "data" / "processed" / "MASTER_CONTENT_CALENDAR.csv"
LEDGER_PATH = Path(__file__).parent / "config" / "schedule_ledger.json"
RULES_PATH = Path(__file__).parent / "config" / "publishing_rules.json"

ET = ZoneInfo("America/New_York")


def load_rules():
    with open(RULES_PATH) as f:
        return json.load(f)


def load_ledger():
    """Load or initialize the schedule ledger."""
    if LEDGER_PATH.exists():
        with open(LEDGER_PATH) as f:
            return json.load(f)
    return {"scheduled": [], "published": [], "themes": {"current_week": None, "current_month": None, "history": []}}


def save_ledger(ledger):
    """Save ledger to disk."""
    with open(LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2, default=str)


def load_calendar():
    """Load MASTER_CONTENT_CALENDAR.csv entries."""
    entries = []
    if not CALENDAR_PATH.exists():
        return entries
    with open(CALENDAR_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(row)
    return entries


def get_upcoming_posts():
    """Get all scheduled (not yet published) posts."""
    ledger = load_ledger()
    now = datetime.now(ET)
    upcoming = []
    for entry in ledger.get("scheduled", []):
        scheduled_dt = datetime.fromisoformat(entry["scheduled_time"])
        if scheduled_dt > now:
            upcoming.append(entry)
    return sorted(upcoming, key=lambda x: x["scheduled_time"])


def get_recent_posts(days=14):
    """Get posts from the last N days (published + scheduled)."""
    ledger = load_ledger()
    cutoff = datetime.now(ET) - timedelta(days=days)
    recent = []

    for entry in ledger.get("published", []) + ledger.get("scheduled", []):
        entry_dt = datetime.fromisoformat(entry.get("scheduled_time", entry.get("published_time", "")))
        if entry_dt > cutoff:
            recent.append(entry)

    # Also pull from MASTER_CONTENT_CALENDAR
    for row in load_calendar():
        if row.get("Status") == "Published" and row.get("Date Posted"):
            try:
                post_dt = datetime.strptime(row["Date Posted"], "%Y-%m-%d").replace(tzinfo=ET)
                if post_dt > cutoff:
                    recent.append({
                        "title": row.get("Title", ""),
                        "published_time": row["Date Posted"],
                        "source": "calendar",
                        "impressions": row.get("Impressions", ""),
                    })
            except ValueError:
                continue

    return sorted(recent, key=lambda x: x.get("scheduled_time", x.get("published_time", "")), reverse=True)


def check_conflicts(proposed_time_iso):
    """
    Check if a proposed publish time conflicts with existing schedule.

    Returns:
        dict with 'clear' (bool), 'conflicts' (list), and 'reason' (str)
    """
    rules = load_rules()
    proposed = datetime.fromisoformat(proposed_time_iso)
    min_gap_hours = rules["scheduling"]["min_hours_between_posts"]
    max_per_week = rules["scheduling"]["max_posts_per_week"]
    blackout_days = rules["scheduling"]["blackout_days"]

    conflicts = []
    result = {"clear": True, "conflicts": [], "reason": ""}

    # Blackout day check
    day_name = proposed.strftime("%A")
    if day_name in blackout_days:
        result["clear"] = False
        result["reason"] = f"{day_name} is a blackout day (no publishing on weekends)"
        return result

    # Check min hours between posts
    ledger = load_ledger()
    all_posts = ledger.get("scheduled", []) + ledger.get("published", [])

    for entry in all_posts:
        entry_time = datetime.fromisoformat(entry.get("scheduled_time", entry.get("published_time", "")))
        gap = abs((proposed - entry_time).total_seconds()) / 3600

        if gap < min_gap_hours:
            conflicts.append({
                "title": entry.get("title", "Unknown"),
                "time": str(entry_time),
                "gap_hours": round(gap, 1),
            })

    if conflicts:
        result["clear"] = False
        result["conflicts"] = conflicts
        result["reason"] = f"Too close to existing post(s). Minimum gap: {min_gap_hours}h"
        return result

    # Check weekly limit
    week_start = proposed - timedelta(days=proposed.weekday())
    week_end = week_start + timedelta(days=7)
    week_posts = [
        e for e in all_posts
        if week_start <= datetime.fromisoformat(e.get("scheduled_time", e.get("published_time", ""))) < week_end
    ]
    if len(week_posts) >= max_per_week:
        result["clear"] = False
        result["reason"] = f"Already {len(week_posts)} posts this week (max: {max_per_week})"
        return result

    return result


def get_next_optimal_slot():
    """
    Calculate the next optimal publish time based on rules.
    Returns ISO 8601 timestamp.
    """
    rules = load_rules()
    optimal_days = rules["scheduling"]["optimal_days"]
    optimal_time = rules["scheduling"]["optimal_time_et"]
    hour, minute = map(int, optimal_time.split(":"))

    now = datetime.now(ET)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # Find the next optimal day
    for days_ahead in range(1, 14):
        candidate = (now + timedelta(days=days_ahead)).replace(
            hour=hour, minute=minute, second=0, microsecond=0, tzinfo=ET
        )
        day_name = candidate.strftime("%A")

        if day_name in optimal_days:
            conflict = check_conflicts(candidate.isoformat())
            if conflict["clear"]:
                return candidate.isoformat()

    # Fallback to any non-blackout day
    fallback_time = rules["scheduling"]["fallback_time_et"]
    fb_hour, fb_minute = map(int, fallback_time.split(":"))
    for days_ahead in range(1, 14):
        candidate = (now + timedelta(days=days_ahead)).replace(
            hour=fb_hour, minute=fb_minute, second=0, microsecond=0, tzinfo=ET
        )
        day_name = candidate.strftime("%A")
        if day_name not in rules["scheduling"]["blackout_days"]:
            conflict = check_conflicts(candidate.isoformat())
            if conflict["clear"]:
                return candidate.isoformat()

    return None


def add_scheduled_post(title, text, scheduled_time, media_path=None,
                       platform="linkedin", blotato_id=None, theme=None):
    """Add a post to the schedule ledger."""
    ledger = load_ledger()
    entry = {
        "title": title,
        "text_preview": text[:150] + "..." if len(text) > 150 else text,
        "full_text_chars": len(text),
        "scheduled_time": scheduled_time,
        "platform": platform,
        "media_path": str(media_path) if media_path else None,
        "blotato_submission_id": blotato_id,
        "theme": theme,
        "status": "scheduled",
        "created_at": datetime.now(ET).isoformat(),
    }
    ledger["scheduled"].append(entry)
    save_ledger(ledger)
    return entry


def mark_published(blotato_id, public_url=None):
    """Move a scheduled post to published."""
    ledger = load_ledger()
    for i, entry in enumerate(ledger.get("scheduled", [])):
        if entry.get("blotato_submission_id") == blotato_id:
            entry["status"] = "published"
            entry["published_time"] = datetime.now(ET).isoformat()
            entry["public_url"] = public_url
            ledger["published"].append(entry)
            ledger["scheduled"].pop(i)
            save_ledger(ledger)
            return entry
    return None


def set_theme(week_theme=None, month_theme=None):
    """Set the current content theme for consistency tracking."""
    ledger = load_ledger()
    if week_theme:
        ledger["themes"]["current_week"] = week_theme
    if month_theme:
        ledger["themes"]["current_month"] = month_theme
    ledger["themes"]["history"].append({
        "set_at": datetime.now(ET).isoformat(),
        "week": week_theme,
        "month": month_theme,
    })
    save_ledger(ledger)


def format_schedule_view():
    """Format a human-readable view of the content schedule."""
    upcoming = get_upcoming_posts()
    recent = get_recent_posts(days=7)
    ledger = load_ledger()
    themes = ledger.get("themes", {})

    lines = []
    lines.append("=" * 60)
    lines.append("  CONTENT SCHEDULE DASHBOARD")
    lines.append("=" * 60)

    # Theme
    if themes.get("current_week") or themes.get("current_month"):
        lines.append("")
        if themes.get("current_month"):
            lines.append(f"  Month Theme: {themes['current_month']}")
        if themes.get("current_week"):
            lines.append(f"  Week Theme:  {themes['current_week']}")

    # Upcoming
    lines.append("")
    lines.append("  UPCOMING SCHEDULED:")
    if upcoming:
        for post in upcoming:
            dt = datetime.fromisoformat(post["scheduled_time"])
            lines.append(f"    {dt.strftime('%a %b %d %I:%M %p ET')} | {post.get('title', 'Untitled')}")
            lines.append(f"      {post.get('text_preview', '')[:80]}")
            lines.append(f"      Platform: {post.get('platform', 'linkedin')} | Media: {'Yes' if post.get('media_path') else 'No'}")
            lines.append("")
    else:
        lines.append("    (none scheduled)")

    # Next optimal slot
    next_slot = get_next_optimal_slot()
    if next_slot:
        dt = datetime.fromisoformat(next_slot)
        lines.append(f"  NEXT OPTIMAL SLOT: {dt.strftime('%A %b %d, %I:%M %p ET')}")
    lines.append("")

    # Recent
    lines.append("  RECENT (Last 7 Days):")
    if recent:
        for post in recent[:5]:
            time_str = post.get("published_time", post.get("scheduled_time", ""))
            title = post.get("title", "Untitled")
            lines.append(f"    {time_str[:10]} | {title}")
    else:
        lines.append("    (none)")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_schedule_view())
