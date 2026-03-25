import os
import json
import argparse
import sys
import io
from dotenv import load_dotenv

# Force UTF-8 for stdout/stderr
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True, write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True, write_through=True)

load_dotenv()

from google import genai
from google.genai import types
from cost_tracker import CostTracker

def call_llm(system_prompt, user_content):
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
            ),
            contents=user_content
        )
        
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tracker = CostTracker()
            tracker.add_gemini_cost("Caption Regeneration", response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count, model=model_name)
            
        return response.text.strip()
    except Exception as e:
        return f"Error: {str(e)}"

def _load_user_context_for_regen(user_id: str, topic: str) -> str:
    """Load per-user persona/brand context from Supabase for prompt injection."""
    safe_uid = (user_id or "default").strip() or "default"
    if safe_uid == "default":
        return ""
    try:
        from generate_text_post import _load_user_generation_context, _build_user_context_sections
        ctx = _load_user_generation_context(safe_uid, topic=topic)
        sections = _build_user_context_sections(ctx, "brand")
        return sections.get("system", "")
    except Exception as e:
        print(f">>> Warning: Could not load user context for regeneration: {e}", file=sys.stderr)
        return ""


def regenerate_caption(topic="Modern AI", purpose="storytelling", post_type="image", style="minimal", instructions=None, user_id="default"):
    # Load per-user persona/brand context
    user_context_block = _load_user_context_for_regen(user_id, topic)

    # Load analysis if available
    input_path = ".tmp/analysis.json"
    if os.path.exists(input_path):
        with open(input_path, "r") as f:
            analysis = json.load(f)
    else:
        analysis = {"common_patterns": "General insights"}

    # Load Directive
    directive_path = f"directives/{purpose}_caption.md"
    if os.path.exists(directive_path):
        with open(directive_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    else:
        system_prompt = "You are an expert LinkedIn copywriter."

    # Prepend dynamic user persona/brand context
    if user_context_block:
        system_prompt = user_context_block + "\n\n---\n\n" + system_prompt

    # Load Current Caption from Analysis if not passed (or from final_plan)
    current_caption = ""
    plan_path = ".tmp/final_plan.json"
    if os.path.exists(plan_path):
        try:
            with open(plan_path, "r") as f:
                plan = json.load(f)
            current_caption = plan.get("caption", "")
        except:
            pass

    # Load Miro Board Strategy
    strategy_context = ""
    try:
        guidelines_path = "LinkedIn guidelines/ULTIMATE TOP PERFORMING LINKEDIN POST GUIDELINES.txt"
        if os.path.exists(guidelines_path):
            with open(guidelines_path, "r", encoding="utf-8") as f:
                content = f.read()
                start_marker = "SECTION 1: THE 4-STEP LINKEDIN CONTENT PLAYBOOK"
                end_marker = "SECTION 2:"
                if start_marker in content:
                    start_idx = content.find(start_marker)
                    end_idx = content.find(end_marker)
                    if end_idx == -1: end_idx = len(content)
                    strategy_context = content[start_idx:end_idx]
    except:
        pass

    # Prepare Prompt
    user_content = f"Topic: {topic}\n"
    user_content += f"Post Type: {post_type}\n"
    user_content += f"Visual Style: {style}\n"
    
    if strategy_context:
        user_content += f"\nSTRATEGY CONTEXT:\n{strategy_context}\n"

    if current_caption:
        user_content += f"\nCURRENT CAPTION:\n{current_caption}\n"
        
    if instructions:
        user_content += f"\nIMPORTANT REFINEMENT INSTRUCTIONS: {instructions}\n"
        user_content += "TASK: Rewrite the CURRENT CAPTION to incorporate the instructions. Keep the tone and style consistent unless asked to change. Do NOT output a preamble.\n"
    else:
        user_content += "TASK: Regenerate the caption for this topic.\n"
        
    user_content += f"Analysis Data: {json.dumps(analysis.get('common_patterns', {}))}\n"
    
    # Generate
    caption = call_llm(system_prompt, user_content)

    if not caption:
        caption = "Error: Failed to regenerate caption."

    # Clean
    lines = caption.split('\n')
    cleaned_lines = []
    skip = True
    for line in lines:
        stripped = line.strip()
        if skip and (stripped.startswith("Here") or stripped.startswith("Sure") or stripped.startswith("Certainly")):
            continue
        if skip and stripped == "":
            continue
        skip = False
        cleaned_lines.append(line)
    caption = "\n".join(cleaned_lines).strip()
    
    # Return JSON
    result = {"caption": caption}
    
    # Update final plan if exists to keep sync
    plan_path = ".tmp/final_plan.json"
    if os.path.exists(plan_path):
        try:
            with open(plan_path, "r") as f:
                plan = json.load(f)
            plan["caption"] = caption
            with open(plan_path, "w") as f:
                json.dump(plan, f, indent=4)
        except:
            pass

    print(json.dumps(result)) # Print strictly JSON for server to capture

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="Modern AI")
    parser.add_argument("--purpose", default="storytelling")
    parser.add_argument("--type", default="image")
    parser.add_argument("--style", default="minimal")
    parser.add_argument("--instructions", default=None, help="Specific instructions for refinement")
    parser.add_argument("--user-id", default="default", help="Authenticated user ID for personalization")
    args = parser.parse_args()
    regenerate_caption(args.topic, args.purpose, args.type, args.style, args.instructions, getattr(args, 'user_id', 'default'))
