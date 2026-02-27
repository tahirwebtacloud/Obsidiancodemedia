import os
import json
import argparse
import sys
import io
import requests

# Force UTF-8 for stdout/stderr
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types
from cost_tracker import CostTracker

# Import visual context builder from generate_assets
sys.path.insert(0, os.path.dirname(__file__))
try:
    from generate_assets import _build_visual_parts
except ImportError:
    # Fallback if import fails
    def _build_visual_parts(path):
        return [], ""

def call_llm(system_prompt, user_content, json_output=True):
    """Calls Gemini LLM"""
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3-pro-preview")
    
    if not api_key:
        print("Error: GOOGLE_GEMINI_API_KEY not found")
        return None
    
    try:
        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7
        )
        if json_output:
            config.response_mime_type = "application/json"
            
        response = client.models.generate_content(
            model=model_name,
            config=config,
            contents=user_content
        )
        
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tracker = CostTracker()
            tracker.add_gemini_cost("Carousel Generation", response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count, model=model_name)
            
        return response.text.strip()
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        return None

def load_research_data():
    """Load research data from viral research and analysis"""
    research_data = ""
    
    # Load viral research results
    viral_path = ".tmp/viral_research.json"
    if os.path.exists(viral_path):
        with open(viral_path, "r", encoding="utf-8") as f:
            viral = json.load(f)
            research_data += f"\n### VIRAL RESEARCH INSIGHTS:\n{json.dumps(viral, indent=2)}\n"
    
    # Load analysis results
    analysis_path = ".tmp/analysis.json"
    if os.path.exists(analysis_path):
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)
            research_data += f"\n### TOPIC ANALYSIS:\n{json.dumps(analysis, indent=2)}\n"
    
    return research_data

def plan_carousel_structure(topic, purpose, research_data, visual_context_path=None):
    """Phase 1: LLM plans the carousel structure based on research"""
    print("\n" + "="*60)
    print("PHASE 1: PLANNING CAROUSEL STRUCTURE")
    print("="*60)
    
    # --- LOAD VISUAL CONTEXT (if provided) ---
    if visual_context_path:
        visual_parts, visual_desc = _build_visual_parts(visual_context_path)
    else:
        visual_parts, visual_desc = [], ""
    
    # --- STEP 1: PLAN CAROUSEL STRUCTURE ---
    print(">>> Step 1: Planning carousel structure...")
    
    system_prompt = """You are an expert LinkedIn carousel strategist. Analyze the research and plan a high-performing carousel.

Your job is to:
1. Decide the optimal number of MID SLIDES (between 5-10) based on topic complexity
2. Design a scroll-stopping hook/title
3. Outline each slide's purpose and key message
4. Plan a compelling CTA

Be strategic and data-driven."""

    user_content = f"""# CAROUSEL PLANNING TASK

## Topic
{topic}

## Purpose
{purpose}

{visual_desc if visual_desc else ""}

## Research Data
{research_data if research_data else "No research data available - use your expertise."}

## YOUR TASK
Analyze the research and create a STRATEGIC CAROUSEL PLAN.

OUTPUT FORMAT (JSON):
{{
  "hook_strategy": "Why this hook will stop scrolling",
  "title": "Main headline for slide 1",
  "subtitle": "Subheadline for slide 1",
  "num_mid_slides": 7,
  "mid_slides_outline": [
    {{"slide_num": 2, "purpose": "Establish problem", "key_message": "What to say"}},
    {{"slide_num": 3, "purpose": "First solution", "key_message": "What to say"}},
    ...
  ],
  "cta_strategy": "Why this CTA will drive action",
  "cta_title": "Main CTA text",
  "cta_subtitle": "Supporting CTA text",
  "total_slides": 9
}}

DECIDE: How many mid slides (5-10) does this topic need?
"""

    raw_response = call_llm(system_prompt, user_content, json_output=True)
    
    if not raw_response:
        print("❌ Failed to get planning response from LLM")
        return None
    
    try:
        plan = json.loads(raw_response)
        print(f"\n✅ CAROUSEL PLAN CREATED:")
        print(f"   - Total Slides: {plan.get('total_slides', 'N/A')}")
        print(f"   - Mid Slides: {plan.get('num_mid_slides', 'N/A')}")
        print(f"   - Hook: {plan.get('title', 'N/A')[:50]}...")
        return plan
    except Exception as e:
        print(f"❌ Failed to parse planning JSON: {e}")
        return None

