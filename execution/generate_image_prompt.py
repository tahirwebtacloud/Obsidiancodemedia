import os
import json
import argparse
import sys
import io
import time
import random
from typing import Dict, Any

from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

# Optional cost tracker import if available
try:
    from cost_tracker import CostTracker
except ImportError:
    class CostTracker:
        def add_gemini_cost(self, *args, **kwargs): pass
        def add_image_cost(self, *args, **kwargs): pass

def _configure_utf8_stdio():
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True, write_through=True)
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True, write_through=True)
    except Exception:
        pass

def get_image_prompt_sop():
    return {
        "type": "OBJECT",
        "description": "Output schema for selecting and filling an image prompt template.",
        "properties": {
            "structural_match_analysis": {
                "type": "STRING",
                "description": "Analyze the core structure of the text post (e.g. is it a 3-step list, a comparison, a timeline, a single quote?). Then, map this structure to the 'best_for' descriptions of the available templates to find the exact matching layout."
            },
            "reasoning": {
                "type": "STRING",
                "description": "Explain how the placeholders will be filled to match the post's core message."
            },
            "selected_template_id": {
                "type": "STRING",
                "description": "The exact ID of the template chosen from the provided image prompt library."
            },
            "final_filled_prompt": {
                "type": "STRING",
                "description": "The final image generation prompt. ALL placeholders must be replaced with context-aware text derived from the text post. DO NOT include the word 'hex' or any raw color codes, HTML colors, or UI codes anywhere in this text string. Convert any specific brand colors to purely descriptive color names like 'bright white' or 'dark slate blue'. Text to be rendered should be short and punchy."
            }
        },
        "required": [
            "structural_match_analysis", "reasoning", "selected_template_id", "final_filled_prompt"
        ]
    }

def discover_image_libraries() -> Dict[str, str]:
    """Scans directives/style_types/ and returns a mapping of filename (without extension) to file path."""
    base_dir = "directives/style_types"
    libraries = {}
    if not os.path.exists(base_dir):
        return libraries

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".json"):
                name = os.path.splitext(file)[0]
                libraries[name] = os.path.join(root, file)
    return libraries

def handle_library_tool_call(fn_name: str, fn_args: dict, libraries: Dict[str, str]) -> str:
    """Handles the tool call from the LLM to fetch a specific template library."""
    if fn_name != "get_image_prompt_library":
        return f"Error: Unknown tool {fn_name}"

    filename = fn_args.get("filename", "")
    if filename not in libraries:
        return f"Error: Library '{filename}' not found. Available: {list(libraries.keys())}"

    filepath = libraries[filename]
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = f.read()
        print(f">>> [Tool Call] Successfully loaded library: {filename}")
        return data
    except Exception as e:
        return f"Error reading library {filename}: {str(e)}"

_RETRYABLE_KEYWORDS = ["503", "unavailable", "429", "rate", "overloaded", "capacity", "quota", "try again"]


def _is_retryable_image_error(error: str) -> bool:
    """Check if an image generation error is transient and worth retrying."""
    if not error:
        return False
    lower = error.lower()
    return any(kw in lower for kw in _RETRYABLE_KEYWORDS)


def _try_generate_image(client, model_name: str, final_prompt: str, max_retries: int = 4):
    """Attempt image generation with exponential backoff + jitter.

    gemini-3-pro-image-preview is a pre-GA model with limited server capacity.
    503 errors are server-side (not quota) and need 15-60s+ to resolve.
    Short retries (3-5s) are ineffective — the server needs real time to free capacity.
    """
    # Exponential backoff: 15s → 30s → 60s → 90s  (+ random jitter 0-5s)
    base_delays = [15, 30, 60, 90]
    last_error = None

    for attempt in range(max_retries):
        print(f">>> Calling {model_name} (attempt {attempt + 1}/{max_retries})...", flush=True)
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=final_prompt,
                config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
            )

            image_bytes = None
            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data:
                                image_bytes = part.inline_data.data
                                break

            if image_bytes:
                return image_bytes, None
            else:
                last_error = "No image data returned from model."
        except Exception as e:
            last_error = str(e)

        if _is_retryable_image_error(last_error) and attempt < max_retries - 1:
            jitter = random.uniform(0, 5)
            delay = base_delays[min(attempt, len(base_delays) - 1)] + jitter
            print(f">>> Server capacity error on {model_name}: {last_error[:120]}", flush=True)
            print(f">>> Waiting {delay:.0f}s before retry (attempt {attempt + 2}/{max_retries})...", flush=True)
            time.sleep(delay)
        else:
            break

    return None, last_error


