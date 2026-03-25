import requests
import json
import sys

url = "http://localhost:9999/api/generate-stream"
headers = {"Content-Type": "application/json"}
payload = {
    "topic": "",
    "style": "minimal",
    "aspect_ratio": "16:9",
    "uid": "test_user_id",
    "auto_topic": True
}

try:
    print("Sending request to server with auto_topic=True...")
    with requests.post(url, headers=headers, json=payload, stream=True) as response:
        for line in response.iter_lines(decode_unicode=True):
            if line:
                print(line)
except Exception as e:
    print("Error:", e)
