import os
import json
import argparse
import requests
import sys
import io
import re
import random

# Force UTF-8 for stdout/stderr to handle emojis on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from google import genai
from google.genai import types
from PIL import Image, ImageFilter, ImageStat

# --- LOGO PATH (single icon, no background) ---
LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", ".agent", "skills", "brand-identity", "resources", "OBSIDIAN LOGIC.png")


def _composite_logo(image_path, logo_variant="light", logo_position="bottom-right", max_logo_ratio=0.12):
    """Overlay brand logo onto generated image at the specified corner.
    logo_variant: 'light' = Logo.png (dark logo for light bg), 'dark' = Logo contrast.png (light logo for dark bg)
    logo_position: 'top-left', 'top-right', 'bottom-left', 'bottom-right'
    """
    if logo_variant not in ("light", "dark", "auto"):
        logo_variant = "auto"
    if logo_position not in (
        "top-left",
        "top-right",
        "bottom-left",
        "bottom-right",
        "top-center",
        "bottom-center",
        "auto",
    ):
        logo_position = "auto"
    if not os.path.exists(image_path):
        print(f">>> Image not found at {image_path}, skipping composite.")
        return

    def _trim_transparent(im_rgba, alpha_cutoff=8):
        """Crop away fully-transparent borders."""
        if im_rgba.mode != "RGBA":
            im_rgba = im_rgba.convert("RGBA")
        alpha = im_rgba.split()[-1]
        bbox = alpha.point(lambda p: 255 if p > alpha_cutoff else 0).getbbox()
        return im_rgba.crop(bbox) if bbox else im_rgba

    try:
        base = Image.open(image_path).convert("RGBA")

        short_side = min(base.width, base.height)
        aspect = (base.width / base.height) if base.height else 1.0
        # Keep the logo watermark-sized across formats
        # - landscape: slightly larger ok
        # - portrait/square: smaller so it doesn't look like a sticker
        if aspect >= 1.2:
            effective_ratio = min(max_logo_ratio, 0.12)
        elif aspect <= 0.85:
            effective_ratio = min(max_logo_ratio, 0.10)
        else:
            effective_ratio = min(max_logo_ratio, 0.11)

        max_logo_size = int(short_side * effective_ratio)
        max_logo_size = max(48, max_logo_size)
        pad = 20

        temp_logo = Image.open(LOGO_PATH).convert("RGBA")
        temp_logo = _trim_transparent(temp_logo, alpha_cutoff=8)
        temp_ratio = min(max_logo_size / temp_logo.width, max_logo_size / temp_logo.height)
        new_w = max(1, int(temp_logo.width * temp_ratio))
        new_h = max(1, int(temp_logo.height * temp_ratio))

        def _candidate_positions():
            return {
                "top-left": (pad, pad),
                "top-right": (base.width - new_w - pad, pad),
                "bottom-left": (pad, base.height - new_h - pad),
                "bottom-right": (base.width - new_w - pad, base.height - new_h - pad),
                "top-center": ((base.width - new_w) // 2, pad),
                "bottom-center": ((base.width - new_w) // 2, base.height - new_h - pad),
            }

        def _region_score(x, y):
            """Lower score = better placement. Prefers clean white/black areas."""
            x = max(0, min(x, base.width - new_w))
            y = max(0, min(y, base.height - new_h))
            region = base.crop((x, y, x + new_w, y + new_h))
            crop = region.convert("L")
            stat = ImageStat.Stat(crop)
            std = stat.stddev[0] if stat.stddev else 0.0
            mean_l = stat.mean[0] if stat.mean else 128.0
            edges = crop.filter(ImageFilter.FIND_EDGES)
            edge_mean = ImageStat.Stat(edges).mean[0]

            # Penalty: distance from pure white (255) or pure black (0)
            # Regions near 0 or 255 get low penalty; mid-tones get high penalty
            dist_to_bw = min(mean_l, 255 - mean_l)  # 0 = perfect white/black, 127 = worst
            color_penalty = dist_to_bw * 1.5

            # Penalty: colorful (saturated) regions — check RGB channel spread
            rgb_stat = ImageStat.Stat(region.convert("RGB"))
            r_m, g_m, b_m = rgb_stat.mean[:3]
            channel_spread = max(r_m, g_m, b_m) - min(r_m, g_m, b_m)
            saturation_penalty = channel_spread * 1.0

            return (std * 0.75) + (edge_mean * 1.25) + color_penalty + saturation_penalty

        positions = _candidate_positions()
        if logo_position == "auto":
            best_key = None
            best_score = None
            for key, (x, y) in positions.items():
                s = _region_score(x, y)
                if best_score is None or s < best_score:
                    best_score = s
                    best_key = key
            logo_position = best_key or "bottom-right"

        pos = positions.get(logo_position, positions["bottom-right"])
        x, y = pos
        x = max(0, min(x, base.width - new_w))
        y = max(0, min(y, base.height - new_h))
        pos = (x, y)

        if not os.path.exists(LOGO_PATH):
            print(f">>> Logo not found at {LOGO_PATH}, skipping composite.")
            return

        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo = _trim_transparent(logo, alpha_cutoff=8)
        logo_ratio = min(max_logo_size / logo.width, max_logo_size / logo.height)
        logo = logo.resize((max(1, int(logo.width * logo_ratio)), max(1, int(logo.height * logo_ratio))), Image.LANCZOS)

        base.paste(logo, pos, logo)
        base = base.convert("RGB")
        base.save(image_path, "PNG")
        print(f">>> Logo composited: variant={logo_variant}, position={logo_position}")
    except Exception as e:
        print(f">>> Logo composite error: {e}")


def _download_image_bytes(url, timeout=10):
    """Download an image URL and return (bytes, mime_type) or (None, None)."""
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "image/jpeg")
            mime = ct.split(";")[0].strip()
            return resp.content, mime
    except Exception as e:
        print(f"    [visual] Failed to download {url[:60]}: {e}")
    return None, None


def _build_visual_parts(visual_context_path):
    """Build Gemini multimodal parts from visual context JSON.
    Returns (list_of_parts, text_description) for injection into the LLM prompt."""
    if not visual_context_path or not os.path.exists(visual_context_path):
        return [], ""
    
    try:
        with open(visual_context_path, "r", encoding="utf-8") as f:
            ctx = json.load(f)
    except Exception:
        return [], ""
    
    post_type = ctx.get("source_post_type", "")
    parts = []
    desc_parts = []

    # --- Handle images/carousel (for image, carousel, or mixed types) ---
    has_images = post_type in ("image", "carousel", "mixed")
    if has_images:
        urls = ctx.get("source_carousel_slides", [])
        if not urls:
            urls = ctx.get("source_image_urls", [])
        if isinstance(urls, str):
            urls = [u.strip() for u in urls.split(",") if u.strip()]
        
        # Limit to 8 images to avoid token overload
        urls = [u for u in urls if u and u.startswith("http")][:8]
        
        downloaded = 0
        for url in urls:
            img_bytes, mime = _download_image_bytes(url)
            if img_bytes:
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))
                downloaded += 1
        
        if downloaded > 0:
            desc_parts.append(f"""[VISUAL CONTEXT: {downloaded} source image(s)/slides are attached above as visual input.]
MANDATORY VISUAL ANALYSIS — Before writing, carefully study every attached image and extract:
1. HOOK: What text/headline grabs attention first? What makes it stop-the-scroll?
2. CONTENT STRUCTURE: How is information organized? (numbered steps, before/after, comparison, data visualization, quote highlight, etc.)
3. KEY MESSAGE: What is the core insight, stat, or claim being communicated visually?
4. TYPOGRAPHY & LAYOUT: Text hierarchy, font sizes, color usage, whitespace strategy.
5. VISUAL STYLE: Photography vs illustration vs infographic vs text-heavy slide.
6. RE-HOOK / CTA: How does the visual encourage continued reading or engagement?
Use ALL of these observations to deeply inform the repurposed post content — the caption should reflect the same insights, structure, and persuasive techniques found in the source visuals.""")
            print(f"    [visual] Attached {downloaded} image(s)/slides to LLM prompt")

    # --- Handle video(s) (for video or mixed types) ---
    has_video = post_type in ("video", "mixed")
    if has_video:
        video_urls = ctx.get("source_video_urls", [])
        if not video_urls:
            single = ctx.get("source_video_url", "")
            if single:
                video_urls = [single]
        video_urls = [u for u in video_urls if u and u.startswith("http")]
        
        for i, vurl in enumerate(video_urls[:3]):  # Limit to 3 videos
            label = f" #{i+1}" if len(video_urls) > 1 else ""
            transcript = _transcribe_video(vurl)
            if transcript:
                desc_parts.append(f"[VIDEO TRANSCRIPTION{label} FROM SOURCE POST]:\n{transcript}\n[END TRANSCRIPTION]")
                print(f"    [visual] Video{label} transcribed: {len(transcript)} chars")
            else:
                desc_parts.append(f"[VIDEO{label} CONTEXT: Video was present but could not be transcribed. Use the text caption as the primary source.]")
        
        if any("TRANSCRIPTION" in d for d in desc_parts):
            desc_parts.append("""MANDATORY TRANSCRIPTION ANALYSIS — Before writing, analyze the video transcription(s) and extract:
1. HOOK: What opening line/statement grabs attention? How does the speaker draw you in?
2. KEY ARGUMENTS: What are the main points, claims, or insights presented?
3. STORYTELLING STRUCTURE: How does the speaker build their narrative? (problem→solution, chronological, contrast, etc.)
4. MEMORABLE QUOTES: Any standout phrases, one-liners, or data points worth preserving.
5. RE-HOOK / CTA: How does the speaker close? What call-to-action or takeaway do they leave?
6. TONE & VOICE: Casual, authoritative, humorous, urgent? Mirror this in the repurposed post.
Use the transcription as the PRIMARY content source — the text caption is secondary context.""")
    
    desc = "\n\n".join(desc_parts) if desc_parts else ""
    return parts, desc


