import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

custom_tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="dummy",
            description="Dummy function",
            parameters={
                "type": "OBJECT",
                "properties": {"x": {"type": "STRING"}}
            }
        )
    ]
)

try:
    response = client.models.generate_content(
        model="gemini-3.1-pro-preview",
        contents="What is the latest Gemini version?",
        config=types.GenerateContentConfig(
            tools=[custom_tool, types.Tool(google_search=types.GoogleSearch())],
            tool_config={"function_calling_config": {"mode": "AUTO"}, "include_server_side_tool_invocations": True}
        )
    )
    print("Success")
except Exception as e:
    print(f"Error: {e}")
