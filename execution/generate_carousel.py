"""
generate_carousel.py
--------------------
Dedicated carousel generator for LinkedIn multi-slide posts.

Carousel Generation Flow (3 phases):
  Phase 1 — Plan Structure:
    - Analyze source content / topic
    - Decide optimal slide count (3-10 slides)
    - Define hook strategy, narrative arc, and CTA placement

  Phase 2 — Generate Content:
    - Generate text for each slide
    - Ensure visual consistency across slides
    - Apply brand colors and typography

  Phase 3 — Generate Caption:
    - Write LinkedIn caption after slides are ready
    - Include carousel teaser and engagement hook

Routing:
  - orchestrator.py routes here when visual_aspect == "carousel"
  - Uses _build_visual_parts from generate_assets.py for source analysis

Output:
  - .tmp/final_plan.json — slides array, caption, image_prompts per slide
"""

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

# Import visual context builder and user context loader from generate_assets
sys.path.insert(0, os.path.dirname(__file__))
try:
    from generate_text_post import _build_visual_parts, _load_user_generation_context, _build_user_context_sections
except ImportError:
    # Fallback if import fails
    def _build_visual_parts(path):
        return [], ""
    def _load_user_generation_context(uid="default", topic=""):
        return {"has_persona": False, "has_brand": False, "voice_context": ""}
    def _build_user_context_sections(ctx, palette="brand"):
        return {"system": "", "runtime": ""}

def _handle_tavily_search(query: str) -> str:
    """Search the web for tools, resources, and GitHub repos using the Tavily API."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY not found in environment."

    print(f"    [tavily] Searching web for: {query}")
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": False,
                "include_raw_content": False,
                "max_results": 3
            },
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if not results:
                return "No results found."

            output = []
            for r in results:
                output.append(f"Title: {r.get('title')}\nURL: {r.get('url')}\nContent: {r.get('content')}\n---")
            return "\n".join(output)
        else:
            return f"Error from Tavily API: {response.status_code} {response.text}"
    except Exception as e:
        return f"Exception calling Tavily: {str(e)}"

def call_llm(system_prompt, user_content, json_output=True, allow_tavily=False):
    """Calls Gemini LLM"""
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")

    if not api_key:
        print("Error: GOOGLE_GEMINI_API_KEY not found")
        return None

    try:
        client = genai.Client(api_key=api_key)

        tools = [types.Tool(google_search=types.GoogleSearch())]
        if allow_tavily:
            tavily_decl = types.FunctionDeclaration(
                name="tavily_search",
                description="Search the web for tools, latest resources, and GitHub repos. Use this to find lead magnets.",
                parameters={"type": "OBJECT", "properties": {"query": {"type": "STRING", "description": "Search query"}}, "required": ["query"]},
            )
            tools.append(types.Tool(function_declarations=[tavily_decl]))

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
            tools=tools,
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO"),
                include_server_side_tool_invocations=True
            )
        )
        if json_output:
            config.response_mime_type = "application/json"

        chat = client.chats.create(model=model_name, config=config)
        response = chat.send_message(user_content)

        # Simple tool calling loop (max 3 rounds)
        for _ in range(3):
            if not response.candidates:
                break
            candidate = response.candidates[0]
            function_calls = getattr(candidate, "function_calls", [])
            if not function_calls and hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                function_calls = [p.function_call for p in candidate.content.parts if getattr(p, "function_call", None)]

            if not function_calls:
                break

            fn_parts = []
            for call in function_calls:
                fn_name = getattr(call, "name", "")
                fn_args = dict(call.args) if getattr(call, "args", None) else {}
                if fn_name == "tavily_search":
                    res = _handle_tavily_search(fn_args.get("query", ""))
                    fn_parts.append(types.Part.from_function_response(name=fn_name, response={"content": res}))

            if fn_parts:
                response = chat.send_message(fn_parts)
            else:
                break

        # Extract final text
        final_text = ""
        if response and response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    final_text += part.text

        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tracker = CostTracker()
            tracker.add_gemini_cost("Carousel Generation", response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count, model=model_name)

        return final_text.strip()
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

def plan_carousel_structure(topic, purpose, research_data, visual_context_path=None, user_context_sections=None):
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
    
    _sys_base = """You are an expert LinkedIn carousel strategist. Analyze the research and plan a high-performing carousel.

## FACT CHECKING & GROUNDING
You MUST use the built-in Google Search tool to verify all product names, AI model versions (e.g., 'Gemini 3.5' vs 'Gemini 1.5'), release dates, and technical capabilities before writing the post. Do NOT hallucinate versions or features. If a claim seems incorrect, search the web to correct it before drafting.

Your job is to:
1. Decide the optimal number of MID SLIDES (between 5-10) based on topic complexity
2. Design a scroll-stopping hook/title
3. Outline each slide's purpose and key message
4. Plan a compelling CTA

