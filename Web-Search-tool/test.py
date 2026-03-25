import sys
from web_search import search_web
import json

def run():
    print("Running search...", flush=True)
    try:
        res = search_web('AI 2026', max_results=3, deep=True)
        if res.get('success'):
            llm_content = ""
            for idx, r in enumerate(res['results']):
                llm_content += f"Result {idx+1}:\n"
                llm_content += f"Title: {r.get('title', '')}\n"
                llm_content += f"URL: {r.get('url', '')}\n"
                llm_content += f"Snippet: {r.get('snippet', '')}\n"
                llm_content += f"Content:\n{r.get('markdown', '')}\n\n"
            print("--- RESULT STR ---")
            print(llm_content)
            print("--- RESULT END ---")
            print(f"Total String Chars: {len(llm_content)}")
            print(f"Total JSON Chars: {len(json.dumps(res))}")
        else:
            print("Search failed:")
            print(res)
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    run()
