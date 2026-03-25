import os
import json
import argparse
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

from cost_tracker import CostTracker

def call_llm(system_prompt, user_content):
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.5),
            contents=user_content
        )
        
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tracker = CostTracker()
            tracker.add_gemini_cost("Rank and Analyze", response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count, model=model_name)
            
        return response.text.strip()
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        return None

def rank_and_analyze(topic):
    """
    Ranks posts and extracts structural patterns using LLM.
    """
    output_path = ".tmp/analysis.json"
    analysis_sources = []
    
    # 1. Collect Sources
    viral_trends_path = ".tmp/viral_trends.json"
    if os.path.exists(viral_trends_path):
        with open(viral_trends_path, "r") as f:
            analysis_sources.extend(json.load(f))
            
    yt_research_path = ".tmp/youtube_research.json"
    if os.path.exists(yt_research_path):
        with open(yt_research_path, "r") as f:
            analysis_sources.extend(json.load(f))

    jina_source_path = ".tmp/source_content.md"
    if os.path.exists(jina_source_path):
        with open(jina_source_path, "r", encoding="utf-8") as f:
            jina_content = f.read()
        analysis_sources.append({"text": jina_content[:2000], "type": "web_search"})

    # PERFORMANCE: Check if we have real viral/competitor data worth an LLM call,
    # or just jina web snippets (which the main generate_assets LLM already consumes directly).
    has_rich_sources = os.path.exists(viral_trends_path) or os.path.exists(yt_research_path)

    if not analysis_sources:
        print("Warning: No research sources found. Using baseline analysis.")
        analysis = {
            "common_patterns": {
                "hooks": ["I realized I've been approaching [Topic] all wrong."],
                "ctas": ["What's your take? Drop it below \u2193"]
            }
        }
    elif not has_rich_sources:
        # FAST PATH: Only jina web search snippets — skip expensive LLM call.
        # The main generation LLM in generate_assets.py already reads source_content.md
        # directly and produces better hooks/CTAs in context of the actual post.
        print(f">>> FAST PATH: {len(analysis_sources)} web-only sources — skipping LLM analysis (generate_assets handles it).")
        analysis = {
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
    else:
        print(f"Analyzing {len(analysis_sources)} sources for topic: {topic}")
        
        # Prepare content for LLM
        context = ""
        for i, src in enumerate(analysis_sources[:10]): # Limit to top 10 for context window
            text = src.get("text") or src.get("description") or src.get("transcript", "")
            context += f"\n--- Source {i+1} ---\n{text[:1000]}\n"

        system_prompt = """You are a viral LinkedIn content analyst. 
Analyze the provided posts and resources.
Task:
1. Extract the top 3 most effective 'Hooks' (opening lines).
2. Extract the top 3 most effective 'CTAs' (call to actions).
3. Identify 3 successful content structures (e.g., 'Problem-Solution-Insight').

Return JSON only in this format:
{
  "common_patterns": {
    "hooks": ["...", "...", "..."],
    "ctas": ["...", "...", "..."],
    "structures": ["...", "...", "..."]
  }
}"""
        
        user_content = f"Topic: {topic}\nContext Sources:\n{context}"
        
        llm_response = call_llm(system_prompt, user_content)
        
        if not llm_response:
             print("Error: LLM returned no response.")
             analysis = {"common_patterns": {"hooks": [], "ctas": [], "structures": []}}
        else:
            try:
                # Strip markdown code blocks if present
                clean_json = llm_response.strip("`").replace("json", "").strip()
                analysis = json.loads(clean_json)
            except Exception as e:
                print(f"Failed to parse LLM analysis: {e}")
                analysis = {"common_patterns": {"hooks": [], "ctas": [], "structures": []}}
    
    with open(output_path, "w") as f:
        json.dump(analysis, f, indent=4)

    print(f"Analysis saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rank and analyze LinkedIn posts.")
    parser.add_argument("--topic", required=True, help="The topic to analyze against.")
    
    args = parser.parse_args()
    rank_and_analyze(args.topic)
