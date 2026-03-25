import requests
import json

data = {
    "source": "topic",
    "topic": "AI coding agents like Cursor and Claude Code",
    "purpose": "educational",
    "type": "text",
    "style": "minimal",
    "visual_aspect": "none",
    "auto_topic": False
}

try:
    with requests.post("http://localhost:9999/api/generate-stream", json=data, stream=True) as r:
        for line in r.iter_lines():
            if line:
                line = line.decode('utf-8', errors='replace')
                print(line.encode('ascii', errors='replace').decode('ascii'))
                if line.startswith("data: "):
                    try:
                        parsed = json.loads(line[6:])
                        if "lead_magnets" in parsed:
                            print("\n\nFOUND LEAD MAGNETS:", json.dumps(parsed["lead_magnets"], indent=2))
                    except:
                        pass
except Exception as e:
    print("Error:", e)
