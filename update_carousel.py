import re

with open("execution/generate_carousel.py", "r", encoding="utf-8") as f:
    content = f.read()

# Modify call_llm
content = re.sub(
    r'def call_llm\(system_prompt, user_content, json_output=True, allow_tavily=False\):',
    r'def call_llm(system_prompt, user_content, json_output=True, allow_tavily=False, include_lead_magnet=False):',
    content
)

# Update tavily logic in call_llm
content = re.sub(
    r'        if allow_tavily:',
    r'        if allow_tavily and include_lead_magnet:',
    content
)

# Update generate_caption definition
content = re.sub(
    r'def generate_caption\(topic, purpose, carousel_plan, slides_content, user_context_sections=None\):',
    r'def generate_caption(topic, purpose, carousel_plan, slides_content, user_context_sections=None, include_lead_magnet=False):',
    content
)

# Update lead magnet prompt insertion
lm_prompt = """
    if include_lead_magnet:
        system_prompt += "\n\n## LEAD MAGNET HUNTER & ENGAGEMENT BAIT\n"
        system_prompt += "You have access to a `tavily_search` tool. Decide if the carousel topic warrants a lead magnet. If it does, use the tool to search the web for the latest, most relevant tools, GitHub repos, or resources related to the topic. You may call the search tool multiple times if needed.\n"
        system_prompt += "If you find a great resource, organically integrate an 'Engagement Bait' Call-To-Action at the end of the caption (e.g., 'Comment [KEYWORD] and I will DM you the link to the [Resource]'). The keyword should be punchy and relevant."
"""

content = re.sub(
    r'    system_prompt \+= "\n\n## LEAD MAGNET HUNTER & ENGAGEMENT BAIT\n".*?punchy and relevant\."',
    lm_prompt,
    content,
    flags=re.DOTALL
)

# Update call_llm inside generate_caption
content = re.sub(
    r'caption = call_llm\(system_prompt, user_content, json_output=False, allow_tavily=True\)',
    r'caption = call_llm(system_prompt, user_content, json_output=False, allow_tavily=True, include_lead_magnet=include_lead_magnet)',
    content
)

# Update generate_carousel definition
content = re.sub(
    r'def generate_carousel\(topic, purpose, user_id="default"\):',
    r'def generate_carousel(topic, purpose, user_id="default", include_lead_magnet=False):',
    content
)

# Update generate_caption call inside generate_carousel
content = re.sub(
    r'caption = generate_caption\(topic, purpose, carousel_plan, slides_content, user_context_sections=user_context_sections\)',
    r'caption = generate_caption(topic, purpose, carousel_plan, slides_content, user_context_sections=user_context_sections, include_lead_magnet=include_lead_magnet)',
    content
)

# Update argparse
argparse_block = """    parser.add_argument("--user_id", type=str, default="default", help="User ID for context")
    parser.add_argument("--include_lead_magnet", action="store_true", help="Allow LLM to search web for lead magnets.")
"""
content = re.sub(
    r'    parser\.add_argument\("--user_id", type=str, default="default", help="User ID for context"\)',
    argparse_block,
    content
)

# Update generate_carousel call in main
content = re.sub(
    r'generate_carousel\(args\.topic, args\.purpose, user_id=args\.user_id\)',
    r'generate_carousel(args.topic, args.purpose, user_id=args.user_id, include_lead_magnet=args.include_lead_magnet)',
    content
)

with open("execution/generate_carousel.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Done updating execution/generate_carousel.py")
