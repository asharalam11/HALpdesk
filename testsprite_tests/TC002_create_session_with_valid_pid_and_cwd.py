import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30

def test_create_session_with_valid_pid_and_cwd():
    url = f"{BASE_URL}/session/create"
    headers = {"Content-Type": "application/json"}
    payload = {
        "pid": 1234,
        "cwd": "/home/user"
    }

    response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    try:
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    json_response = response.json()
    assert "session_id" in json_response, "Response missing session_id"
    assert isinstance(json_response["session_id"], str), "session_id should be a string"
    assert json_response.get("status") == "success", "Status is not 'success'"

test_create_session_with_valid_pid_and_cwd()