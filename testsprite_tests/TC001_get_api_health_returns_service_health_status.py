import requests

BASE_URL = "http://localhost:9999"
TIMEOUT = 30


def test_get_api_health_returns_service_health_status():
    url = f"{BASE_URL}/api/health"
    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"Request to {url} failed: {e}"

    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    try:
        json_data = response.json()
    except ValueError:
        assert False, f"Response is not valid JSON: {response.text}"

    # Validate required fields
    assert "status" in json_data, "Response JSON missing 'status' field"
    assert isinstance(json_data["status"], str), "'status' field is not a string"

    assert "checks" in json_data, "Response JSON missing 'checks' field"
    assert isinstance(json_data["checks"], dict), "'checks' field is not an object/dict"


# Run the test

test_get_api_health_returns_service_health_status()
