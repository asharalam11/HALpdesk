import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30

def test_diagnostics_endpoint_returns_provider_connectivity_and_sessions_info():
    url = f"{BASE_URL}/diagnostics"
    headers = {
        "Accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"Request to /diagnostics failed: {e}"
    
    data = response.json()
    
    # Validate top-level keys
    assert isinstance(data, dict), "Response should be a JSON object"
    assert "provider" in data, "Response missing 'provider' key"
    assert "connectivity" in data, "Response missing 'connectivity' key"
    assert "sessions" in data, "Response missing 'sessions' key"
    
    # Validate provider info is a dict/object
    assert isinstance(data["provider"], dict), "'provider' should be an object"
    # Validate connectivity info is a dict/object
    assert isinstance(data["connectivity"], dict), "'connectivity' should be an object"
    # Validate sessions info is a dict/object
    assert isinstance(data["sessions"], dict), "'sessions' should be an object"

    # Optionally perform further checks depending on expected structure
    # Here just ensure they are not empty
    assert len(data["provider"]) > 0, "'provider' object should not be empty"
    assert len(data["connectivity"]) > 0, "'connectivity' object should not be empty"
    assert len(data["sessions"]) > 0, "'sessions' object should not be empty"


test_diagnostics_endpoint_returns_provider_connectivity_and_sessions_info()