import os
import subprocess
import argparse
import sys
from dotenv import load_dotenv
load_dotenv()
import io
import shutil

# Force UTF-8 for stdout/stderr to handle emojis on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True, write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True, write_through=True)

_ORCHESTRATOR_TEMP_FILES = {
    "final_plan.json",
    "analysis.json",
    "viral_trends.json",
    "youtube_research.json",
    "regenerated_image.json",
    "manual_save.json",
    "synthesized_research.md",
    "source_content.md",
    "dm_drafts.json",
}
_ORCHESTRATOR_TEMP_PREFIXES = (
    "source_payload_",
    "visual_context_",
    "brand_palette_",
    "ref_image_",
    "run_costs_",
)


def clear_temp_directory():
    """Clears only orchestrator-specific temp files, preserving per-user data."""
    temp_dir = ".tmp"
    print(f"\n>>> Cleaning orchestrator temps in {temp_dir}...")
    os.makedirs(temp_dir, exist_ok=True)

    for filename in os.listdir(temp_dir):
        # Only delete known orchestrator artifacts
        should_delete = (
            filename in _ORCHESTRATOR_TEMP_FILES
            or filename.startswith(_ORCHESTRATOR_TEMP_PREFIXES)
        )
        if not should_delete:
            continue

        file_path = os.path.join(temp_dir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

def run_step(command):
    # Inject -u to force unbuffered stdout in Python subprocesses
    if command and command[0] == "python" and "-u" not in command:
        command.insert(1, "-u")

    print(f"\n>>> Running: {' '.join(command)}", flush=True)
    # Use Popen to stream output line-by-line for real-time SSE updates
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        bufsize=1
    )
    
    for line in iter(proc.stdout.readline, ''):
        sys.stdout.write(line)
        sys.stdout.flush()
        
    proc.stdout.close()
    return_code = proc.wait()
    
    if return_code != 0:
        print(f"Error in step: {' '.join(command)}")
        # FAIL FAST: Exit the orchestrator immediately on any step failure
        sys.exit(return_code)
        
    return True

