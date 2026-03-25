from google.genai import types
import inspect

print("ToolConfig attributes:")
for x in dir(types.ToolConfig):
    if not x.startswith("_"):
        print(x)
