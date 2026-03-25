import requests

def test_get_api_health_models_returns_model_configuration_diagnostics():
    base_url = "http://localhost:9999"
    url = f"{base_url}/api/health/models"
    timeout = 30

    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException as e:
        assert False, f"HTTP request to {url} failed: {e}"

    assert response.status_code == 200, f"Expected status code 200 but got {response.status_code}"
    try:
        json_data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate required fields presence and types
    assert isinstance(json_data, dict), "Response JSON is not an object"
    assert "text_model" in json_data and isinstance(json_data["text_model"], str), "'text_model' missing or not a string"
    assert "image_model" in json_data and (isinstance(json_data["image_model"], str) or json_data["image_model"] is None), "'image_model' missing or not a string/null"
    assert "env_flags" in json_data and isinstance(json_data["env_flags"], dict), "'env_flags' missing or not an object"

    # Additional checks: text_model and image_model should be non-empty strings or null for image_model
    assert json_data["text_model"].strip() != "", "'text_model' is an empty string"
    # image_model can be null or non-empty string, check if string then must not be empty
    if json_data["image_model"] is not None:
        assert json_data["image_model"].strip() != "", "'image_model' is an empty string"

    # env_flags contents are unspecified, just ensure it's a dict

test_get_api_health_models_returns_model_configuration_diagnostics()