Be strategic and data-driven."""
    # Prepend user persona/brand/voice context if available
    if user_context_sections and user_context_sections.get("system"):
        system_prompt = user_context_sections["system"] + "\n\n---\n\n" + _sys_base
    else:
        system_prompt = _sys_base

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

    # Inject user runtime context into the prompt
    if user_context_sections and user_context_sections.get("runtime"):
        user_content += f"\n\n## ACTIVE USER CONTEXT\n{user_context_sections['runtime']}\n"

    raw_response = call_llm(system_prompt, user_content, json_output=True)
    
    if not raw_response:
        print("❌ Failed to get planning response from LLM")
        return None
    
    try:
        import re
        cleaned_response = raw_response.strip()
        cleaned_response = re.sub(r'^```[a-zA-Z]*\s*\n', '', cleaned_response)
        cleaned_response = re.sub(r'\n\s*```$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        plan = json.loads(cleaned_response)
        print(f"\n✅ CAROUSEL PLAN CREATED:")
        print(f"   - Total Slides: {plan.get('total_slides', 'N/A')}")
        print(f"   - Mid Slides: {plan.get('num_mid_slides', 'N/A')}")
        print(f"   - Hook: {plan.get('title', 'N/A')[:50]}...")
        return plan
    except Exception as e:
        print(f"❌ Failed to parse planning JSON: {e}")
        return None

def generate_slide_content(topic, purpose, carousel_plan, research_data, user_context_sections=None):
    """Phase 2: Generate detailed text content for each slide"""
    print("\n" + "="*60)
    print("PHASE 2: GENERATING SLIDE CONTENT")
    print("="*60)
    
    _sys_base = """You are an expert LinkedIn content writer specializing in viral carousels.

## FACT CHECKING & GROUNDING
You MUST use the built-in Google Search tool to verify all product names, AI model versions (e.g., 'Gemini 3.5' vs 'Gemini 1.5'), release dates, and technical capabilities before writing the post. Do NOT hallucinate versions or features. If a claim seems incorrect, search the web to correct it before drafting.

Your job is to write engaging, value-packed content for each slide based on the strategic plan."""
    if user_context_sections and user_context_sections.get("system"):
        system_prompt = user_context_sections["system"] + "\n\n---\n\n" + _sys_base
    else:
        system_prompt = _sys_base

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
        import re
        cleaned_response = raw_response.strip()
        cleaned_response = re.sub(r'^```[a-zA-Z]*\s*\n', '', cleaned_response)
        cleaned_response = re.sub(r'\n\s*```$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        content = json.loads(cleaned_response)
        slides = content.get("slides", [])
        print(f"\n✅ GENERATED CONTENT FOR {len(slides)} SLIDES")
        return slides
    except Exception as e:
        print(f"❌ Failed to parse content JSON: {e}")
        return None

def generate_caption(topic, purpose, carousel_plan, slides_content, user_context_sections=None):
    """Phase 3: Generate LinkedIn caption AFTER all slides are ready"""
    print("\n" + "="*60)
    print("PHASE 3: GENERATING CAPTION")
    print("="*60)
    
    # NOTE: Static voice-tone.md and brand_knowledge.md removed.
    # Each user's voice/tone and brand data now flows exclusively from
    # their Supabase profile via user_context_sections to prevent cross-user data leaks.

    directive_path = f"directives/{purpose}_caption.md"
    if os.path.exists(directive_path):
        with open(directive_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    else:
        system_prompt = "You are an expert LinkedIn content writer. Write engaging captions that drive engagement."

    # Prepend dynamic user persona/brand context so it governs all output
    prefix_blocks = []
    if user_context_sections and user_context_sections.get("system"):
        prefix_blocks.append(user_context_sections["system"])
    if prefix_blocks:
        system_prompt = "\n\n---\n\n".join(prefix_blocks + [system_prompt])

    system_prompt += "\n\n## LEAD MAGNET HUNTER & ENGAGEMENT BAIT\n"
    system_prompt += "You have access to a `tavily_search` tool. Decide if the carousel topic warrants a lead magnet. If it does, use the tool to search the web for the latest, most relevant tools, GitHub repos, or resources related to the topic. You may call the search tool multiple times if needed.\n"
    system_prompt += "If you find a great resource, organically integrate an 'Engagement Bait' Call-To-Action at the end of the caption (e.g., 'Comment [KEYWORD] and I will DM you the link to the [Resource]'). The keyword should be punchy and relevant."

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

    caption = call_llm(system_prompt, user_content, json_output=False, allow_tavily=True)
    
    if caption:
        print(f"\n✅ CAPTION GENERATED ({len(caption)} chars)")
        return caption
    else:
        print("❌ Failed to generate caption")
        return f"Check out my latest carousel on {topic}!"

def generate_carousel(topic, purpose="authority", visual_context_path=None, user_id="default"):
    """Main carousel generation orchestrator"""
    print("\n" + "="*60)
    print(f"🎯 STARTING CAROUSEL GENERATION")
    print(f"   Topic: {topic}")
    print(f"   Purpose: {purpose}")
    print("="*60)
    
    # Load user persona + brand + voice context from Supabase
    user_context = _load_user_generation_context(user_id, topic=topic)
    user_context_sections = _build_user_context_sections(user_context, "brand")
    if user_context.get("has_persona") or user_context.get("has_brand"):
        print(
            f">>> Loaded tenant context for carousel "
            f"user={user_context.get('user_id')} "
            f"(persona={user_context.get('has_persona')}, brand={user_context.get('has_brand')})"
        )
    
    # Load research data (already done by orchestrator)
    research_data = load_research_data()
    
    # PHASE 1: Plan structure
    carousel_plan = plan_carousel_structure(topic, purpose, research_data, user_context_sections=user_context_sections)
    if not carousel_plan:
        print("❌ Planning failed. Aborting.")
        return
    
    # PHASE 2: Generate slide content
    slides_content = generate_slide_content(topic, purpose, carousel_plan, research_data, user_context_sections=user_context_sections)
    if not slides_content:
        print("❌ Content generation failed. Aborting.")
        return
    
    # PHASE 3: Generate caption (AFTER slides)
    caption = generate_caption(topic, purpose, carousel_plan, slides_content, user_context_sections=user_context_sections)
    
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
    parser.add_argument("--user_id", default="default", help="Active user ID for tenant-scoped persona/brand/voice injection.")
    
    args = parser.parse_args()
    generate_carousel(args.topic, args.purpose, args.visual_context, user_id=args.user_id)