def generate_slide_content(topic, purpose, carousel_plan, research_data):
    """Phase 2: Generate detailed text content for each slide"""
    print("\n" + "="*60)
    print("PHASE 2: GENERATING SLIDE CONTENT")
    print("="*60)
    
    system_prompt = """You are an expert LinkedIn content writer specializing in viral carousels.

Your job is to write engaging, value-packed content for each slide based on the strategic plan."""

    mid_slides_outline = carousel_plan.get("mid_slides_outline", [])
    
    user_content = f"""# CONTENT GENERATION TASK

## Topic
{topic}

## Carousel Plan Summary
- Title: {carousel_plan.get('title')}
- Number of mid slides: {len(mid_slides_outline)}
- CTA: {carousel_plan.get('cta_title')}

## Mid Slides Outline
{json.dumps(mid_slides_outline, indent=2)}

## Research Context
{research_data if research_data else "Use your expertise"}

## YOUR TASK
Write compelling, specific content for each mid slide.

OUTPUT FORMAT (JSON):
{{
  "slides": [
    {{"number": 2, "title": "Slide title/point", "body": "2-3 sentences explaining this point"}},
    {{"number": 3, "title": "Slide title/point", "body": "2-3 sentences explaining this point"}},
    ...
  ]
}}

Write {len(mid_slides_outline)} mid slides (numbers 2 through {len(mid_slides_outline) + 1}).
"""

    raw_response = call_llm(system_prompt, user_content, json_output=True)
    
    if not raw_response:
        print("❌ Failed to generate slide content")
        return None
    
    try:
        content = json.loads(raw_response)
        slides = content.get("slides", [])
        print(f"\n✅ GENERATED CONTENT FOR {len(slides)} SLIDES")
        return slides
    except Exception as e:
        print(f"❌ Failed to parse content JSON: {e}")
        return None

