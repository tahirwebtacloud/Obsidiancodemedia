import requests

BASE_URL = "http://localhost:9999"
API_PATH = "/api/research/viral"
TIMEOUT = 30

# Placeholder for a valid bearer token, replace it with a proper token before running the test
AUTH_TOKEN = "your_valid_bearer_token_here"

def test_post_api_research_viral_runs_viral_content_research_workflow():
    url = BASE_URL + API_PATH
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    # Minimal valid ResearchRequest body based on typical research request data
    payload = {
        "query": "latest viral linkedin posts",
        "limit": 5,
        "filters": {
            "platform": "linkedin",
            "date_range": {"start": "2026-01-01", "end": "2026-03-01"}
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request to {url} failed with exception: {e}"

    assert response.status_code == 200, f"Expected status 200 but got {response.status_code}"

    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate that essential keys exist in the response JSON based on ResearchResult expected structure
    # Should contain ranked viral posts, metadata, and parsed hooks
    assert isinstance(data, dict), "Response JSON root is not an object"
    assert "ranked_posts" in data, "Response missing 'ranked_posts'"
    assert isinstance(data["ranked_posts"], list), "'ranked_posts' is not a list"
    assert "metadata" in data, "Response missing 'metadata'"
    assert isinstance(data["metadata"], dict), "'metadata' is not an object"
    assert "parsed_hooks" in data, "Response missing 'parsed_hooks'"
    assert isinstance(data["parsed_hooks"], list), "'parsed_hooks' is not a list"

    # Optionally check that ranked_posts list has at least one item (if expected)
    assert len(data["ranked_posts"]) > 0, "'ranked_posts' list is empty"
    # Optional: items in ranked_posts have expected fields
    post = data["ranked_posts"][0]
    assert isinstance(post, dict), "Each item in 'ranked_posts' should be an object"
    assert "post_id" in post or "id" in post, "Viral post missing identifier"

test_post_api_research_viral_runs_viral_content_research_workflow()