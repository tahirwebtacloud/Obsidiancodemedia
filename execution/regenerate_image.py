import os
import json
import argparse
import random
import time as _time
from dotenv import load_dotenv
import sys
import io
import re

# Force UTF-8 for stdout/stderr to handle emojis on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True, write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True, write_through=True)

load_dotenv()

from google import genai
from google.genai import types
from cost_tracker import CostTracker

def call_llm(system_prompt, user_content):
    """Calls the Google Gemini API."""
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        return "Error: Missing API Key."

    try:
        client = genai.Client(api_key=api_key)
        model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")
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
            tracker.add_gemini_cost("Text Generation", response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count, model=model_name)
            
        return response.text.strip()
    except Exception as e:
        return f"Error: {str(e)}"

_RETRYABLE_KEYWORDS = ["503", "unavailable", "429", "rate", "overloaded", "capacity", "quota", "try again"]


def _is_retryable_image_error(error: str) -> bool:
    """Check if an image generation error is transient and worth retrying."""
    if not error:
        return False
    return any(kw in error.lower() for kw in _RETRYABLE_KEYWORDS)


def _try_regen_image(client, model_name: str, contents, max_retries: int = 4):
    """Attempt image generation/editing with exponential backoff + jitter.

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
                contents=contents,
                config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
            )

            image_bytes = None
            finish_reason = "Unknown"
            error_text = ""

            if response.candidates:
                finish_reason = response.candidates[0].finish_reason
                for i, candidate in enumerate(response.candidates):
                    print(f">>> Candidate {i} finish reason: {candidate.finish_reason}")
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data:
                                image_bytes = part.inline_data.data
                                break
                            elif hasattr(part, 'text') and part.text:
                                print(f">>> Text content found: {part.text}")
                                error_text += part.text + " "

            if image_bytes:
                return image_bytes, None
            else:
                last_error = f"No image data. Reason: {finish_reason}"
                if error_text:
                    last_error += f" | Details: {error_text.strip()}"

        except Exception as e:
            last_error = str(e)
            print(f"Error generating image: {last_error}")

        if _is_retryable_image_error(last_error) and attempt < max_retries - 1:
            jitter = random.uniform(0, 5)
            delay = base_delays[min(attempt, len(base_delays) - 1)] + jitter
            print(f">>> Server capacity error on {model_name}: {last_error[:120]}", flush=True)
            print(f">>> Waiting {delay:.0f}s before retry (attempt {attempt + 2}/{max_retries})...", flush=True)
            _time.sleep(delay)
        else:
            break

    return None, last_error


# Fallback image models — only used after primary model exhausts all retries.
# gemini-3-pro-image-preview is preferred for quality; fallbacks trade quality for availability.
_REGEN_MODEL_FALLBACKS = [
    "gemini-2.0-flash-exp",
]


def generate_image_asset(prompt, aspect_ratio="16:9", source_image_bytes=None, high_quality=False):
    """Generates or edits an image using the optimal model for each operation.

    Model routing:
    - IMAGE EDITING — High Quality (source_image_bytes + high_quality=True):
      Uses gemini-3-pro-image-preview (Nano Banana Pro) — highest fidelity
      for photorealistic editing. Slower, lower rate limits (10 RPM),
      longer exponential backoff. No fallback to Flash.
    - IMAGE EDITING — Standard (source_image_bytes + high_quality=False):
      Uses gemini-3.1-flash-image-preview (Nano Banana 2) — optimized for
      instruction-based conversational editing with source image preservation.
      Higher rate limits (30 RPM) allow shorter retry delays.
      Falls back to Pro if Flash fails.
    - IMAGE GENERATION (no source image):
      Uses gemini-3-pro-image-preview (Nano Banana Pro) — highest fidelity
      for fresh text-to-image generation. Lower rate limits (10 RPM) need
      longer exponential backoff.
    """
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        return None, "Missing API Key"

    client = genai.Client(api_key=api_key)

    # Force-strip any rogue hex codes to prevent text hallucination
    safe_prompt = re.sub(r'#[0-9a-fA-F]{3,8}\b', '', prompt)
    safe_prompt = re.sub(r'\b[0-9a-fA-F]{6}\b', '', safe_prompt)
    safe_prompt = re.sub(r'(?i)\bhex code\b', 'color', safe_prompt)
    safe_prompt = re.sub(r'(?i)\bhex\b', 'color', safe_prompt)

    # --- IMAGE EDITING: HIGH QUALITY (Pro model — separate pipeline) ---
    if source_image_bytes and high_quality:
        hq_model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
        contents = [
            types.Part.from_bytes(data=source_image_bytes, mime_type="image/png"),
            safe_prompt
        ]
        print(f">>> IMAGE EDITING [HQ]: Using {hq_model} (Pro — highest fidelity editing)")
        print(f">>> Edit prompt: {safe_prompt[:150]}...")

        # Pro has 10 RPM — use longer backoff (4 retries: 15/30/60/90s)
        image_bytes, error = _try_regen_image(client, hq_model, contents, max_retries=4)

        if image_bytes:
            tracker = CostTracker()
            tracker.add_image_cost("Image Edit (Refine HQ)", model=hq_model)
            timestamp = int(_time.time() * 1000)
            output_filename = f"generated_image_{timestamp}.png"
            os.makedirs(".tmp", exist_ok=True)
            with open(f".tmp/{output_filename}", "wb") as f:
                f.write(image_bytes)
            print(f">>> HQ image edited successfully with {hq_model}", flush=True)
            return f"/assets/{output_filename}", None

        return None, error or "High-quality image editing failed."

    # --- IMAGE EDITING: STANDARD (Flash model — fast pipeline) ---
    if source_image_bytes:
        edit_model = "gemini-3.1-flash-image-preview"
        contents = [
            types.Part.from_bytes(data=source_image_bytes, mime_type="image/png"),
            safe_prompt
        ]
        print(f">>> IMAGE EDITING [STD]: Using {edit_model} (Flash — optimized for conversational editing)")
        print(f">>> Edit prompt: {safe_prompt[:150]}...")

        image_bytes, error = _try_regen_image(client, edit_model, contents, max_retries=3)

        if image_bytes:
            tracker = CostTracker()
            tracker.add_image_cost("Image Edit (Refine)", model=edit_model)
            timestamp = int(_time.time() * 1000)
            output_filename = f"generated_image_{timestamp}.png"
            os.makedirs(".tmp", exist_ok=True)
            with open(f".tmp/{output_filename}", "wb") as f:
                f.write(image_bytes)
            print(f">>> Image edited successfully with {edit_model}", flush=True)
            return f"/assets/{output_filename}", None

        # Fallback: try Pro model for editing if Flash fails
        print(f">>> Flash editing failed — trying Pro model as fallback for editing...")
        pro_model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
        image_bytes, error = _try_regen_image(client, pro_model, contents, max_retries=2)

        if image_bytes:
            tracker = CostTracker()
            tracker.add_image_cost("Image Edit (Refine Fallback)", model=pro_model)
            timestamp = int(_time.time() * 1000)
            output_filename = f"generated_image_{timestamp}.png"
            os.makedirs(".tmp", exist_ok=True)
            with open(f".tmp/{output_filename}", "wb") as f:
                f.write(image_bytes)
            print(f">>> Image edited successfully with fallback {pro_model}", flush=True)
            return f"/assets/{output_filename}", None

        return None, error or "Image editing failed after all models."

    # --- IMAGE GENERATION MODE (Tweak pipeline / from-scratch) ---
    else:
        primary_model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")

        ar_map = {
            "1:1": "Square (1:1)",
            "16:9": "Cinematic Landscape (16:9)",
            "9:16": "Vertical Story (9:16)",
            "4:5": "Portrait (4:5)"
        }
        ar_desc = ar_map.get(aspect_ratio, aspect_ratio)
        final_prompt = f"Aspect Ratio: {ar_desc}. {safe_prompt}"
        contents = final_prompt

        print(f">>> IMAGE GENERATION MODE: Using {primary_model} (Pro — highest fidelity)")
        image_bytes, error = _try_regen_image(client, primary_model, contents, max_retries=4)

        if image_bytes:
            tracker = CostTracker()
            tracker.add_image_cost("Regenerate Image", model=primary_model)
            timestamp = int(_time.time() * 1000)
            output_filename = f"generated_image_{timestamp}.png"
            os.makedirs(".tmp", exist_ok=True)
            with open(f".tmp/{output_filename}", "wb") as f:
                f.write(image_bytes)
            print(f">>> Image generated successfully with {primary_model}", flush=True)
            return f"/assets/{output_filename}", None

        # Fallback models for generation
        if not _is_retryable_image_error(error):
            return None, error or "Image generation failed."

        for fallback_model in _REGEN_MODEL_FALLBACKS:
            if fallback_model == primary_model:
                continue
            print(f">>> Primary model exhausted retries — trying fallback: {fallback_model}", flush=True)
            image_bytes, error = _try_regen_image(client, fallback_model, contents, max_retries=2)

            if image_bytes:
                tracker = CostTracker()
                tracker.add_image_cost("Regenerate Image", model=fallback_model)
                timestamp = int(_time.time() * 1000)
                output_filename = f"generated_image_{timestamp}.png"
                os.makedirs(".tmp", exist_ok=True)
                with open(f".tmp/{output_filename}", "wb") as f:
                    f.write(image_bytes)
                print(f">>> Image generated successfully with fallback {fallback_model}", flush=True)
                return f"/assets/{output_filename}", None

            if not _is_retryable_image_error(error):
                break

        return None, error or "Image generation failed after all models."

def regenerate_image(caption, style="minimal", aspect_ratio="16:9", instructions=None):
    """Regenerates image based on existing caption and style."""
    
    # SANITIZE ASPECT RATIO
    if aspect_ratio.lower() in ["image", "video", "carousel", "none", "null", "undefined"]:
        print(f">>> Warning: Invalid aspect ratio '{aspect_ratio}' detected. Defaulting to 16:9.")
        aspect_ratio = "16:9"

    output_path = ".tmp/regenerated_image.json"
    
    # Map display names to directive style names
    style_key_map = {
        "minimal": "Minimal Illustration",
        "infographic": "Infographic / Chart",
        "ugc": "UGC / YT Thumbnail",
        "mockup": "Device Mockup"
    }
    target_style = style_key_map.get(style.lower(), "Minimal Illustration")

    # Load image SOP
    image_sop_path = "directives/image_prompt_design.md"
    if os.path.exists(image_sop_path):
        with open(image_sop_path, "r", encoding="utf-8") as f:
            image_sop = f.read()
        
        # BIND DYNAMIC CONTEXT: Replace placeholders in SOP
        image_sop = image_sop.replace("{ASPECT_RATIO}", aspect_ratio)
        
        image_user_content = f"REQUESTED STYLE: {target_style}\n"
        image_user_content += f"TARGET ASPECT RATIO: {aspect_ratio}\n"
        image_user_content += f"Generate a detailed image prompt for this LinkedIn post:\n\n{caption}\n\n"
        
        if instructions:
            image_user_content += f"USER INSTRUCTIONS: {instructions}\n"
            
        image_user_content += "Final Action: Generate the detailed single paragraph string prompt following the specific style template in your instructions."
        
        print(f">>> Generating detailed {target_style} prompt using custom SOP...")
        image_prompt_text = call_llm(image_sop, image_user_content)
        
        if image_prompt_text.startswith("Error"):
            print(f">>> LLM Error detected. Aborting image generation. Reason: {image_prompt_text}")
            # Early exit but MUST write JSON
            error_result = {"error": f"Prompt Generation Failed: {image_prompt_text}"}
            with open(output_path, "w") as f:
                json.dump(error_result, f, indent=4)
            return None, f"Prompt Generation Failed: {image_prompt_text}"
            
        # Clean the response
        if image_prompt_text.startswith("```"):
            image_prompt_text = image_prompt_text.strip("`").replace("json", "").strip()
    else:
        instructions_text = f" with {instructions}" if instructions else ""
        image_prompt_text = f"Professional {target_style} image{instructions_text}. Wide shot, {aspect_ratio}, Obsidian Black and Signal Yellow theme."
    
    # STRICT CONSTRAINT: Deterministically remove colons to enforce style rule
    image_prompt_text = image_prompt_text.replace(":", " -")

    # FORCE ASPECT RATIO: Append it to ensure the model sees it (Final safety check)
    if aspect_ratio not in image_prompt_text:
        image_prompt_text = f"{image_prompt_text}, {aspect_ratio} aspect ratio"

    # Generate the image
    image_url, error_msg = generate_image_asset(image_prompt_text, aspect_ratio=aspect_ratio)
    
    result = {
        "asset_url": image_url,
        "final_image_prompt": image_prompt_text
    }
    
    if error_msg:
        result["error"] = error_msg
    
    with open(output_path, "w") as f:
        json.dump(result, f, indent=4)
    
    print(f"Result saved to {output_path}")


def regenerate_image_with_context(caption, style, aspect_ratio, instructions, source_image_path, high_quality=False):
    """Refines an existing image using VLM analysis + image editing mode.
    
    Pipeline (separate from Tweak which generates from scratch):
    1. Read source image bytes
    2. VLM analyzes the source image → writes a prompt preserving its exact composition
       while applying ONLY the user's refinement instructions
    3. Image model receives source image bytes + refined prompt → edits in-place
    
    When high_quality=True, routes to Pro model (higher fidelity, slower).
    When high_quality=False (default), routes to Flash model (faster, lower fidelity).
    """
    print(f">>> REFINE pipeline: Context-aware editing. Source: {source_image_path}")
    
    # 1. Read Source Image
    try:
        with open(source_image_path, "rb") as f:
            image_bytes = f.read()
        print(f">>> Source image loaded: {len(image_bytes)} bytes")
    except Exception as e:
        print(f"ERROR: Cannot read source image: {e}")
        output_path = ".tmp/regenerated_image.json"
        result = {"error": f"Cannot read source image: {e}"}
        with open(output_path, "w") as f:
            json.dump(result, f, indent=4)
        return

    # 2. VLM Call — analyze source image and apply user instructions
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    system_prompt = """You are an expert AI image editor. Your job is to write image editing instructions.