# Fallback image models — only used after primary model exhausts all retries.
# gemini-3-pro-image-preview is preferred for quality; fallbacks trade quality for availability.
_IMAGE_MODEL_FALLBACKS = [
    "gemini-2.0-flash-exp",
]


def generate_image_asset(prompt: str, aspect_ratio: str = "16:9"):
    """Generates an image using the configured model with robust retry + fallback.

    Strategy:
    1. Try primary model (GEMINI_IMAGE_MODEL) with 4 retries and exponential backoff
    2. If all retries fail with server-capacity errors, try fallback models
    3. Fallback models get fewer retries since they're a last resort
    """
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    primary_model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
    if not api_key:
        return None, "Missing GOOGLE_GEMINI_API_KEY"

    client = genai.Client(api_key=api_key)

    ar_map = {
        "1:1": "Square (1:1)",
        "16:9": "Cinematic Landscape (16:9)",
        "9:16": "Vertical Story (9:16)",
        "4:5": "Portrait (4:5)"
    }
    ar_desc = ar_map.get(aspect_ratio, aspect_ratio)

    # Force-strip any rogue hex codes to prevent text hallucination
    import re
    safe_prompt = re.sub(r'#[0-9a-fA-F]{3,8}\b', '', prompt)
    safe_prompt = re.sub(r'\b[0-9a-fA-F]{6}\b', '', safe_prompt)
    safe_prompt = re.sub(r'(?i)\bhex code\b', 'color', safe_prompt)
    safe_prompt = re.sub(r'(?i)\bhex\b', 'color', safe_prompt)

    final_prompt = f"Aspect Ratio: {ar_desc}. {safe_prompt}"

    # --- Primary model: full retries with exponential backoff ---
    print(f">>> Image generation: trying primary model {primary_model} (aspect_ratio={aspect_ratio})", flush=True)
    image_bytes, error = _try_generate_image(client, primary_model, final_prompt, max_retries=4)

    if image_bytes:
        tracker = CostTracker()
        tracker.add_image_cost("Generate Image", model=primary_model)
        os.makedirs(".tmp", exist_ok=True)
        timestamp = int(time.time() * 1000)
        output_filename = f"generated_image_{timestamp}.png"
        with open(f".tmp/{output_filename}", "wb") as f:
            f.write(image_bytes)
        print(f">>> Image generated successfully with {primary_model}", flush=True)
        return f"/assets/{output_filename}", None

    # --- Fallback models: only if primary failed with capacity errors ---
    if not _is_retryable_image_error(error):
        return None, error or "Image generation failed."

    for fallback_model in _IMAGE_MODEL_FALLBACKS:
        if fallback_model == primary_model:
            continue
        print(f">>> Primary model exhausted retries — trying fallback: {fallback_model}", flush=True)
        image_bytes, error = _try_generate_image(client, fallback_model, final_prompt, max_retries=2)

        if image_bytes:
            tracker = CostTracker()
            tracker.add_image_cost("Generate Image", model=fallback_model)
            os.makedirs(".tmp", exist_ok=True)
            timestamp = int(time.time() * 1000)
            output_filename = f"generated_image_{timestamp}.png"
            with open(f".tmp/{output_filename}", "wb") as f:
                f.write(image_bytes)
            print(f">>> Image generated successfully with fallback {fallback_model}", flush=True)
            return f"/assets/{output_filename}", None

        if not _is_retryable_image_error(error):
            break

    return None, error or "Image generation failed after all models."

