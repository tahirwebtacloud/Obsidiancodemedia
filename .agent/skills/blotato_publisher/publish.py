#!/usr/bin/env python3
"""
Blotato Publisher - Review-First Publishing Workflow

The workflow enforces: DRAFT → REVIEW → APPROVE → SCHEDULE → CONFIRM

Commands:
  python3 publish.py preview              Show post + image + quality score before scheduling
  python3 publish.py schedule             Schedule after review (prompts for confirmation)
  python3 publish.py schedule --now       Publish immediately (still runs quality gate)
  python3 publish.py status               Show content schedule dashboard
  python3 publish.py status --detailed    Show full schedule with recent posts
  python3 publish.py accounts             List connected Blotato accounts
  python3 publish.py upload <image>       Upload image and get public URL
  python3 publish.py theme <week> [month] Set content theme for consistency
  python3 publish.py test                 Test API connection
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from SKILLS.blotato_publisher import api_client
from SKILLS.blotato_publisher.quality_gate import score_post, format_scorecard
from SKILLS.blotato_publisher.schedule_ledger import (
    format_schedule_view, check_conflicts, get_next_optimal_slot,
    add_scheduled_post, get_upcoming_posts, set_theme, load_ledger,
)
from SKILLS.blotato_publisher.media_handler import (
    upload_for_publishing, list_available_images, preview_image_info, get_local_image,
)

ET = ZoneInfo("America/New_York")
POST_PATH = PROJECT_ROOT / "strategy" / "Today_Linkedin_Post.md"


def load_post():
    """Load post text from Today_Linkedin_Post.md."""
    if not POST_PATH.exists():
        print(f"ERROR: No post found at {POST_PATH}")
        print("Create your post in strategy/Today_Linkedin_Post.md first.")
        sys.exit(1)

    text = POST_PATH.read_text().strip()

    # Strip markdown frontmatter if present
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2].strip()

    # Strip markdown headers
    lines = []
    for line in text.split("\n"):
        if line.startswith("# ") or line.startswith("## "):
            continue
        lines.append(line)

    return "\n".join(lines).strip()


def cmd_preview(args):
    """Preview post with quality gate scoring."""
    post_text = load_post()
    has_image = args.image is not None

    print("\n" + "=" * 60)
    print("  POST PREVIEW")
    print("=" * 60)
    print()

    # Show post text (first 500 chars)
    preview = post_text[:500] + ("..." if len(post_text) > 500 else "")
    print(preview)
    print()

    # Image info
    if args.image:
        try:
            img_path = get_local_image(args.image)
            info = preview_image_info(img_path)
            print(f"  IMAGE: {info['filename']}")
            print(f"  Size:  {info.get('dimensions', '?')} ({info['size_kb']}KB)")
            print(f"  Square: {'Yes' if info.get('is_square') else 'No'}")
            print()
        except FileNotFoundError as e:
            print(f"  IMAGE: Not found - {e}")
            has_image = False

    # Quality gate
    next_slot = get_next_optimal_slot()
    is_optimal = True  # Assume optimal if using suggested slot

    result = score_post(post_text, has_image=has_image, scheduled_optimal=is_optimal)
    print(format_scorecard(result))

    # Scheduling suggestion
    if next_slot:
        dt = datetime.fromisoformat(next_slot)
        print(f"\n  Suggested schedule: {dt.strftime('%A %b %d, %I:%M %p ET')}")

    # Conflict check
    if next_slot:
        conflict = check_conflicts(next_slot)
        if not conflict["clear"]:
            print(f"  WARNING: {conflict['reason']}")

    if not result["passed"]:
        print("\n  POST BLOCKED by quality gate. Fix feedback items before scheduling.")
    else:
        print("\n  POST APPROVED. Ready to schedule with: python3 publish.py schedule")

    return result


def cmd_schedule(args):
    """Schedule post after review and confirmation."""
    post_text = load_post()

    # Run quality gate first
    has_image = args.image is not None
    is_optimal = not args.now  # If --now, timing isn't optimal

    result = score_post(post_text, has_image=has_image, scheduled_optimal=is_optimal)

    if not result["passed"] and not args.force:
        print(format_scorecard(result))
        print("\nPost blocked by quality gate. Use --force to override.")
        sys.exit(1)

    # Determine schedule time
    if args.now:
        scheduled_time = None
        time_display = "IMMEDIATELY"
    elif args.time:
        scheduled_time = args.time
        time_display = args.time
    else:
        scheduled_time = get_next_optimal_slot()
        if scheduled_time:
            dt = datetime.fromisoformat(scheduled_time)
            time_display = dt.strftime("%A %b %d, %I:%M %p ET")
        else:
            print("ERROR: Could not find an available slot. Use --time to specify manually.")
            sys.exit(1)

    # Check conflicts
    if scheduled_time:
        conflict = check_conflicts(scheduled_time)
        if not conflict["clear"]:
            print(f"CONFLICT: {conflict['reason']}")
            if not args.force:
                print("Use --force to override.")
                sys.exit(1)

    # Upload image if provided
    media_urls = []
    media_path = None
    if args.image:
        try:
            img_path = get_local_image(args.image)
            media_path = str(img_path)
            method = args.upload_method or "blotato"
            public_url = upload_for_publishing(img_path, method=method)
            media_urls.append(public_url)
            print(f"  Image uploaded: {public_url}")
        except Exception as e:
            print(f"  Image upload failed: {e}")
            if not args.force:
                print("  Proceeding without image. Use --force to skip.")
                sys.exit(1)

    # Confirmation prompt
    print("\n" + "=" * 60)
    print("  CONFIRM PUBLISH")
    print("=" * 60)
    print(f"  Platform:  LinkedIn (personal profile)")
    print(f"  Schedule:  {time_display}")
    print(f"  Characters: {len(post_text)}")
    print(f"  Image:     {'Yes - ' + (args.image or '') if media_urls else 'No'}")
    print(f"  Quality:   {result['total']}/35")
    print("=" * 60)

    if not args.yes:
        confirm = input("\n  Type 'yes' to confirm: ").strip().lower()
        if confirm != "yes":
            print("  Cancelled.")
            sys.exit(0)

    # Get LinkedIn account
    print("\n  Connecting to Blotato...")
    li_account = api_client.get_linkedin_account()
    account_id = li_account["account_id"]
    print(f"  Account: {li_account['fullname']} (ID: {account_id})")

    # Publish/schedule
    print("  Submitting post...")
    response = api_client.publish_post(
        account_id=account_id,
        text=post_text,
        platform="linkedin",
        media_urls=media_urls if media_urls else None,
        scheduled_time=scheduled_time,
    )

    submission_id = response.get("postSubmissionId", response.get("id", ""))
    print(f"  Submission ID: {submission_id}")

    # Poll for status
    print("  Waiting for confirmation...")
    status_result = api_client.wait_for_post(submission_id, timeout=60)
    status = status_result.get("status", "unknown")

    if status in ("published", "scheduled"):
        public_url = status_result.get("publicUrl", "")
        print(f"\n  SUCCESS: Post {status}!")
        if public_url:
            print(f"  URL: {public_url}")

        # Update ledger
        title = post_text.split("\n")[0][:60]
        add_scheduled_post(
            title=title,
            text=post_text,
            scheduled_time=scheduled_time or datetime.now(ET).isoformat(),
            media_path=media_path,
            platform="linkedin",
            blotato_id=submission_id,
        )
        print("  Ledger updated.")

    elif status == "failed":
        error = status_result.get("errorMessage", "Unknown error")
        print(f"\n  FAILED: {error}")
        sys.exit(1)
    else:
        print(f"\n  Status: {status} — check Blotato dashboard for updates")
        print(f"  https://my.blotato.com/api-dashboard")


def cmd_status(args):
    """Show content schedule dashboard."""
    print(format_schedule_view())

    if args.detailed:
        ledger = load_ledger()
        upcoming = get_upcoming_posts()
        if upcoming:
            print("\n  FULL POST PREVIEWS:")
            for post in upcoming:
                print(f"\n  --- {post.get('title', 'Untitled')} ---")
                print(f"  {post.get('text_preview', '')}")
                print(f"  Scheduled: {post.get('scheduled_time', '')}")
                print(f"  Media: {post.get('media_path', 'None')}")


def cmd_accounts(args):
    """List connected Blotato accounts."""
    print("\nConnected accounts:")
    accounts = api_client.get_accounts()
    for acc in (accounts if isinstance(accounts, list) else [accounts]):
        print(f"  {acc.get('platform', '?')}: {acc.get('fullname', 'Unknown')} (ID: {acc.get('id')})")

    print("\nLinkedIn details:")
    try:
        li = api_client.get_linkedin_account()
        print(f"  Profile: {li['fullname']} (ID: {li['account_id']})")
        if li["pages"]:
            print("  Company Pages:")
            for page in li["pages"]:
                print(f"    - {page['name']} (ID: {page['id']})")
        else:
            print("  No company pages — posts go to personal profile")
    except Exception as e:
        print(f"  Error: {e}")


def cmd_upload(args):
    """Upload an image and return the public URL."""
    method = args.method or "blotato"
    url = upload_for_publishing(args.image, method=method)
    print(f"\nPublic URL: {url}")
    print("Use this URL in mediaUrls when publishing.")


def cmd_theme(args):
    """Set content theme for the week/month."""
    set_theme(week_theme=args.week, month_theme=args.month)
    print(f"Theme set:")
    if args.week:
        print(f"  Week: {args.week}")
    if args.month:
        print(f"  Month: {args.month}")


def cmd_test(args):
    """Test API connection."""
    print("Testing Blotato API connection...")
    try:
        accounts = api_client.get_accounts()
        count = len(accounts) if isinstance(accounts, list) else 1
        print(f"  Connected! {count} account(s) found.")

        li = api_client.get_linkedin_account()
        print(f"  LinkedIn: {li['fullname']} (ID: {li['account_id']})")
        print("\n  Ready to publish!")
    except Exception as e:
        print(f"  Connection failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Blotato Publisher - Review-First LinkedIn Publishing")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Preview
    p_preview = subparsers.add_parser("preview", help="Preview post with quality scoring")
    p_preview.add_argument("--image", "-i", help="Image filename from media/")

    # Schedule
    p_sched = subparsers.add_parser("schedule", help="Schedule post after review")
    p_sched.add_argument("--image", "-i", help="Image filename from media/")
    p_sched.add_argument("--time", "-t", help="ISO 8601 schedule time")
    p_sched.add_argument("--now", action="store_true", help="Publish immediately")
    p_sched.add_argument("--force", "-f", action="store_true", help="Override quality gate")
    p_sched.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    p_sched.add_argument("--upload-method", choices=["blotato", "imgbb", "url"], default="blotato")

    # Status
    p_status = subparsers.add_parser("status", help="View content schedule")
    p_status.add_argument("--detailed", "-d", action="store_true", help="Show full post previews")

    # Accounts
    subparsers.add_parser("accounts", help="List connected accounts")

    # Upload
    p_upload = subparsers.add_parser("upload", help="Upload image for publishing")
    p_upload.add_argument("image", help="Image path or filename from media/")
    p_upload.add_argument("--method", "-m", choices=["blotato", "imgbb"], default="blotato")

    # Theme
    p_theme = subparsers.add_parser("theme", help="Set content theme")
    p_theme.add_argument("week", help="This week's content theme")
    p_theme.add_argument("month", nargs="?", help="This month's content theme")

    # Test
    subparsers.add_parser("test", help="Test API connection")

    args = parser.parse_args()

    commands = {
        "preview": cmd_preview,
        "schedule": cmd_schedule,
        "status": cmd_status,
        "accounts": cmd_accounts,
        "upload": cmd_upload,
        "theme": cmd_theme,
        "test": cmd_test,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
