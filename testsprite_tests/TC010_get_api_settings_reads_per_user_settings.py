import requests

BASE_URL = "http://localhost:9999"
API_PATH = "/api/settings"
TIMEOUT = 30

# Insert a valid token here for the test (replace with actual token)
AUTH_TOKEN = "your_valid_authorization_token_here"


def test_get_api_settings_reads_per_user_settings():
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Accept": "application/json",
    }

    try:
        response = requests.get(f"{BASE_URL}{API_PATH}", headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"HTTP request failed: {e}"

    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"

    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON."

    # Validate that key user settings objects are present
    expected_keys = ["professional_bio", "writing_style_rules", "brand_id", "publishing_config"]
    for key in expected_keys:
        assert key in data, f"Response JSON missing expected key: '{key}'"

    # Additional optional: check types (basic)
    assert isinstance(data["professional_bio"], (str, type(None))), "'professional_bio' should be string or null"
    assert isinstance(data["writing_style_rules"], (str, type(None))), "'writing_style_rules' should be string or null"
    assert isinstance(data["brand_id"], (str, type(None))), "'brand_id' should be string or null"
    assert isinstance(data["publishing_config"], (dict, type(None))), "'publishing_config' should be dict or null"


test_get_api_settings_reads_per_user_settings()