def _transcribe_video(video_url, max_size_mb=20):
    """Download a video and transcribe it using Gemini's multimodal capabilities."""
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3-pro-preview")
    if not api_key:
        return None
    
    try:
        print(f"    [video] Downloading video for transcription: {video_url[:80]}")
        resp = requests.get(video_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
        if resp.status_code != 200:
            print(f"    [video] Download failed: HTTP {resp.status_code}")
            return None
        
        # Read up to max_size_mb
        chunks = []
        total = 0
        limit = max_size_mb * 1024 * 1024
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            chunks.append(chunk)
            total += len(chunk)
            if total > limit:
                print(f"    [video] Truncated at {max_size_mb}MB")
                break
        
        video_bytes = b"".join(chunks)
        if len(video_bytes) < 1000:
            print(f"    [video] Video too small ({len(video_bytes)} bytes), skipping")
            return None
        
        ct = resp.headers.get("content-type", "video/mp4")
        mime = ct.split(";")[0].strip()
        if "video" not in mime:
            mime = "video/mp4"
        
        print(f"    [video] Transcribing {len(video_bytes) / 1024 / 1024:.1f}MB video via Gemini...")
        
        client = genai.Client(api_key=api_key)
        video_part = types.Part.from_bytes(data=video_bytes, mime_type=mime)
        
        response = client.models.generate_content(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction="You are a transcription assistant. Transcribe the spoken content in this video accurately. Include speaker descriptions if multiple speakers are present. Output ONLY the transcription text, nothing else.",
                temperature=0.1,
            ),
            contents=[video_part, "Transcribe all spoken content in this video. Be thorough and accurate."]
        )
        
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tracker = CostTracker()
            tracker.add_gemini_cost("Video Transcription", response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count, model=model_name)
        
        transcript = response.text.strip()
        if transcript and len(transcript) > 20:
            return transcript
        return None
    except Exception as e:
        print(f"    [video] Transcription error: {e}")
        return None


