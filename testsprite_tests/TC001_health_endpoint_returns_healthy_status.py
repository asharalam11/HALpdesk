import requests

def test_health_endpoint_returns_healthy_status():
    base_url = "http://localhost:8080"
    url = f"{base_url}/health"
    headers = {
        "Accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"Request to {url} failed: {e}"

    try:
        json_resp = response.json()
    except ValueError:
        assert False, "Response is not a valid JSON"

    assert "status" in json_resp, "Response JSON does not contain 'status' field"
    assert json_resp["status"] == "healthy", f"Expected status 'healthy', got '{json_resp['status']}'"

test_health_endpoint_returns_healthy_status()