def generate_caption(topic, purpose, carousel_plan, slides_content):
    """Phase 3: Generate LinkedIn caption AFTER all slides are ready"""
    print("\n" + "="*60)
    print("PHASE 3: GENERATING CAPTION")
    print("="*60)
    
    # Load Voice & Tone Directive (applies to ALL captions)
    voice_tone_path = ".agent/skills/brand-identity/resources/voice-tone.md"
    voice_tone = ""
    if os.path.exists(voice_tone_path):
        with open(voice_tone_path, "r", encoding="utf-8") as f:
            voice_tone = f.read()

    # Load Brand Knowledge Base (proof points, case studies, services)
    brand_knowledge_path = "directives/brand_knowledge.md"
    brand_knowledge = ""
    if os.path.exists(brand_knowledge_path):
        with open(brand_knowledge_path, "r", encoding="utf-8") as f:
            brand_knowledge = f.read()

    directive_path = f"directives/{purpose}_caption.md"
    if os.path.exists(directive_path):
        with open(directive_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    else:
        system_prompt = "You are an expert LinkedIn content writer. Write engaging captions that drive engagement."

    # Prepend voice-tone + brand knowledge to system prompt
    brand_context = ""
    if voice_tone:
        brand_context += voice_tone
    if brand_knowledge:
        brand_context += "\n\n---\n\n" + brand_knowledge
    if brand_context:
        system_prompt = brand_context + "\n\n---\n\n" + system_prompt

    slides_summary = "\n".join([f"Slide {s.get('number')}: {s.get('title')}" for s in slides_content])
    
    user_content = f"""# CAPTION GENERATION

## Topic
{topic}

## Carousel Structure
Title: {carousel_plan.get('title')}
{slides_summary}
CTA: {carousel_plan.get('cta_title')}

## YOUR TASK
Write a scroll-stopping LinkedIn caption for this carousel.

OUTPUT: Just the caption text (no JSON, no formatting).
"""

    caption = call_llm(system_prompt, user_content, json_output=False)
    
    if caption:
        print(f"\n✅ CAPTION GENERATED ({len(caption)} chars)")
        return caption
    else:
        print("❌ Failed to generate caption")
        return f"Check out my latest carousel on {topic}!"

def generate_carousel(topic, purpose="authority", visual_context_path=None):
    """Main carousel generation orchestrator"""
    print("\n" + "="*60)
    print(f"🎯 STARTING CAROUSEL GENERATION")
    print(f"   Topic: {topic}")
    print(f"   Purpose: {purpose}")
    print("="*60)
    
    # Load research data (already done by orchestrator)
    research_data = load_research_data()
    
    # PHASE 1: Plan structure
    carousel_plan = plan_carousel_structure(topic, purpose, research_data)
    if not carousel_plan:
        print("❌ Planning failed. Aborting.")
        return
    
    # PHASE 2: Generate slide content
    slides_content = generate_slide_content(topic, purpose, carousel_plan, research_data)
    if not slides_content:
        print("❌ Content generation failed. Aborting.")
        return
    
    # PHASE 3: Generate caption (AFTER slides)
    caption = generate_caption(topic, purpose, carousel_plan, slides_content)
    
    # Save carousel layout (visible to user for manual verification)
    layout_path = ".tmp/carousel_layout.json"
    layout = {
        "topic": topic,
        "purpose": purpose,
        "plan": carousel_plan,
        "slides": [
            {
                "type": "title",
                "number": 1,
                "title": carousel_plan.get("title"),
                "subtitle": carousel_plan.get("subtitle")
            }
        ] + [
            {
                "type": "content",
                "number": s.get("number"),
                "title": s.get("title"),
                "body": s.get("body")
            } for s in slides_content
        ] + [
            {
                "type": "cta",
                "number": len(slides_content) + 2,
                "title": carousel_plan.get("cta_title"),
                "subtitle": carousel_plan.get("cta_subtitle")
            }
        ],
        "caption": caption
    }
    
    with open(layout_path, "w", encoding="utf-8") as f:
        json.dump(layout, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ CAROUSEL LAYOUT saved to: {layout_path}")
    
    # PLACID GENERATION - DEACTIVATED
    print("\n" + "="*60)
    print("⏸️  PLACID API GENERATION - DEACTIVATED")
    print("   (Awaiting new API credentials)")
    print("="*60)
    
    # Create placeholder slide URLs
    slide_urls = []
    for slide in layout["slides"]:
        slide_urls.append({
            "type": slide["type"],
            "number": slide.get("number"),
            "title": slide.get("title", ""),
            "subtitle": slide.get("subtitle", ""),
            "body": slide.get("body", ""),
            "url": f"PLACEHOLDER_URL_SLIDE_{slide.get('number', 0)}"
        })
    
    # Create visible content for the UI (Append slides to caption)
    # Using specific formatting to make it stand out in the text box
    ui_caption = caption 
    ui_caption += "\n\n" + "░"*50 + "\n"
    ui_caption += "      🎞️ CAROUSEL SLIDE LAYOUT 🎞️      \n"
    ui_caption += "░"*50 + "\n"
    
    for slide in layout["slides"]:
        ui_caption += f"\n📍 SLIDE {slide.get('number')} [{slide['type'].upper()}]\n"
        ui_caption += "-"*40 + "\n"
        
        if slide.get("title"): 
            ui_caption += f"📌 TITLE: {slide.get('title')}\n"
        if slide.get("subtitle"): 
            ui_caption += f"📝 SUBTITLE: {slide.get('subtitle')}\n"
        if slide.get("body"): 
            ui_caption += f"📄 BODY: {slide.get('body')}\n"
            
        ui_caption += "\n" # Extra spacing between slides

    # Save final plan
    # delivering clean structure for webhook processing
    final_plan = {
        "caption": ui_caption, # Visible in UI (Caption + Layout)
        "clean_caption": caption, # PURE caption for webhook if needed
        "source": "carousel",
        "type": "carousel",
        "carousel_slides": slide_urls,
        "carousel_layout": layout,
        "asset_url": "https://placehold.co/1080x1350/E5E7EB/1F2937?text=Carousel+Generated", 
        "placid_status": "DEACTIVATED"
    }
    
    output_path = ".tmp/final_plan.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_plan, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ FINAL PLAN saved to: {output_path}")
    print(f"\n{'='*60}")
    print(f"🎉 CAROUSEL GENERATION COMPLETE!")
    print(f"   Total Slides: {len(slide_urls)}")
    print(f"   Layout: {layout_path}")
    print(f"   Final Plan: {output_path}")
    print(f"{'='*60}\n")
    
    return True  # Success

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate LinkedIn carousel with research-driven planning.")
    parser.add_argument("--topic", required=True, help="Carousel topic")
    parser.add_argument("--purpose", default="authority", help="Post purpose (how to, authority, etc)")
    parser.add_argument("--visual_context", help="Path to JSON file with visual context")
    
    args = parser.parse_args()
    generate_carousel(args.topic, args.purpose, args.visual_context)