from cost_tracker import CostTracker

def call_llm(system_prompt, user_content, json_mode=False):
    """
    Calls the Google Gemini API using the latest google-genai SDK.
    """
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3-pro-preview")
    if not api_key:
        print("Error: GOOGLE_GEMINI_API_KEY not found in environment.")
        return "Error: Missing API Key. Please add GOOGLE_GEMINI_API_KEY to your .env file."

    try:
        client = genai.Client(api_key=api_key)
        
        config_params = {
            "system_instruction": system_prompt,
            "temperature": 0.7,
        }
        if json_mode:
            config_params["response_mime_type"] = "application/json"

        # Using Gemini 3 Pro
        response = client.models.generate_content(
            model=model_name,
            config=types.GenerateContentConfig(**config_params),
            contents=user_content
        )
        
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tracker = CostTracker()
            tracker.add_gemini_cost("Text Generation", response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count, model=model_name)

        return response.text.strip()
    except Exception as e:
        print(f"Error calling Gemini: {str(e)}")
        return f"Error: Failed to generate content via Gemini. {str(e)}"

def generate_image_asset(prompt, aspect_ratio="16:9"):
    """
    Generates an image using Nano Banana Pro (gemini-3-pro-image-preview).
    """
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
    if not api_key:
        print("Error: Missing API Key for image generation.")
        return None, "Missing API Key"

    try:
        client = genai.Client(api_key=api_key)
        
        # Ensure aspect ratio is in the prompt
        final_prompt = prompt
        
        # Map to descriptive terms for better adherence
        ar_map = {
            "1:1": "Square (1:1)",
            "16:9": "Cinematic Landscape (16:9)",
            "9:16": "Vertical Story (9:16)",
            "4:5": "Portrait (4:5)"
        }
        
        ar_desc = ar_map.get(aspect_ratio, aspect_ratio)
        
        if aspect_ratio:
            # Prepend for higher attention
            final_prompt = f"Aspect Ratio: {ar_desc}. {final_prompt}"

        print(f">>> Using Nano Banana Pro ({model_name}) for prompt: {final_prompt[:50]}...")
        
        response = client.models.generate_content(
            model=model_name,
            contents=final_prompt,
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
            tracker.add_image_cost("Generate Image", model=model_name)
            
            # Save to file with unique timestamp
            import time
            timestamp = int(time.time() * 1000)
            output_filename = f"generated_image_{timestamp}.png"
            output_path = f".tmp/{output_filename}"
            
            # Ensure folder exists
            os.makedirs(".tmp", exist_ok=True)
            
            with open(output_path, "wb") as f:
                f.write(image_bytes)
                
            print(f">>> Image saved to {output_path}")
            return f"/assets/{output_filename}", None
        else:
            final_error = f"No image data. Reason: {finish_reason}"
            if error_text:
                final_error += f" | Details: {error_text.strip()}"
            print(f"Error: {final_error}")
            return None, final_error
            
    except Exception as e:
        print(f"Error generating image: {str(e)}")
        return None, str(e)

def generate_assets(post_type, purpose, topic, source="topic", style="minimal", source_content=None, aspect_ratio="16:9", visual_aspect="none", visual_context_path=None, style_type=None, color_palette="brand", reference_image_path=None, custom_topic=None):
    """
    Mega-Generation: Caption + Image Prompt + Nano Banana Pro in one pass.
    """
    print(f">>> generate_assets called with style={style}, style_type={style_type}, visual_aspect={visual_aspect}")
    # SANITIZE ASPECT RATIO: Prevent "image", "video" etc from leaking in
    if aspect_ratio.lower() in ["image", "video", "carousel", "none", "null", "undefined"]:
        print(f">>> Warning: Invalid aspect ratio '{aspect_ratio}' detected. Defaulting to 16:9.")
        aspect_ratio = "16:9"

    output_path = ".tmp/final_plan.json"
    # Route to article directives for article post type, caption directives for text posts
    if post_type.lower() == "article":
        directive_path = f"directives/{purpose}_article.md"
        print(f">>> Article mode: using {directive_path}")
    else:
        directive_path = f"directives/{purpose}_caption.md"
    image_sop_path = "directives/image_prompt_design.md"
    
    # --- LOAD CONTEXT DATA ---
    analysis = {}
    input_path = ".tmp/analysis.json"
    analysis_context = ""
    if os.path.exists(input_path):
        with open(input_path, "r") as f:
            analysis = json.load(f)
            analysis_context = f"Common Patterns Analysis:\n{json.dumps(analysis.get('common_patterns', {}))}\n"

    # Load Miro Board Strategy (Section 1 of Guidelines)
    strategy_context = ""
    try:
        guidelines_path = "LinkedIn guidelines/ULTIMATE TOP PERFORMING LINKEDIN POST GUIDELINES.txt"
        if os.path.exists(guidelines_path):
            with open(guidelines_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Extract Section 1
                start_marker = "SECTION 1: THE 4-STEP LINKEDIN CONTENT PLAYBOOK"
                end_marker = "SECTION 2:"
                if start_marker in content:
                    start_idx = content.find(start_marker)
                    end_idx = content.find(end_marker)
                    if end_idx == -1:
                        end_idx = len(content)
                    strategy_context = content[start_idx:end_idx]
    except Exception as e:
        print(f"Warning: Could not load strategy context: {e}")

    # Check for Viral Reference context
    viral_ref_path = ".tmp/viral_trends.json"
    viral_context = ""
    if os.path.exists(viral_ref_path):
        with open(viral_ref_path, "r") as f:
            viral_trends = json.load(f)
            if viral_trends:
                viral_anchor = viral_trends[0]
                viral_context = f"\nViral Anchor Reference (structural template):\nURL: {viral_anchor['url']}\nOriginal Text: {viral_anchor['text']}\n"

    # Check for Jina Search context
    jina_context_path = ".tmp/source_content.md"
    jina_content = ""
    if os.path.exists(jina_context_path):
        with open(jina_context_path, "r", encoding="utf-8") as f:
            jina_content = f.read()[:4000] # Limit to avoid token issues

    # Check for YouTube research context
    yt_research_path = ".tmp/youtube_research.json"
    yt_context = ""
    if os.path.exists(yt_research_path):
        with open(yt_research_path, "r") as f:
            yt_data = json.load(f)
            if yt_data:
                yt_context = f"\nYouTube Research Insights:\n{json.dumps(yt_data[:3])}\n"

    # Load Voice & Tone Directive (applies to ALL captions)
    voice_tone_path = ".agent/skills/brand-identity/resources/voice-tone.md"
    voice_tone = ""
    if os.path.exists(voice_tone_path):
        with open(voice_tone_path, "r", encoding="utf-8") as f:
            voice_tone = f.read()
        print(">>> Loaded founder voice-tone directive")

    # Load Brand Knowledge Base (proof points, case studies, services)
    brand_knowledge_path = "directives/brand_knowledge.md"
    brand_knowledge = ""
    if os.path.exists(brand_knowledge_path):
        with open(brand_knowledge_path, "r", encoding="utf-8") as f:
            brand_knowledge = f.read()
        print(">>> Loaded brand knowledge base")

    # Load Caption Directive
    if not os.path.exists(directive_path):
        system_prompt = "You are an expert LinkedIn copywriter. Write a post about the given topic."
    else:
        with open(directive_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()

    # Apply Surveillance Playbook Rules if source is surveillance
    if source.lower() == "surveillance":
        playbook_path = "Antigravity_Linkedin_Assessment  clean/strategy/POST_PERFORMANCE_PLAYBOOK.md"
        if os.path.exists(playbook_path):
            with open(playbook_path, "r", encoding="utf-8") as f:
                playbook_content = f.read()
            system_prompt += f"\n\n---\n## SURVEILLANCE PLAYBOOK FOR REPURPOSING\nThe user wants to repurpose a top-performing post. Read and strictly apply the formulas from this playbook to extract the exact structural DNA of the source post, and generate a new post following that exact formula, but centered around the New Topic:\n\n{playbook_content}\n\n---\n"
            print(">>> Loaded POST_PERFORMANCE_PLAYBOOK.md for surveillance repurposing")

    # Prepend voice-tone + brand knowledge to system prompt so it governs all output
    brand_context = ""
    if voice_tone:
        brand_context += voice_tone
    if brand_knowledge:
        brand_context += "\n\n---\n\n" + brand_knowledge
    if brand_context:
        system_prompt = brand_context + "\n\n---\n\n" + system_prompt

    # Load Image SOP
    image_sop = ""
    if os.path.exists(image_sop_path):
        with open(image_sop_path, "r", encoding="utf-8") as f:
            image_sop = f.read()
        
        # BIND DYNAMIC CONTEXT: Replace placeholders in SOP
        image_sop = image_sop.replace("{ASPECT_RATIO}", aspect_ratio)

    # --- LOAD STYLE TYPE PROMPTS (if applicable) ---
    # Generic: works for any visual style that has type prompts (infographic, ugc, etc.)
    style_type_prompt_section = ""
    _has_style_type = False
    _style_type_label = ""
    _style_label_for_sop = style  # human-readable style name for SOP override
    if style_type:
        style_key = style.lower()
        type_prompts_path = f"directives/style_types/{style_key}/{style_type}.json"
        if os.path.exists(type_prompts_path):
            try:
                with open(type_prompts_path, "r", encoding="utf-8") as f:
                    type_data = json.load(f)
                if type_data and "prompts" in type_data:
                    prompts = type_data["prompts"]
                    style_type_label = type_data.get("label", style_type)
                    _has_style_type = True
                    _style_type_label = style_type_label
                    print(f">>> Loaded {len(prompts)} pre-set prompts for {style_key} type: {style_type_label}")
                    
                    # Build the prompt selection section for the LLM
                    # SHUFFLE order to eliminate positional bias (LLMs favor early options)
                    _core_fields = {'id', 'best_for', 'prompt', 'layout', 'visual_hierarchy', 'focal_point', 'white_space', 'balance'}
                    shuffled_prompts = list(prompts)
                    random.shuffle(shuffled_prompts)
                    prompt_options = []
                    for i, p in enumerate(shuffled_prompts, 1):
                        prompt_block = f"""### OPTION {i} (ID: {p['id']})
**BEST FOR:** {p.get('best_for', 'General use')}
**Image Prompt:** {p['prompt']}
**Layout:** {p.get('layout', '')}
**Visual Hierarchy:** {p.get('visual_hierarchy', '')}
**Focal Point:** {p.get('focal_point', '')}
**White Space:** {p.get('white_space', '')}
**Balance:** {p.get('balance', '')}"""
                        # Render any extra metadata fields dynamically
                        for field_key, field_val in p.items():
                            if field_key not in _core_fields and field_val:
                                label = field_key.replace('_', ' ').title()
                                prompt_block += f"\n**{label}:** {field_val}"
                        prompt_options.append(prompt_block)
                    print(f">>> Shuffled template order: {[p['id'] for p in shuffled_prompts]}")
                    
                    # Map style to its SOP template name for the override notice
                    _sop_style_names = {
                        "infographic": "Infographic / Chart",
                        "ugc": "UGC / YT Thumbnail",
                        "minimal": "Minimal Illustration",
                        "mockup": "Device Mockup",
                    }
                    _style_label_for_sop = _sop_style_names.get(style_key, style)
                    
                    style_type_prompt_section = f"""
## !! CRITICAL OVERRIDE - {_style_label_for_sop.upper()} TYPE: {style_type_label.upper()} !!
**A specific sub-type has been selected. The following instructions SUPERSEDE the generic "{_style_label_for_sop}" template in the Image Prompt Design SOP above.**
**DO NOT use the generic SOP template for this style.**
**Instead, you MUST use EXACTLY one of the {len(prompts)} pre-set templates below as your LAYOUT/STRUCTURE base, but REPLACE all color references with the DYNAMIC COLOR PALETTE from the injection section above.**

You have {len(prompts)} template options below. You MUST evaluate ALL of them before choosing.

{chr(10).join(prompt_options)}

**MANDATORY TEMPLATE SCORING (you MUST do this before choosing):**
Read the "BEST FOR" tag on EACH option. Then score every template on these 3 dimensions (1-10 each):

| Template | Content Fit (does BEST FOR match THIS topic?) | Tone Match (does visual energy match emotional register?) | Layout Shape (does the structure fit the content shape?) | TOTAL | Use or Reject? | Rejection Reason |

Fill this table for ALL {len(prompts)} options. Then select the template with the HIGHEST total score.

**SCORING RULES:**
- Content Fit: Compare the post's actual topic to each template's BEST FOR tags. A direct keyword match = 8-10. Adjacent match = 5-7. Poor match = 1-4.
- Tone Match: Serious/analytical content → structured layouts (8+). Humor/relatability → meme or lifestyle formats (8+). Educational → informative/diagram (8+). Provocative → bold visual hooks (8+). Mismatched tone = 1-4.
- Layout Shape: Does the content have 2 opposing ideas? → split-screen/comparison. A process/steps? → flowchart/timeline. A single bold take? → text-heavy/minimal. Multiple data points? → grid/dashboard. A reaction/scenario? → meme format. Shape mismatch = 1-4.

**CRITICAL: You MUST reject at least {len(prompts) - 1} template(s) with an explicit reason.** "Not the best fit" is not a valid rejection. Name the specific mismatch (e.g., "Topic is a 3-step process but this template is a 2x2 grid — wrong shape").

Once selected, replace ALL {{{{TEXT_PLACEHOLDER_*}}}} / {{{{PLACEHOLDER}}}} tokens with actual content derived from the post.

**MANDATORY OUTPUT RULES:**
- **DYNAMIC COLOR OVERRIDE**: Replace ALL hardcoded color names and hex codes in the chosen template (e.g., "red", "blue", "#70181E", "Signal Yellow") with the corresponding colors from the DYNAMIC COLOR PALETTE INJECTION section above. The user-selected palette is the FINAL AUTHORITY on all colors.
- Map template colors to palette colors: primary accent colors -> palette Secondary, background colors -> palette Dark, text colors -> palette Light, highlight colors -> palette Accent, subtle/support colors -> palette Neutral.
- Fill in ALL text placeholders with real content from the caption/topic. No remaining {{{{placeholders}}}} in the final prompt.
- Keep ALL layout, visual hierarchy, focal point, white space, balance, positioning, shadows, gradients, borders, and texture instructions from the chosen template.
- Append the target aspect ratio ({aspect_ratio}) to the end of the prompt.
- Return the FULLY FILLED prompt as the image_prompt value in your JSON response.
"""
                else:
                    print(f">>> Warning: No prompts found for style_type '{style_type}' under style '{style_key}'")
            except Exception as e:
                print(f">>> Warning: Failed to load style type prompts: {e}")
        else:
            print(f">>> Warning: Type prompts file not found at {type_prompts_path}")

    # --- NEUTRALIZE SOP CONFLICTS when style_type overrides are active ---
    if _has_style_type and image_sop:
        image_sop += f"""

---
**!! SOP OVERRIDE NOTICE !!**
A specific sub-type ("{_style_type_label}") has been selected for the "{_style_label_for_sop}" style.
- **IGNORE** the generic "{_style_label_for_sop}" template above. Use the CRITICAL OVERRIDE section below instead.
- **IGNORE** the Workflow step "Fill the corresponding template above". The pre-set template below replaces it.
- **APPLY THE DYNAMIC COLOR PALETTE**: The "DYNAMIC COLOR PALETTE INJECTION" section below provides the EXACT hex codes to use. Replace any hardcoded colors in the chosen template with the palette colors. The palette is the FINAL AUTHORITY on all colors.
---
"""

    # --- LOAD COLOR PALETTE ---
    selected_palette = None
    color_palette_section = ""
    color_palette_path = "directives/color_palettes.json"
    if os.path.exists(color_palette_path):
        try:
            with open(color_palette_path, "r", encoding="utf-8") as f:
                palettes_data = json.load(f)
                palettes = {p["id"]: p for p in palettes_data.get("palettes", [])}
                
                # Validate and load selected palette
                if color_palette.lower() in palettes:
                    selected_palette = palettes[color_palette.lower()]
                    print(f">>> Loaded color palette: {selected_palette['name']} ({color_palette})")
                else:
                    print(f">>> Warning: Color palette '{color_palette}' not found. Available: {list(palettes.keys())}. Defaulting to 'brand'.")
                    selected_palette = palettes.get("brand", palettes[list(palettes.keys())[0]])
                
                # Build color analysis section for LLM
                if selected_palette:
                    color_palette_section = f"""
## !! DYNAMIC COLOR PALETTE INJECTION !!
A specific color palette has been selected: **{selected_palette['name']}**

**PALETTE COLORS:**
- Primary: {selected_palette['primary']}
- Secondary: {selected_palette['secondary']}
- Accent: {selected_palette['accent']}
- Neutral: {selected_palette['neutral']}
- Dark: {selected_palette['dark']}
- Light: {selected_palette['light']}

**SOP TEMPLATE PLACEHOLDER MAPPING (use these when filling SOP templates):**
- {{{{PRIMARY_BG}}}} = {selected_palette['dark']}
- {{{{PRIMARY_ACCENT}}}} = {selected_palette['secondary']}
- {{{{SECONDARY}}}} = {selected_palette['light']}
- {{{{NEUTRAL}}}} = {selected_palette['neutral']}

**COLOR THEORY & EMOTIONAL CONTEXT:**
{selected_palette['color_theory']}

Emotional Register: {selected_palette['emotional_context']}
Best Used For: {selected_palette['best_for']}

**MANDATORY COLOR ANALYSIS (before generating image prompt):**
1. CONTENT-COLOR FIT: Analyze the post's core message, topic, and emotional tone. Does this palette's emotional context match the post's intent?
2. COLOR PLACEMENT STRATEGY: For EACH color in the palette, decide WHERE and HOW it should appear:
   - Primary ({selected_palette['primary']}): {selected_palette['usage_guidelines']['primary_use']}
   - Secondary ({selected_palette['secondary']}): {selected_palette['usage_guidelines']['secondary_use']}
   - Accent ({selected_palette['accent']}): {selected_palette['usage_guidelines']['accent_use']}
   - Neutral ({selected_palette['neutral']}): {selected_palette['usage_guidelines']['neutral_use']}
3. VISUAL HIERARCHY: Ensure color placement guides the viewer's eye to the most important elements first.
4. CONTRAST & READABILITY: Use dark text on light backgrounds and light text on dark backgrounds.

**MANDATORY OUTPUT RULES:**
- When generating the image prompt, use the EXACT hex codes from this palette (e.g., "{selected_palette['primary']}" not "black").
- Replace ALL {{{{PRIMARY_BG}}}}, {{{{PRIMARY_ACCENT}}}}, {{{{SECONDARY}}}}, {{{{NEUTRAL}}}} placeholders in SOP templates with the mapped hex codes above.
- If using a style_type template (CRITICAL OVERRIDE), replace any hardcoded color values in that template with the corresponding palette colors above.

**ANTI-DEFAULT RULE:**
Do NOT ignore this palette and revert to #0E0E0E/#F9C74F. The selected palette ({selected_palette['name']}) is the FINAL AUTHORITY on all colors in the image prompt. No exceptions.
"""
        except Exception as e:
            print(f">>> Warning: Failed to load color palettes: {e}")
            color_palette_section = ""
    else:
        print(f">>> Warning: Color palettes file not found at {color_palette_path}")

    # --- BUILD VISUAL CONTEXT (must happen before prompt construction) ---
    visual_parts, visual_desc = _build_visual_parts(visual_context_path)

    # --- INJECT USER REFERENCE IMAGE (if provided) ---
    reference_image_desc = ""
    if reference_image_path and os.path.exists(reference_image_path):
        try:
            with open(reference_image_path, "rb") as f:
                ref_bytes = f.read()
            # Determine mime type from extension
            ext = os.path.splitext(reference_image_path)[1].lower()
            mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
            ref_mime = mime_map.get(ext, "image/png")
            ref_part = types.Part.from_bytes(data=ref_bytes, mime_type=ref_mime)
            visual_parts.append(ref_part)
            reference_image_desc = """
## USER REFERENCE IMAGE (attached above)
The user has provided a reference image for visual inspiration. Analyze this image carefully:
- **Style & Aesthetic**: What visual style, color scheme, typography, and mood does this image use?
- **Layout & Composition**: How is the content arranged? What layout patterns are used?
- **Adapt, Don't Copy**: Use the reference as INSPIRATION for the visual direction of the new image. Match its energy, style, and quality level, but create ORIGINAL content based on the topic.
- Do NOT replicate the reference image literally — extract its design principles and apply them to the new content.
"""
            print(f">>> Reference image injected: {reference_image_path} ({len(ref_bytes)} bytes)")
        except Exception as e:
            print(f">>> Warning: Failed to load reference image: {e}")

    # --- PREPARE THE MEGA PROMPT ---
    custom_topic_str = f"## NEW TOPIC OVERRIDE\nThe user has requested to repurpose the original structure and hook style from the source content, but change the subject matter entirely. Generate the post tightly aligned with this new topic:\n{custom_topic}\n" if custom_topic else ""
    
    user_content = f"""# TASK: Generate LinkedIn Post Assets
Topic: {topic}
Post Type: {post_type}
Purpose: {purpose}
Visual Aspect: {visual_aspect}
Visual Style: {style}
{f'Style Type: {style_type}' if _has_style_type else ''}
TARGET ASPECT RATIO: {aspect_ratio}

## CONTEXT DATA
{jina_content if jina_content else "No web search data available."}
{viral_context if viral_context else ""}
{yt_context if yt_context else ""}
{analysis_context if analysis_context else ""}

## DIRECT REPURPOSE SOURCE (PRIORITY)
{source_content if source_content else "No direct content provided."}

{custom_topic_str}

{visual_desc}

{reference_image_desc}

## INSTRUCTIONS

### STEP 1: DEEP SOURCE ANALYSIS (MANDATORY)
Before writing ANYTHING, analyze ALL provided source material:
- **Text Caption / Source Post**: Identify the exact formula used from the Surveillance Playbook (e.g. Identity Challenge, Money Math). Extract the hook (first 1-2 lines), the body structure (how ideas flow), the re-hook (mid-post attention recapture), and the CTA/close.
- **Visual Context** (if images/slides attached above): Follow the MANDATORY VISUAL ANALYSIS instructions in the visual context section. Extract hooks, content structure, key messages, typography patterns, and persuasive techniques from every image.
- **Video Transcription** (if provided above): Follow the MANDATORY TRANSCRIPTION ANALYSIS instructions. Extract the speaker's hook, key arguments, storytelling arc, memorable quotes, and closing CTA.
- **Cross-Reference**: Combine insights from text + visuals + transcription to understand the FULL message, not just the caption text.

### STEP 2: GENERATE REPURPOSED POST
Using your deep analysis from Step 1, generate a LinkedIn post that:
- Preserves the core insights, data points, and persuasive techniques from the source
- Adapts the content to the requested Post Type ({post_type}) and Purpose ({purpose})
- Follows the system instructions (caption directive) for tone, structure, and formatting
- If source had strong hooks/rehooks, create equally strong ones for the new format
- If source had specific data/stats/quotes (from images or transcription), incorporate them

**POST TYPE ADAPTATION ({post_type}):**
- **If "text"**: Generate a standard LinkedIn post (150-250 words max). Concise, punchy, scroll-stopping. Single cohesive message.
- **If "article"**: Generate a detailed LinkedIn article (800-1200 words). Follow the article directive structure closely. Multi-paragraph with clear sections, real depth, case studies, and proof points. Use line breaks for structure, NOT markdown headers. This is a FULL article, not an extended post.

**VISUAL ASPECT ADAPTATION ({visual_aspect}):**
- **If "none"**: Generate a standalone text post. The caption must be complete and self-contained. No visual asset needed.
- **If "image"**: Generate a text caption + image prompt. The caption should reference or complement the visual. The image amplifies one core insight from the post.
- **If "video"**: Generate a text caption + video concept. The caption should tease the video content. Include a brief video script/concept in your thinking (though only caption is returned in JSON).
- **If "carousel"**: This is handled by a separate generator, but if you receive this, treat it as a multi-slide concept where each slide builds on the previous one.

### STEP 3: VISUAL ASSET GENERATION (if Visual Aspect requires it)
**Only generate image_prompt if Visual Aspect is "image":**
- Generate a single core point/discovery (max 10 words) for visualization
{"- A SPECIFIC INFOGRAPHIC TYPE has been selected. You MUST use the pre-set template from the '!! CRITICAL OVERRIDE' section below. Do NOT use the generic SOP infographic template." if _has_style_type else "- Generate a detailed image prompt following the Artist SOP below"}
- The image should complement and amplify the caption, not just repeat it
- Use the TARGET ASPECT RATIO ({aspect_ratio}) specified above

**If Visual Aspect is "none", "video", or "carousel":**
- Leave image_prompt and single_point as empty strings
- The caption is the primary deliverable

## IMAGE PROMPT DESIGN SOP (FOR ARTIST AGENT)
{image_sop if image_sop else "Use style: " + style}

{color_palette_section}

{style_type_prompt_section}

## STRICT TYPOGRAPHIC RULES (for image prompts only)
1. Do NOT use colons (:) in any text on the image.
2. If separating phrases, use separate lines for each phrase.
3. Use H1, H2, H3 hierarchy for text sizing:
   - H1: Main Headline (Largest)
   - H2: Sub-headline (Medium)
   - H3: Details/Labels (Smallest)
4. Ensure text size varies significantly between H1, H2, and H3 to create hierarchy.

## LOGO PLACEMENT (for image prompts only)
A brand logo will be composited onto the generated image AFTER generation. You must decide:
1. **logo_position**: Choose the area with the LEAST visual content / most clean space. Options:
   - corners: "top-left", "top-right", "bottom-left", "bottom-right"
   - center edges: "top-center", "bottom-center"
   - or "auto" if you're unsure (the system will pick the emptiest region).
   Avoid areas where headline text, the focal subject, or key UI elements appear.
2. **logo_variant**: Analyze the DOMINANT BACKGROUND COLOR in the chosen area.
   - If the area is LIGHT/WHITE, use "light" (dark logo).
   - If the area is DARK/BLACK, use "dark" (light logo with white text).
   - Or "auto" if unsure (the system will pick the highest-contrast variant).

## FORMATTING
Return ONLY a valid JSON object with this structure:
{{
  "caption": "The full post text (following system instructions for structure, tone, word count)",
  "single_point": "Core discovery for image (max 10 words, or empty string if no image needed)",
  "image_prompt": "Detailed AI image prompt (or empty string if no image needed)",
  "image_palette": ["hex1", "hex2", "hex3"], // Use the EXACT hex codes from the DYNAMIC COLOR PALETTE INJECTION section
  "logo_position": "auto", // top-left, top-right, bottom-left, bottom-right, top-center, bottom-center, auto
  "logo_variant": "auto" // light, dark, auto
}}
"""

    # Build final contents: image parts first (if any), then text prompt
    if visual_parts:
        contents = visual_parts + [user_content]
        print(f">>> Requesting multimodal assets from LLM ({len(visual_parts)} visual parts + text)...")
    else:
        contents = user_content
        print(">>> Requesting combined assets from LLM (Simplified Flow)...")
    
    raw_response = call_llm(system_prompt, contents, json_mode=True)
    print(">>>STAGE:text_done", flush=True)
    
    try:
        response_data = json.loads(raw_response)
    except Exception as e:
        print(f"Error parsing JSON response: {e}")
        # Fallback to a basic structure if LLM fails JSON
        response_data = {
            "caption": raw_response,
            "single_point": topic,
            "image_prompt": f"Professional {style} image about {topic}"
        }

    caption = response_data.get("caption", "")
    image_prompt_text = response_data.get("image_prompt", "")
    palette = response_data.get("image_palette", ["#0E0E0E (Obsidian Black)", "#F9C74F (Signal Yellow)", "White"])
    logo_position = response_data.get("logo_position", "auto")
    logo_variant = response_data.get("logo_variant", "auto")

    # Prepare final plan object
    plan = {
        "caption": caption,
        "source": source,
        "analysis": analysis,
        "asset_prompts": {}
    }

    if post_type.lower() == "image":
        plan["asset_prompts"]["nano_banana_pro"] = {
            "scene": {
                "location": "modern corporate office",
                "environment": "clean, tech-focused workspace",
                "palette": palette
            },
            "technical_settings": {
                "aspect_ratio": aspect_ratio,
                "quality": "high resolution",
                "style": "Authentic iPhone photo"
            }
        }
    elif post_type.lower() == "video":
        plan["asset_prompts"]["sora_veo"] = f"A cinematic drone shot through a neon-lit city of the future, showing integrated AI systems, seamless transitions."
    elif post_type.lower() == "article":
        plan["article_outline"] = [
            f"Introduction: The shift towards {topic}",
            "Key discoveries from our research",
            "Practical applications for businesses",
            "Conclusion and next steps"
        ]

    # Handle Image Generation
    image_url = None
    error_msg = None
    
    # Determine if we need an image: Either type is 'image' OR visual_aspect is 'image'
    should_generate_image = post_type.lower() == "image" or str(visual_aspect).lower() == "image"
    
    if should_generate_image:
        print(">>>STAGE:image_start", flush=True)
        full_prompt = image_prompt_text if image_prompt_text else f"Professional {style} image about {topic}. Obsidian Black and Signal Yellow theme."
        
        # STRICT CONSTRAINT: Deterministically remove colons to enforce style rule
        full_prompt = full_prompt.replace(":", " -")
        
        # REGEX CLEANUP: Remove conflicting terms (square, portrait, landscape) if they contradict the number
        full_prompt = re.sub(r'(square|portrait|landscape|vertical|horizontal)\s+image\s+aspect\s+ratio', '', full_prompt, flags=re.IGNORECASE)
        # Handle "image aspect ratio" specifically (edge case from invalid input)
        full_prompt = re.sub(r'image\s+aspect\s+ratio', '', full_prompt, flags=re.IGNORECASE)
        
        full_prompt = re.sub(r'(square|portrait|landscape|vertical|horizontal)\s+aspect\s+ratio', '', full_prompt, flags=re.IGNORECASE)

        # Remove conflicting numbers (e.g. if we want 4:5, remove 16:9)
        common_ratios = ["16:9", "9:16", "1:1", "4:5"]
        for ratio in common_ratios:
             if ratio != aspect_ratio:
                 full_prompt = full_prompt.replace(ratio, "")
            
        print(f">>> Dynamic Image Prompt: {full_prompt[:50]}...")
        
        # Pass aspect_ratio to generate function which handles prepending
        image_url, error_msg = generate_image_asset(full_prompt, aspect_ratio=aspect_ratio)
        
    if should_generate_image:
        print(">>>STAGE:image_done", flush=True)

    if image_url:
        # Composite brand logo onto generated image
        local_image_path = image_url.replace("/assets/", ".tmp/")
        _composite_logo(local_image_path, logo_variant=logo_variant, logo_position=logo_position)
        plan["asset_url"] = image_url
        plan["final_image_prompt"] = full_prompt
        plan["logo_position"] = logo_position
        plan["logo_variant"] = logo_variant
    elif error_msg:
        plan["error"] = error_msg

    with open(output_path, "w") as f:
        json.dump(plan, f, indent=4)

    print(f"Final plan saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate post assets and captions.")
    parser.add_argument("--type", required=True, help="Post type (image, video, article, etc).")
    parser.add_argument("--purpose", default="storytelling", help="Post goal.")
    parser.add_argument("--topic", default="Modern AI", help="Topic of the post.")
    parser.add_argument("--source", default="topic", help="Content source.")
    parser.add_argument("--style", default="minimal", help="Visual style.")
    parser.add_argument("--source_content", help="Direct text content to repurpose.")
    parser.add_argument("--aspect_ratio", default="16:9", help="Target aspect ratio.")
    parser.add_argument("--visual_aspect", default="none", help="Visual aspect.")
    parser.add_argument("--style_type", default=None, help="Sub-type for the visual style (e.g. glassmorphic_venn).")
    parser.add_argument("--visual_context", help="Path to JSON file with visual context.")
    parser.add_argument("--color_palette", default="brand", help="Color palette to use (brand, pastel, neon, monochrome, warm, cool).")
    parser.add_argument("--reference_image", default=None, help="Path to a user-provided reference image for style inspiration.")
    parser.add_argument("--custom_topic", default=None, help="User-provided custom topic for repurposing.")
    
    args = parser.parse_args()
    # FIX: Read from temp file if source_content is a path
    if args.source_content and os.path.exists(args.source_content) and os.path.isfile(args.source_content):
        with open(args.source_content, "r", encoding="utf-8") as f:
            args.source_content = f.read()

    generate_assets(args.type, args.purpose, args.topic, args.source, args.style, args.source_content, args.aspect_ratio, args.visual_aspect, args.visual_context, args.style_type, args.color_palette, args.reference_image, args.custom_topic)
