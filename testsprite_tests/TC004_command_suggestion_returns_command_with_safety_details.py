import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30


def test_command_suggestion_returns_command_with_safety_details():
    session_id = None
    try:
        # Create a new session to use for the command suggest endpoint
        create_session_resp = requests.post(
            f"{BASE_URL}/session/create",
            json={"pid": 1234, "cwd": "/tmp"},
            timeout=TIMEOUT,
        )
        assert create_session_resp.status_code == 200, f"Unexpected status code: {create_session_resp.status_code}"
        create_session_json = create_session_resp.json()
        assert "session_id" in create_session_json, "session_id not in response"
        assert create_session_json.get("status") == "success", "Session creation status not success"
        session_id = create_session_json["session_id"]

        # Use the session_id to request a command suggestion
        query = "List all files in the current directory"
        command_suggest_resp = requests.post(
            f"{BASE_URL}/command/suggest",
            json={"session_id": session_id, "query": query},
            timeout=TIMEOUT,
        )
        assert command_suggest_resp.status_code == 200, f"Unexpected status code: {command_suggest_resp.status_code}"
        resp_json = command_suggest_resp.json()

        # Validate response includes required fields
        assert "command" in resp_json and isinstance(resp_json["command"], str) and resp_json["command"].strip() != "", "Missing or empty command"
        assert "safety_level" in resp_json and isinstance(resp_json["safety_level"], str) and resp_json["safety_level"].strip() != "", "Missing or empty safety_level"
        assert "safety_reason" in resp_json and isinstance(resp_json["safety_reason"], str), "Missing safety_reason"
        assert resp_json.get("status") == "success", "Status is not 'success'"

    finally:
        if session_id:
            # Delete the session if API supported deletion, but no delete endpoint is specified in PRD.
            # So no deletion step is done here.
            pass


test_command_suggestion_returns_command_with_safety_details()