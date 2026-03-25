import requests

BASE_URL = "http://localhost:9999"
API_PATH = "/api/drafts"
TIMEOUT = 30

# Replace this with a valid token for authentication
AUTH_TOKEN = "Bearer YOUR_VALID_AUTH_TOKEN"

def test_post_api_drafts_creates_and_saves_new_draft():
    url = BASE_URL + API_PATH
    headers = {
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Include required fields: title, status, content
    payload = {
        "title": "Test Draft Title",
        "status": "draft",
        "content": "Sample draft content"
    }

    draft_id = None
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        assert response.status_code == 200, f"Expected status 200, got {response.status_code}"
        data = response.json()
        assert "message" in data and isinstance(data["message"], str), "Response missing 'message' or invalid type"
        assert data["message"].lower() == "saved", f"Unexpected message: {data['message']}"
        assert "draft" in data and isinstance(data["draft"], dict), "Response missing 'draft' object"
        draft = data["draft"]
        assert "id" in draft and isinstance(draft["id"], str) and draft["id"], "Draft 'id' missing or empty"
        assert "title" in draft and draft["title"] == payload["title"], "Draft 'title' mismatch or missing"
        assert "status" in draft and draft["status"] == payload["status"], "Draft 'status' mismatch or missing"
        draft_id = draft["id"]
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"


test_post_api_drafts_creates_and_saves_new_draft()