RULES:
1. ANALYZE the provided image in extreme detail: composition, layout, colors, typography, shapes, style, aspect ratio, lighting, subject placement.
2. Your output prompt must PRESERVE every aspect of the original image EXCEPT what the user explicitly asks to change.
3. DO NOT change the style, color palette, aspect ratio, or overall composition unless the user specifically requests it.
4. Describe the original image faithfully, then append the user's requested modifications.
5. Output ONLY the final image editing prompt. No conversational text, no explanations."""

    user_instructions = instructions if instructions else "Improve the overall quality while keeping the image identical."
    
    user_content = [
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        f"\nUSER'S EDIT REQUEST: {user_instructions}\n",
        f"CAPTION CONTEXT: {caption}\n" if caption else "",
        "\nTASK: Write a detailed image editing prompt that preserves the original image exactly as-is, applying ONLY the user's requested changes. Start by describing what the image currently looks like, then specify what to change."
    ]

    try:
        vlm_model = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")
        print(f">>> Calling VLM ({vlm_model}) for image analysis + edit prompt...")
        response = client.models.generate_content(
            model=vlm_model,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.5,
            ),
            contents=user_content
        )
        
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tracker = CostTracker()
            tracker.add_gemini_cost("Image Refine VLM", response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count, model=vlm_model)
        
        new_prompt = response.text.strip()
        print(f">>> Refine prompt: {new_prompt[:200]}...")
        
        if new_prompt.startswith("```"):
            new_prompt = new_prompt.strip("`").replace("json", "").replace("text", "").strip()

    except Exception as e:
        print(f"VLM Error: {e}")
        output_path = ".tmp/regenerated_image.json"
        result = {"error": f"VLM analysis failed: {e}"}
        with open(output_path, "w") as f:
            json.dump(result, f, indent=4)
        return

    # 3. Image Editing Mode — pass source image bytes so the model edits in-place
    hq_label = "HQ (Pro)" if high_quality else "STD (Flash)"
    print(f">>> Generating refined image (editing mode [{hq_label}] with source image bytes)...")
    image_url, error_msg = generate_image_asset(new_prompt, aspect_ratio=aspect_ratio, source_image_bytes=image_bytes, high_quality=high_quality)
    
    output_path = ".tmp/regenerated_image.json"
    result = {
        "asset_url": image_url,
        "final_image_prompt": new_prompt
    }
    
    if error_msg:
        result["error"] = error_msg
    
    with open(output_path, "w") as f:
        json.dump(result, f, indent=4)
        
    print(f">>> Refine result saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regenerate image for a caption.")
    parser.add_argument("--caption", required=True, help="The caption context.")
    parser.add_argument("--style", default="minimal", help="Visual style.")
    parser.add_argument("--aspect_ratio", default="16:9", help="Target aspect ratio.")
    parser.add_argument("--instructions", default=None, help="User instructions for refinement.")
    parser.add_argument("--source_image", default=None, help="Path to source image for context.")
    parser.add_argument("--color_palette", default="brand", help="Color palette name.")
    parser.add_argument("--high_quality", action="store_true", help="Use Pro model for higher fidelity editing (slower).")
    
    args = parser.parse_args()
    
    if args.source_image and os.path.exists(args.source_image):
        regenerate_image_with_context(args.caption, args.style, args.aspect_ratio, args.instructions, args.source_image, high_quality=args.high_quality)
    else:
        regenerate_image(args.caption, args.style, args.aspect_ratio, args.instructions)
