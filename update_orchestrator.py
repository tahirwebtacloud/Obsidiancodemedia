import re

with open("orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add parser argument
content = re.sub(
    r'parser\.add_argument\("--time_range".*?\)',
    r'parser.add_argument("--time_range", default="day", choices=["day", "week", "month", "year"], help="Time range for web research results (default: day).")\n    parser.add_argument("--include_lead_magnet", action="store_true", help="Pass through toggle to allow LLM to search web for lead magnets.")',
    content
)

# 2. Add include_lead_magnet flag to run_pipeline parameters
content = re.sub(
    r'def run_pipeline\(topic, post_type, purpose, source_content=None, visual_aspect="none", visual_context_path=None, custom_topic=None, user_id="default", deep_research=False, raw_notes=None\):',
    r'def run_pipeline(topic, post_type, purpose, source_content=None, visual_aspect="none", visual_context_path=None, custom_topic=None, user_id="default", deep_research=False, raw_notes=None, include_lead_magnet=False):',
    content
)

# 3. Add include_lead_magnet pass-through for generate_text_post
content = re.sub(
    r'generate_text_post\(post_type, purpose, topic, "topic", "minimal", source_content, visual_aspect, visual_context_path, custom_topic, user_id, raw_notes\)',
    r'generate_text_post(post_type, purpose, topic, "topic", "minimal", source_content, visual_aspect, visual_context_path, custom_topic, user_id, raw_notes, include_lead_magnet)',
    content
)

# 4. Add include_lead_magnet pass-through for generate_carousel
content = re.sub(
    r'generate_carousel\(topic, purpose, user_id\)',
    r'generate_carousel(topic, purpose, user_id, include_lead_magnet)',
    content
)

# 5. Add include_lead_magnet to the run_pipeline call in main
content = re.sub(
    r'raw_notes=_raw_notes_text\n\s*\)',
    r'raw_notes=_raw_notes_text,\n            include_lead_magnet=args.include_lead_magnet\n        )',
    content
)

with open("orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Done updating orchestrator.py")
