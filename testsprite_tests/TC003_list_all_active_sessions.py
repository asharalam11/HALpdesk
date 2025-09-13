import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30

def test_list_all_active_sessions():
    url = f"{BASE_URL}/session/list"
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"Request to list sessions failed: {e}"

    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    assert "sessions" in data, "Response JSON missing 'sessions' key"
    assert isinstance(data["sessions"], list), "'sessions' should be a list"

test_list_all_active_sessions()