def main():
    parser = argparse.ArgumentParser(description="Obsidian LinkedIn System Orchestrator")
    parser.add_argument("--action", required=True, choices=["research_viral", "develop_post", "send_dm"], help="Main action to perform.")
    parser.add_argument("--source", choices=["topic", "news", "competitor", "blog", "youtube", "surveillance"], help="Source for development.")
    parser.add_argument("--url", help="URL for the source (news, blog, youtube, etc).")
    parser.add_argument("--urls", help="Comma-separated profile/post URLs for competitor research.")
    parser.add_argument("--topic", help="Theme/Topic for research or development.")
    parser.add_argument("--custom_topic", help="Optional user-provided topic to override or guide the generation.")
    parser.add_argument("--type", choices=["text", "article", "image", "carousel", "video", "poll"], default="text", help="Post format.")
    parser.add_argument("--purpose", choices=["educational", "storytelling", "authority", "promotional"], default="educational", help="Post goal.")
    parser.add_argument("--style", default="minimal", help="Visual style for assets.")
    parser.add_argument("--visual_aspect", default="none", help="Visual aspect (none, image, video, carousel).")
    parser.add_argument("--style_type", default=None, help="Sub-type for the visual style (e.g. glassmorphic_venn for infographic).")
    parser.add_argument("--name", help="Target name for DM.")
    parser.add_argument("--context", help="Context for DM.")
    parser.add_argument("--preview", action="store_true", help="Generate content but do not save to Baserow.")
    parser.add_argument("--source_content", help="Direct text content to repurpose (bypasses search).")
    parser.add_argument("--aspect_ratio", default="16:9", help="Target aspect ratio for assets.")
    parser.add_argument("--color_palette", default="brand", help="Color palette to use (brand, pastel, neon, monochrome, warm, cool).")
    parser.add_argument("--brand_palette_file", default=None, help="Path to a user-isolated palette JSON payload.")
    parser.add_argument("--visual_context", help="Path to JSON file with visual context (images, carousel slides, video URL).")
    parser.add_argument("--reference_image", default=None, help="Path to a user-provided reference image for style inspiration.")
    parser.add_argument("--user_id", default="default", help="Active user ID for tenant-scoped generation context.")
    parser.add_argument("--deep_research", action="store_true", help="Run the Researcher LLM pipeline step.")
    parser.add_argument("--raw_notes", default=None, help="Path to raw weekly notes file for Journalist Workflow (storytelling).")
    parser.add_argument("--time_range", default="day", choices=["day", "week", "month", "year"], help="Time range for web research results (default: day).")
    parser.add_argument("--include_lead_magnet", action="store_true", help="Pass through toggle to allow LLM to search web for lead magnets.")

    args = parser.parse_args()

    # --- PRE-CLEAR: Read files that server.py wrote BEFORE clearing .tmp ---
    if args.source_content and os.path.exists(args.source_content) and os.path.isfile(args.source_content):
        with open(args.source_content, "r", encoding="utf-8") as f:
            args.source_content = f.read()
        print(f">>> [PRE-CLEAR] Read source_content ({len(args.source_content)} chars)")

    _raw_notes_text = None
    if args.raw_notes and os.path.exists(args.raw_notes) and os.path.isfile(args.raw_notes):
        with open(args.raw_notes, "r", encoding="utf-8") as f:
            _raw_notes_text = f.read()
        print(f">>> [PRE-CLEAR] Read raw_notes ({len(_raw_notes_text)} chars)")

    _visual_context_data = None
    if args.visual_context and os.path.exists(args.visual_context):
        with open(args.visual_context, "r", encoding="utf-8") as f:
            _visual_context_data = f.read()
        print(f">>> [PRE-CLEAR] Read visual_context JSON")

    _reference_image_bytes = None
    _reference_image_ext = None
    if args.reference_image and os.path.exists(args.reference_image):
        with open(args.reference_image, "rb") as f:
            _reference_image_bytes = f.read()
        _reference_image_ext = os.path.splitext(args.reference_image)[1]
        print(f">>> [PRE-CLEAR] Read reference_image ({len(_reference_image_bytes)} bytes)")

    _brand_palette_data = None
    if args.brand_palette_file and os.path.exists(args.brand_palette_file):
        with open(args.brand_palette_file, "r", encoding="utf-8") as f:
            _brand_palette_data = f.read()
        print(">>> [PRE-CLEAR] Read brand_palette_file JSON")
    
    # --- PORTABILITY & RELIABILITY: Clear intermediate data ---
    clear_temp_directory()
    # -----------------------------------------------------------

    # --- POST-CLEAR: Re-write preserved files back to .tmp ---
    if _visual_context_data:
        os.makedirs(".tmp", exist_ok=True)
        args.visual_context = ".tmp/_visual_context_preserved.json"
        with open(args.visual_context, "w", encoding="utf-8") as f:
            f.write(_visual_context_data)

    if _reference_image_bytes:
        os.makedirs(".tmp", exist_ok=True)
        args.reference_image = f".tmp/_reference_image_preserved{_reference_image_ext}"
        with open(args.reference_image, "wb") as f:
            f.write(_reference_image_bytes)

    if _brand_palette_data:
        os.makedirs(".tmp", exist_ok=True)
        args.brand_palette_file = ".tmp/_brand_palette_preserved.json"
        with open(args.brand_palette_file, "w", encoding="utf-8") as f:
            f.write(_brand_palette_data)

    if _raw_notes_text:
        os.makedirs(".tmp", exist_ok=True)
        args.raw_notes = ".tmp/_raw_notes_preserved.txt"
        with open(args.raw_notes, "w", encoding="utf-8") as f:
            f.write(_raw_notes_text)

    print(f"--- Obsidian LinkedIn System: {args.action.upper()} ---")
    
    if args.action == "research_viral":
        print(f"--- Action: {args.action} ---")
        
        print(">>>STAGE:research_start", flush=True)
        if args.urls:
            print(f">>> Running Targeted Competitor Research for URLs: {args.urls}")
            run_step(["python", "execution/viral_research_apify.py", "--urls", args.urls])
        elif args.topic:
            print(f">>> Running Keyword-based Viral Research for: {args.topic}")
            run_step(["python", "execution/viral_research_apify.py", "--topic", args.topic, "--type", args.type])
        print(">>>STAGE:research_done", flush=True)
        
        # Analyze and Rank automatically
        print(">>>STAGE:pattern_start", flush=True)
        run_step(["python", "execution/rank_and_analyze.py", "--topic", args.topic or "Research"])
        print(">>>STAGE:pattern_done", flush=True)
        
        if not args.preview:
            run_step(["python", "execution/baserow_logger.py", "--type", "trends", "--path", ".tmp/viral_trends.json"])

    elif args.action == "develop_post":
        topic = args.topic or "Modern AI"
        
        print(">>>STAGE:research_start", flush=True)
        # 1. Base Generation / Source Ingestion
        if args.source_content:
            # source_content is already read into memory by PRE-CLEAR above.
            # Write it to a temp file so generate_assets.py can read it (avoids WinError 206).
            os.makedirs(".tmp", exist_ok=True)
            _sc_path = ".tmp/_source_content_preserved.txt"
            with open(_sc_path, "w", encoding="utf-8") as f:
                f.write(args.source_content)
            args.source_content = _sc_path
            
            print(">>> [DIRECT] Using provided source content for repurposing...")
        elif args.source == "surveillance":
            # For surveillance, the original text is already in args.source_content (via PRE-CLEAR block).
            print(f">>> [SURVEILLANCE] Processing Top-Performing Post for Repurposing...")
        elif args.source == "topic":
            print(f">>> [JINA] Searching web for authentic context on: {topic}...")
            run_step(["python", "execution/jina_search.py", "--topic", topic, "--time_range", args.time_range])
        elif args.source == "youtube":
             if not args.url:
                print(f"Error: --url is required for source {args.source}")
                sys.exit(1)
             print(f">>> [YOUTUBE] Scrapping and repurposing: {args.url}...")
             run_step(["python", "execution/apify_youtube.py", "--urls", args.url])
        elif args.source in ["news", "blog"]:
            if not args.url:
                print(f"Error: --url is required for source {args.source}")
                sys.exit(1)
            run_step(["python", "execution/ingest_source.py", "--url", args.url, "--type", args.source])


        print(">>>STAGE:research_done", flush=True)
        
        # 2. Analyze — PERFORMANCE: Skip full subprocess when no rich sources exist
        print(">>>STAGE:pattern_start", flush=True)
        if getattr(args, "deep_research", False) and os.path.exists(".tmp/source_content.md"):
            print(f">>> [DEEP RESEARCH] Activating Researcher LLM for topic: {topic}...")
            run_step(["python", "execution/research_synthesizer.py", "--topic", topic, "--source", ".tmp/source_content.md", "--output", ".tmp/synthesized_research.md"])
        _has_rich_sources = os.path.exists(".tmp/viral_trends.json") or os.path.exists(".tmp/youtube_research.json")
        if _has_rich_sources:
            run_step(["python", "execution/rank_and_analyze.py", "--topic", topic])
        else:
            # FAST PATH: Write static analysis directly, skip subprocess overhead (~3-8s saved)
            import json as _json
            os.makedirs(".tmp", exist_ok=True)
            _fast_analysis = {
                "common_patterns": {
                    "hooks": [
                        f"Most people misunderstand {topic}. Here's the truth.",
                        f"I've spent years studying {topic}. One insight changed everything.",
                        f"Stop scrolling. This will change how you think about {topic}."
                    ],
                    "ctas": [
                        "What's your take? Drop it below \u2193",
                        "Share this with someone who needs to hear it.",
                        "Follow for more insights like this."
                    ],
                    "structures": [
                        "Hook > Insight > Evidence > Reframe > CTA",
                        "Contrarian Take > Supporting Data > Personal Experience > Question",
                        "Problem > Common Misconception > Real Solution > Proof"
                    ]
                }
            }
            with open(".tmp/analysis.json", "w") as _af:
                _json.dump(_fast_analysis, _af, indent=4)
            print(">>> FAST PATH: Static analysis written (no viral/competitor data to analyze)")
        print(">>>STAGE:pattern_done", flush=True)
        
        # 3. Generate Assets (Gemini 3.0)
        # Emit text_start immediately here so UI doesn't stall while python initializes the large modules
        print(">>>STAGE:text_start", flush=True)
        
        # CAROUSEL ROUTING: Use dedicated carousel generator for carousel type
        # CHECK: args.type OR args.visual_aspect
        if args.type.lower() == "carousel" or args.visual_aspect.lower() == "carousel":
            print(f">>> Routing to dedicated carousel generator...")
            gen_command = ["python", "execution/generate_carousel.py", "--topic", topic, "--purpose", args.purpose]
            gen_command.extend(["--user_id", args.user_id or "default"])
            if args.include_lead_magnet:
                gen_command.append("--include_lead_magnet")
            if args.visual_context and os.path.exists(args.visual_context):
                gen_command.extend(["--visual_context", args.visual_context])
            run_step(gen_command)
        else:
            # 3a. Generate Text Post
            text_command = ["python", "execution/generate_text_post.py", "--type", args.type, "--purpose", args.purpose, "--topic", topic, "--source", args.source or "manual"]
            text_command.extend(["--user_id", args.user_id or "default"])
            if args.include_lead_magnet:
                text_command.append("--include_lead_magnet")
            if args.source_content:
                text_command.extend(["--source_content", args.source_content])
            if args.raw_notes and os.path.exists(args.raw_notes):
                text_command.extend(["--raw_notes", args.raw_notes])
            if args.custom_topic:
                text_command.extend(["--custom_topic", args.custom_topic])
            run_step(text_command)

            # 3b. Generate Image Prompt & Asset (if visual asset requested)
            if args.visual_aspect in ["image", "carousel"] or args.type in ["image", "article", "poll"]:
                img_command = ["python", "execution/generate_image_prompt.py", "--topic", topic, "--style", args.style, "--aspect_ratio", args.aspect_ratio, "--color_palette", args.color_palette]
                img_command.extend(["--user_id", args.user_id or "default"])
                if args.style_type:
                    img_command.extend(["--style_type", args.style_type])
                if args.brand_palette_file and os.path.exists(args.brand_palette_file):
                    img_command.extend(["--brand_palette_file", args.brand_palette_file])
                run_step(img_command)
        
        # 4. Log Result (Only if not in preview mode)
        if not args.preview:
            run_step(["python", "execution/baserow_logger.py", "--type", "posts", "--path", ".tmp/final_plan.json"])

    elif args.action == "send_dm":
        # ... (DM logic remains same)
        if not args.name or not args.context:
            print("Error: --name and --context are required for send_dm")
            sys.exit(1)
        run_step(["python", "execution/dm_automation.py", "--name", args.name, "--context", args.context])
        run_step(["python", "execution/baserow_logger.py", "--type", "dms", "--path", ".tmp/dm_drafts.json"])

    print("\n--- Process Complete! ---")

if __name__ == "__main__":
    main()

