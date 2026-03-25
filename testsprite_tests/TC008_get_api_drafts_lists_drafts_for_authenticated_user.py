import requests

BASE_URL = "http://localhost:9999"
API_PATH = "/api/drafts"
TIMEOUT = 30

# Provide a valid token with access to the drafts API
AUTH_TOKEN = "Bearer YOUR_VALID_AUTH_TOKEN"

def test_get_api_drafts_lists_drafts_authenticated_user():
    headers = {
        "Authorization": AUTH_TOKEN,
        "Accept": "application/json"
    }
    try:
        response = requests.get(f"{BASE_URL}{API_PATH}", headers=headers, timeout=TIMEOUT)
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        json_data = response.json()
        assert isinstance(json_data, dict), "Response JSON is not a dictionary"
        assert "drafts" in json_data, "'drafts' key not in response JSON"
        assert isinstance(json_data["drafts"], list), "'drafts' is not a list"
        # Optionally verify draft fields if drafts exist
        for draft in json_data["drafts"]:
            assert isinstance(draft, dict), "Draft item is not a dictionary"
            # Common fields expected in a draft object (per PRD)
            for field in ["id", "title", "status"]:
                assert field in draft, f"Field '{field}' missing in draft"
    except requests.exceptions.RequestException as e:
        assert False, f"Request to {API_PATH} failed: {e}"
    except ValueError:
        assert False, "Response is not valid JSON"

test_get_api_drafts_lists_drafts_authenticated_user()