import requests

def test_post_api_generate_triggers_synchronous_content_generation():
    base_url = "http://localhost:9999"
    endpoint = "/api/generate"
    url = base_url + endpoint

    # Valid GenerateRequest payload matching PRD specification
    payload = {
        "type": "post",
        "purpose": "professional",
        "visual_aspect": "image",
        "aspect_ratio": "16:9",
        "context": "Technology trends in 2026",
        "tone": "informative"
    }

    # Replace with a valid token for Authorization header
    token = "your_valid_bearer_token_here"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    # Validate status code
    assert response.status_code == 200, f"Expected status code 200 but got {response.status_code}"

    # Validate response content-type
    content_type = response.headers.get("Content-Type", "")
    assert "application/json" in content_type, f"Expected JSON response but got {content_type}"

    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate required fields in response JSON
    required_fields = ["caption", "single_point", "image_prompt", "asset_url"]
    for field in required_fields:
        assert field in data, f"Response JSON missing required field: {field}"
        assert isinstance(data[field], str), f"Field {field} should be a string"


test_post_api_generate_triggers_synchronous_content_generation()