def generate_image_prompt_and_asset(text_plan_path, style, topic, aspect_ratio, color_palette, user_id, style_type=None, brand_palette_file=None):
    """Orchestrates the image prompt generation and image rendering."""
    print(f"\n>>>STAGE:image_start", flush=True)

    def _write_image_error(plan_path, plan_data, error_msg):
        """Write image generation error to final_plan.json so frontend can display it."""
        if plan_data is not None:
            plan_data["image_error"] = error_msg
            try:
                with open(plan_path, "w", encoding="utf-8") as ef:
                    json.dump(plan_data, ef, indent=4)
            except Exception:
                pass
        print(f">>>STAGE:image_done", flush=True)

    # 1. Read the text post
    if not os.path.exists(text_plan_path):
        print(f"Error: Text plan not found at {text_plan_path}")
        _write_image_error(text_plan_path, {}, f"Text plan not found at {text_plan_path}")
        return

    with open(text_plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    caption = plan.get("caption", "")
    if not caption:
        print("Error: No caption found to base the image prompt on.")
        _write_image_error(text_plan_path, plan, "No caption found to base the image prompt on.")
        return


    # 2. Setup libraries and tools
    libraries = discover_image_libraries()
    library_names = list(libraries.keys())
    
    # Check if we should bypass tool calling due to a direct style_type match
    direct_library_content = None
    if style_type and style_type in libraries:
        print(f">>> [Direct Bypass] Loading requested style_type library directly: {style_type}")
        try:
            with open(libraries[style_type], "r", encoding="utf-8") as lf:
                direct_library_content = lf.read()
        except Exception as e:
            print(f"Failed to load {style_type}: {e}")

    tool_declaration = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_image_prompt_library",
                description="Fetch the JSON array of templates for a specific image style.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "filename": {"type": "STRING", "enum": library_names, "description": "The name of the library to load"}
                    },
                    "required": ["filename"],
                },
            )
        ]
    )

    # Resolve color palette
    palette_data = "No explicit color palette details provided. Use general color knowledge."

    if brand_palette_file and os.path.exists(brand_palette_file):
        try:
            with open(brand_palette_file, "r", encoding="utf-8") as f:
                palette_data = f.read()
            print(f">>> [Color] Loaded custom brand palette from file")
        except Exception as e:
            print(f">>> [Color] Failed to load brand palette file: {e}")
    else:
        try:
            with open("directives/color_palettes.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                all_palettes = data.get("palettes", [])

            found = False
            for p in all_palettes:
                if p.get("id") == color_palette:
                    palette_data = json.dumps(p, indent=2)
                    print(f">>> [Color] Loaded standard palette: {color_palette}")
                    found = True
                    break

            if not found:
                print(f">>> [Color] Palette '{color_palette}' not found in color_palettes.json")
        except Exception as e:
            print(f">>> [Color] Failed to load standard palettes: {e}")

    # Strip hex codes from palette_data so the LLM doesn't even see them to hallucinate them
    import re
    # Remove # followed by 3-8 hex characters
    palette_data = re.sub(r'#[0-9a-fA-F]{3,8}\b', '[Color Hidden]', palette_data)
    # Remove purely 6-character hex strings that don't have a hash
    palette_data = re.sub(r'\b[0-9a-fA-F]{6}\b', '[Color Hidden]', palette_data)

    # 3. Build System Prompt
    if direct_library_content:
        system_prompt = f"""You are an expert LinkedIn Visual Strategist.
Here is a LinkedIn post that was just generated. You need to create an **image prompt** for it.

POST CAPTION:
---------------------
{caption}
---------------------

Your tasks:
1. The user has specifically requested the '{style_type}' style templates.
2. Here are the templates you MUST choose from:
{direct_library_content}
3. Select the BEST layout for this specific post. Read the "best_for" field of each template and carefully match it against the core structure and topic of the post. Does the post have 3 steps? Choose a 3-step layout. Does it compare two things? Choose a comparison layout.
4. Replace ALL placeholders (like {{{{TEXT_PLACEHOLDER_1}}}}) with actual, punchy text derived from the post caption. Keep text short and readable.
5. EXTREMELY IMPORTANT COLOR RULE: The image generation model will literally render color codes or hex strings as text floating on the image if you include them anywhere in the final prompt. NEVER include the word 'hex' or any exact color codes in your output. Instead, translate the palette into purely descriptive visual instructions (e.g., 'A vibrant blue background with warm orange accents').
{palette_data}

Output your final decision using the enforced JSON schema.
"""
    else:
        system_prompt = f"""You are an expert LinkedIn Visual Strategist.
Here is a LinkedIn post that was just generated. You need to create an **image prompt** for it.

POST CAPTION:
---------------------
{caption}
---------------------

Your tasks:
1. Review the available image style libraries: {library_names}
2. The user requested the general style: "{style}". If there is a matching library, you MUST call `get_image_prompt_library` with that filename to fetch the JSON array of templates.
3. Once you receive the templates, select the BEST layout for this specific post. Read the "best_for" field of each template and carefully match it against the core structure and topic of the post. Does the post have 3 steps? Choose a 3-step layout. Does it compare two things? Choose a comparison layout.
4. Replace ALL placeholders (like {{{{TEXT_PLACEHOLDER_1}}}}) with actual, punchy text derived from the post caption. Keep text short and readable.
5. EXTREMELY IMPORTANT COLOR RULE: The image generation model will literally render color codes or hex strings as text floating on the image if you include them anywhere in the final prompt. NEVER include the word 'hex' or any exact color codes in your output. Instead, translate the palette into purely descriptive visual instructions (e.g., 'A vibrant blue background with warm orange accents').
{palette_data}

Output your final decision using the enforced JSON schema.
"""

    # 4. Call Text LLM (Gemini 3.1 Pro Preview)
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")
    client = genai.Client(api_key=api_key)

    print(">>> Generating Image Prompt (LLM Analysis + Tool Calling)...")
    chat = client.chats.create(
        model=model_name,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.4,
            response_mime_type="application/json",
            response_schema=get_image_prompt_sop(),
            tools=[tool_declaration] if not direct_library_content else None
        )
    )

    try:
        response = chat.send_message("Please analyze the post, fetch the appropriate library, and generate the image prompt.")

        # Tool calling loop
        for _ in range(5):
            candidate = response.candidates[0]

            # Robustly extract function calls (new SDK vs old SDK structure)
            function_calls = getattr(candidate, "function_calls", [])
            if not function_calls and hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                function_calls = [p.function_call for p in candidate.content.parts if getattr(p, "function_call", None)]

            if not function_calls:
                break

            fn_parts = []
            for call in function_calls:
                fn_name = getattr(call, "name", "")
                fn_args = dict(call.args) if getattr(call, "args", None) else {}
                result_str = handle_library_tool_call(fn_name, fn_args, libraries)
                fn_parts.append(types.Part.from_function_response(name=fn_name, response={"content": result_str}))

            response = chat.send_message(fn_parts)

        # Parse output
        final_text = "".join([p.text for p in response.candidates[0].content.parts if hasattr(p, "text") and p.text])
        prompt_data = json.loads(final_text)

        final_prompt = prompt_data.get("final_filled_prompt", "")
        print(f">>> Image Prompt Generated (Template: {prompt_data.get('selected_template_id')})")
        print(f">>> Reasoning: {prompt_data.get('reasoning')}")

    except Exception as e:
        err_msg = f"Image prompt generation failed: {e}"
        print(f"Error: {err_msg}")
        _write_image_error(text_plan_path, plan, err_msg)
        return

    # Skip internal image_done

    # 5. Generate actual image
    # Skip internal image_start
    image_url, error_msg = generate_image_asset(final_prompt, aspect_ratio)

    print(">>>STAGE:image_done", flush=True)
    if image_url:
        plan["asset_url"] = image_url
        plan["final_image_prompt"] = final_prompt
        plan.pop("image_error", None)  # Clear any previous error
        # Save back to file
        with open(text_plan_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=4)
        print(f">>> Image saved and appended to {text_plan_path}")
    else:
        err_msg = f"Image model returned no image: {error_msg}"
        print(f"Error: {err_msg}")
        _write_image_error(text_plan_path, plan, err_msg)

    # Skip internal image_done

if __name__ == "__main__":
    _configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--text_plan_path", default=".tmp/final_plan.json")
    parser.add_argument("--style", default="minimal")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--aspect_ratio", default="16:9")
    parser.add_argument("--color_palette", default="brand")
    parser.add_argument("--user_id", default="default")
    parser.add_argument("--style_type", default=None)
    parser.add_argument("--brand_palette_file", default=None)
    args = parser.parse_args()

    generate_image_prompt_and_asset(
        args.text_plan_path, args.style, args.topic, args.aspect_ratio, args.color_palette, args.user_id, args.style_type, args.brand_palette_file
    )