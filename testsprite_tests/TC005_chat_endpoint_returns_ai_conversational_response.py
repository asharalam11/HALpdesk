import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30

def test_chat_endpoint_returns_ai_conversational_response():
    session_id = None
    try:
        # Create a new session to use in chat
        create_session_payload = {"pid": 1234, "cwd": "/tmp"}
        create_resp = requests.post(
            f"{BASE_URL}/session/create",
            json=create_session_payload,
            timeout=TIMEOUT
        )
        assert create_resp.status_code == 200, f"Session create failed with status {create_resp.status_code}"
        create_data = create_resp.json()
        assert "session_id" in create_data and create_data.get("status") == "success"
        session_id = create_data["session_id"]

        # Send a chat message to the /chat endpoint
        chat_payload = {"session_id": session_id, "message": "Hello, AI assistant!"}
        chat_resp = requests.post(
            f"{BASE_URL}/chat",
            json=chat_payload,
            timeout=TIMEOUT
        )
        assert chat_resp.status_code == 200, f"Chat request failed with status {chat_resp.status_code}"
        chat_data = chat_resp.json()
        assert chat_data.get("status") == "success", f"Unexpected status in chat response: {chat_data.get('status')}"
        assert "response" in chat_data and isinstance(chat_data["response"], str) and len(chat_data["response"]) > 0

    finally:
        # Clean up: delete the created session if applicable (assuming endpoint for delete session exists)
        if session_id:
            try:
                requests.delete(f"{BASE_URL}/session/{session_id}", timeout=TIMEOUT)
            except Exception:
                pass

test_chat_endpoint_returns_ai_conversational_response()