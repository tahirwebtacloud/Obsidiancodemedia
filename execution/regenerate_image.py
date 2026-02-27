import os
import json
import argparse
from dotenv import load_dotenv
import sys
import io
import re

# Force UTF-8 for stdout/stderr to handle emojis on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

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
        model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3-pro-preview")
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

def generate_image_asset(prompt, aspect_ratio="16:9", source_image_bytes=None):
    """Generates or edits an image using Nano Banana Pro (gemini-3-pro-image-preview)."""
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        return None, "Missing API Key"

    try:
        client = genai.Client(api_key=api_key)
        model_name = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")

        # Ensure aspect ratio is in the prompt
        # Map to descriptive terms for better adherence
        ar_map = {
            "1:1": "Square (1:1)",
            "16:9": "Cinematic Landscape (16:9)",
            "9:16": "Vertical Story (9:16)",
            "4:5": "Portrait (4:5)"
        }
        
        ar_desc = ar_map.get(aspect_ratio, aspect_ratio)
        
        final_prompt = prompt
        if aspect_ratio:
            # Prepend for higher attention
            final_prompt = f"Aspect Ratio: {ar_desc}. {final_prompt}"

        print(f">>> Generating image for prompt: {final_prompt[:50]}...")
        
        # Construct contents. If source_image_bytes is present, it's an editing task.
        if source_image_bytes:
            print(">>> Image Editing Mode: Including source image in request.")
            contents = [
                types.Part.from_bytes(data=source_image_bytes, mime_type="image/png"),
                final_prompt
            ]
        else:
            contents = final_prompt

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]
            )
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
                        # Check for inline_data
                        if hasattr(part, 'inline_data') and part.inline_data:
                            image_bytes = part.inline_data.data
                            break
                        elif hasattr(part, 'text') and part.text:
                             print(f">>> Text content found: {part.text}")
                             error_text += part.text + " "

        if image_bytes:
            tracker = CostTracker()
            tracker.add_image_cost("Regenerate Image", model=model_name)
            
            import time
            timestamp = int(time.time() * 1000)
            output_filename = f"generated_image_{timestamp}.png"
            output_path = f".tmp/{output_filename}"
            os.makedirs(".tmp", exist_ok=True)
            
            with open(output_path, "wb") as f:
                f.write(image_bytes)
                
            print(f">>> Image saved to {output_path}")
            return f"/assets/{output_filename}", None
        else:
            final_error = f"No image data. Reason: {finish_reason}"
            if error_text:
                final_error += f" | Details: {error_text.strip()}"
            return None, final_error
            
    except Exception as e:
        print(f"Error generating image: {str(e)}")
        return None, str(e)

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


def regenerate_image_with_context(caption, style, aspect_ratio, instructions, source_image_path):
    """Regenerates image using VLM to interpret source image + instructions."""
    print(f">>> Context-aware regeneration. Source: {source_image_path}")
    
    # 1. Read Image
    try:
        with open(source_image_path, "rb") as f:
            image_bytes = f.read()
    except Exception as e:
        print(f"Error reading source image: {e}")
        return regenerate_image(caption, style, aspect_ratio, instructions)

    # 2. VLM Call (Gemini 3 Pro) to creates new prompt
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    # Map style
    style_key_map = {
        "minimal": "Minimal Illustration",
        "infographic": "Infographic / Chart",
        "ugc": "UGC / YT Thumbnail",
        "mockup": "Device Mockup",
        "cinematic": "Cinematic (Video)"
    }
    target_style = style_key_map.get(style.lower(), "Minimal Illustration")

    system_prompt = """You are an expert AI Art Director specializing in image editing.
Your goal is to write a precise, descriptive image generation prompt that RECREATES the provided image while applying the user's refinement instructions.
CRITICAL: You MUST describe the composition, layout, camera angle, lighting, and subject placement in extreme detail to ensure the new image matches the structure of the original.
Analyze the provided image to understand its visual structure.
Then, apply the USER INSTRUCTIONS to modify the specific elements requested, but KEEP the overall composition and structure identical unless instructed otherwise.
Output ONLY the final image generation prompt. Do not add conversational text."""

    user_content = [
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        f"\n\nORIGINAL CAPTION CONTEXT: {caption}\n",
        f"TARGET STYLE: {target_style}\n",
        f"TARGET ASPECT RATIO: {aspect_ratio}\n",
        f"USER INSTRUCTIONS: {instructions if instructions else 'Keep the core concept but improve quality and adherence to style.'}\n\n",
        "TASK: Write a new, detailed image generation prompt that incorporates the user's instructions into the visual embodied by the image."
    ]

    try:
        vlm_model = os.getenv("GEMINI_TEXT_MODEL", "gemini-3-pro-preview")
        print(">>> Calling VLM for prompt engineering...")
        response = client.models.generate_content(
            model=vlm_model,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
            ),
            contents=user_content
        )
        
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tracker = CostTracker()
            tracker.add_gemini_cost("Image Context Refinement", response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count, model=vlm_model)
        
        new_prompt = response.text.strip()
        print(f">>> New Prompt Derived: {new_prompt}")
        
        # Clean prompt
        if new_prompt.startswith("```"):
            new_prompt = new_prompt.strip("`").replace("json", "").replace("text", "").strip()

    except Exception as e:
        print(f"VLM Error: {e}")
        # Fallback
        return regenerate_image(caption, style, aspect_ratio, instructions)

    # 3. Generate Image (Editing Mode)
    # Pass the original image bytes for semantic editing, not just the prompt
    image_url, error_msg = generate_image_asset(new_prompt, aspect_ratio=aspect_ratio, source_image_bytes=image_bytes)
    
    output_path = ".tmp/regenerated_image.json"
    result = {
        "asset_url": image_url,
        "final_image_prompt": new_prompt
    }
    
    if error_msg:
        result["error"] = error_msg
    
    with open(output_path, "w") as f:
        json.dump(result, f, indent=4)
        
    print(f"Result saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regenerate image for a caption.")
    parser.add_argument("--caption", required=True, help="The caption context.")
    parser.add_argument("--style", default="minimal", help="Visual style.")
    parser.add_argument("--aspect_ratio", default="16:9", help="Target aspect ratio.")
    parser.add_argument("--instructions", default=None, help="User instructions for refinement.")
    parser.add_argument("--source_image", default=None, help="Path to source image for context.")
    parser.add_argument("--color_palette", default="brand", help="Color palette name.")
    
    args = parser.parse_args()
    
    if args.source_image and os.path.exists(args.source_image):
        regenerate_image_with_context(args.caption, args.style, args.aspect_ratio, args.instructions, args.source_image)
    else:
        regenerate_image(args.caption, args.style, args.aspect_ratio, args.instructions)
