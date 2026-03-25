import os
import sys
import json
import argparse
from typing import Dict, Any

# Ensure execution is in sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(override=True)

def synthesize_research(topic: str, source_file: str = ".tmp/source_content.md", output_file: str = ".tmp/synthesized_research.md") -> bool:
    """
    Reads raw, noisy web scraping data (e.g., from Tavily FB/IG/LinkedIn searches),
    cleans it out (removes SVG, HTML junk, emojis), and synthesizes it into a highly
    structured, clean Markdown brief using the Gemini LLM.
    """
    print(f">>> [RESEARCH SYNTHESIZER] Activating Deep Research for: {topic}")

    if not os.path.exists(source_file):
        print(f"[Error] Source file not found: {source_file}")
        return False

    with open(source_file, "r", encoding="utf-8") as f:
        raw_content = f.read()

    # Limit payload to prevent token explosion if raw data is massive
    char_limit = 25000 
    truncated_content = raw_content[:char_limit]

    system_prompt = """
    You didn't follow my commands properly last time, which resulted in a proper failure and haluicination, Thi time yuo must follow the exact line by line commands i have given below.

    You are an elite Intelligence Analyst and Expert Copywriter.
    Your job is to read raw, noisy data scraped from various social media platforms (LinkedIn, Facebook, X, Instagram) and synthesize it into a clean, highly structured Research Brief. 

    The raw data often contains extreme noise: SVG paths, raw HTML tags, excessive emojis, UI element text (like "Like", "Comment", "Share"), and irrelevant navigational text.
    
    YOUR RULES:
    1. IGNORE ALL NOISE. Filter out all SVG paths, HTML, and UI elements.
    2. EXTRACT THE GOLD. Focus entirely on actual insights, statistics, unique opinions, emerging trends, and compelling quotes related to the topic.
    3. BE OBJECTIVE BUT PUNCHY. Summarize the core narratives happening right now on social media about this topic.
    4. MUST OUTPUT PURE MARKDOWN ONLY. No json blocks, just direct markdown.
    5. USE GOOGLE SEARCH. You MUST actively use your Google Search tool to verify breaking news, find hard statistics, and supplement the brief with the absolute latest context. Do not guess; search it.

    OUTPUT STRUCTURE REQUIRED:
    # Deep Research Brief: [Topic]

    ## 1. The Core Narrative
    (2-3 sentences summarizing the dominant conversation around this topic right now)

    ## 2. Key Insights & Trends
    - (Insight 1: detailed explanation)
    - (Insight 2: detailed explanation)
    - (Insight 3: detailed explanation)

    ## 3. Notable Statistics & Data Points
    (List any solid numbers, percentages, or data points mentioned in the data. If none, say "No hard data found.")

    ## 4. Controversies or Counter-Narratives
    (What are people disagreeing about? Are there contrarian takes?)

    ## 5. Swipe File (Best Quotes/Hooks)
    (Copy-paste 2-3 of the most compelling sentences or hooks written by real people in the raw data)
    """

    user_prompt = f"TOPIC: {topic}\n\nRAW NOISY DATA:\n{truncated_content}"

    print(f">>> [RESEARCH SYNTHESIZER] Analyzing {len(truncated_content)} chars of raw data...")
    
    # Use the primary text model
    model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")
    
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        print(">>> [RESEARCH SYNTHESIZER] Error: GOOGLE_GEMINI_API_KEY is not configured in .env")
        return False
        
    try:
        client = genai.Client(api_key=api_key)
        
        # Combine system prompt + user prompt directly (simple schema)
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        response = client.models.generate_content(
            model=model_name,
            contents=combined_prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}]
            )
        )
        synthesized_md = response.text
    except Exception as e:
        print(f">>> [RESEARCH SYNTHESIZER] Failed to call Gemini API: {e}")
        return False

    if not synthesized_md:
        print(">>> [RESEARCH SYNTHESIZER] Error: LLM returned empty synthesized brief.")
        return False

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(synthesized_md)

    print(f">>> [RESEARCH SYNTHESIZER] Deep Research Brief saved securely to {output_file} ({len(synthesized_md)} chars)")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthesize raw, noisy social media data into a clean research brief.")
    parser.add_argument("--topic", required=True, help="The primary topic being researched.")
    parser.add_argument("--source", default=".tmp/source_content.md", help="Path to raw input file.")
    parser.add_argument("--output", default=".tmp/synthesized_research.md", help="Path to clean output file.")
    
    args = parser.parse_args()
    success = synthesize_research(args.topic, source_file=args.source, output_file=args.output)
    if not success:
        sys.exit(1)
