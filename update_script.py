import re

with open("execution/generate_text_post.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add include_lead_magnet to generate_text_post
content = re.sub(
    r'def generate_text_post\(post_type, purpose, topic, source="topic", style="minimal", source_content=None, visual_aspect="none", visual_context_path=None, custom_topic=None, user_id="default", raw_notes=None\):',
    r'def generate_text_post(post_type, purpose, topic, source="topic", style="minimal", source_content=None, visual_aspect="none", visual_context_path=None, custom_topic=None, user_id="default", raw_notes=None, include_lead_magnet=False):',
    content
)

# 2. Add include_lead_magnet to the generate_text_post call in main
content = re.sub(
    r'user_id=args.user_id,\n\s*raw_notes=_raw_notes\n\s*\)',
    r'user_id=args.user_id,\n        raw_notes=_raw_notes,\n        include_lead_magnet=args.include_lead_magnet\n    )',
    content
)

# 3. Modify system blocks condition
system_blocks_replacement = """    system_blocks = [
        "## FACT CHECKING & GROUNDING\n"
        "You MUST use the built-in Google Search tool to verify all product names, AI model versions (e.g., 'Gemini 3.5' vs 'Gemini 1.5'), release dates, and technical capabilities before writing the post.\n"
        "If you mention a tool or version, verify it exists. Do NOT hallucinate versions or features. If a claim from the provided context (e.g., Tavily or Jina) seems incorrect or refers to non-existent models, search the web to correct it before drafting.\n\n"
    ]
    
    if include_lead_magnet:
        system_blocks.append(
            "## LEAD MAGNET HUNTER & ENGAGEMENT BAIT\n"
            "You have access to a `tavily_search` tool. Decide if the topic warrants a lead magnet. If it does, use the tool to search the web for the latest, most relevant tools, GitHub repos, or resources related to the topic. You may call the search tool multiple times if needed.\n"
            "If you find a great resource, DO NOT hardcode a generic CTA. Instead, you MUST use the `get_cta_library` tool (likely looking for a lead magnet category) to find a high-converting template, and integrate the resource organically. Be sure to output the lead magnets you found in the `lead_magnets` JSON array."
        )"""

content = re.sub(
    r'    system_blocks = \[\n        "## FACT CHECKING & GROUNDING\n".*?JSON array\."\n    \]',
    system_blocks_replacement,
    content,
    flags=re.DOTALL
)

# 4. Create dynamic tool declarations
dynamic_tools_func = """def get_tool_declarations(include_lead_magnet=False):
    funcs = [
        types.FunctionDeclaration(
            name="get_hook_library",
            description="Load the full hook templates from a specific hook category.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "filename": {"type": "STRING", "enum": _HOOK_LIBRARY_FILES}
                },
                "required": ["filename"],
            },
        ),
        types.FunctionDeclaration(
            name="get_cta_library",
            description="Load the full CTA templates from a specific CTA category.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "filename": {"type": "STRING", "enum": _CTA_LIBRARY_FILES}
                },
                "required": ["filename"],
            },
        ),
        types.FunctionDeclaration(
            name="get_user_persona",
            description="Fetch the active user's professional bio, core skills, tone of voice, and writing rules.",
        ),
        types.FunctionDeclaration(
            name="get_user_brand",
            description="Fetch the active user's brand identity, products, colors, and tagline.",
        ),
        types.FunctionDeclaration(
            name="get_user_voice_samples",
            description="Fetch real examples of the user's past writing related to a topic.",
            parameters={"type": "OBJECT", "properties": {"topic": {"type": "STRING", "description": "Topic to search for"}}, "required": ["topic"]},
        ),
        types.FunctionDeclaration(
            name="get_brand_knowledge",
            description="Fetch technical product specs, case studies, or deeper knowledge related to a topic.",
            parameters={"type": "OBJECT", "properties": {"topic": {"type": "STRING", "description": "Topic to search for"}}, "required": ["topic"]},
        ),
    ]
    
    if include_lead_magnet:
        funcs.append(
            types.FunctionDeclaration(
                name="tavily_search",
                description="Search the web for tools, latest resources, and GitHub repos. Use this to find lead magnets.",
                parameters={"type": "OBJECT", "properties": {"query": {"type": "STRING", "description": "Search query"}}, "required": ["query"]},
            )
        )
        
    return types.Tool(function_declarations=funcs)
"""

# Replace the static _LIBRARY_TOOL_DECLARATIONS with the function
content = re.sub(
    r'# Build tool declarations for Gemini function calling\n_LIBRARY_TOOL_DECLARATIONS = types\.Tool\(.*?\]\n\)',
    dynamic_tools_func,
    content,
    flags=re.DOTALL
)

# 5. Update call_llm tool parameter
content = re.sub(
    r'tools=\[_LIBRARY_TOOL_DECLARATIONS\]',
    r'tools=[get_tool_declarations(include_lead_magnet)]',
    content
)

with open("execution/generate_text_post.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Done updating execution/generate_text_post.py")
