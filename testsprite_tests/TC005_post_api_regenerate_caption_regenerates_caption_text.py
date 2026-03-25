import requests

BASE_URL = "http://localhost:9999"
AUTH_TOKEN = "your_valid_token_here"  # Replace with a valid token

def test_post_api_regenerate_caption_regenerates_caption_text():
    url = f"{BASE_URL}/api/regenerate-caption"
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    # Fixed payload keys to camelCase to match expected RegenerateCaptionRequest
    payload = {
        "postContext": "Existing post text or context for regeneration",
        "styleInstructions": "Make it more engaging and professional"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
    try:
        resp_json = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    assert "caption" in resp_json, "Response JSON missing 'caption' key"
    assert isinstance(resp_json["caption"], str), "'caption' should be a string"
    assert len(resp_json["caption"].strip()) > 0, "'caption' should not be empty"

test_post_api_regenerate_caption_regenerates_caption_text()
