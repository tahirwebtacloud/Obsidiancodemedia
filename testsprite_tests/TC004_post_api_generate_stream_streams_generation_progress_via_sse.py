import requests
import itertools
import json

BASE_URL = "http://localhost:9999"
GENERATE_STREAM_ENDPOINT = "/api/generate-stream"
TIMEOUT = 30

# Placeholder: Replace with a valid token for testing
AUTH_TOKEN = "your_valid_bearer_token_here"

def test_post_api_generate_stream_sse():
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json"
    }

    # Corrected valid GenerateRequest body as per PRD expectations
    generate_request_payload = {
        "routing_config": {
            "type": "post",
            "purpose": "linkedin",
            "visual_aspect": "image",
            "aspect_ratio": "16:9"
        },
        "prompt": "Generate a LinkedIn post about AI innovation in 2026"
    }

    url = BASE_URL + GENERATE_STREAM_ENDPOINT

    try:
        with requests.post(
            url,
            headers=headers,
            json=generate_request_payload,
            timeout=TIMEOUT,
            stream=True,
        ) as response:
            # Check HTTP status code
            assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"

            # Check Content-Type header for SSE
            content_type = response.headers.get("Content-Type", "")
            assert (
                "text/event-stream" in content_type
            ), f"Expected Content-Type to include 'text/event-stream', got '{content_type}'"

            # Collect event types received to verify stages and result
            received_events = []

            # SSE lines come chunked; usually: "event: <event_name>\ndata: <json or text>\n\n"
            def parse_sse_event(lines):
                event = None
                data = None
                for line in lines:
                    if line.startswith("event:"):
                        event = line[len("event:"):].strip()
                    elif line.startswith("data:"):
                        data = line[len("data:"):].strip()
                return event, data

            lines_buffer = []
            # Use iterator over lines stripped of trailing newlines
            line_iter = (line.decode("utf-8").strip() for line in response.iter_lines())

            for line in line_iter:
                if line == "":
                    # End of event block
                    event, data = parse_sse_event(lines_buffer)
                    lines_buffer = []
                    if event:
                        received_events.append((event, data))

                        # For 'stage' events, data should be JSON with 'stage' key whose value is string
                        if event == "stage":
                            try:
                                stage_obj = json.loads(data)
                                assert (
                                    "stage" in stage_obj and isinstance(stage_obj["stage"], str)
                                ), f"Invalid stage event data: {data}"
                            except Exception as e:
                                raise AssertionError(f"Failed to parse stage event data JSON: {e}")

                        # For result event, data is JSON with expected keys
                        if event == "result":
                            try:
                                result_obj = json.loads(data)
                                # Validate expected keys exist with string values
                                expected_keys = ["caption", "single_point", "image_prompt", "asset_url"]
                                for key in expected_keys:
                                    assert (
                                        key in result_obj and isinstance(result_obj[key], str)
                                    ), f"Missing or invalid key '{key}' in result event: {data}"
                            except Exception as e:
                                raise AssertionError(f"Failed to parse result event data JSON: {e}")
                    
                    # Check after receiving 'result' event to stop reading
                    if event == "result":
                        break

                else:
                    lines_buffer.append(line)

            # Assert that at least these stage events are received in order, as given in PRD example:
            required_stage_sequence = [
                "text_start",
                "text_done",
                "image_start",
                "image_done",
            ]

            # Extract just stage values in order received
            stages_received = [json.loads(data)["stage"] for (ev, data) in received_events if ev == "stage"]

            # Check that required stages appear in order in stages_received
            # They may be interleaved with other events, so check subsequence
            it = iter(stages_received)
            for required_stage in required_stage_sequence:
                assert any(s == required_stage for s in it), f"Missing stage event '{required_stage}' in order"

            # Check that a 'result' event was received
            result_events = [ev for ev, _ in received_events if ev == "result"]
            assert result_events, "No 'result' event received in SSE stream"

    except requests.exceptions.RequestException as e:
        raise AssertionError(f"Request failed: {e}")

test_post_api_generate_stream_sse()
