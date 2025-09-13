#!/usr/bin/env python3
"""Basic test script for HALpdesk"""
import requests
import time

def test_daemon():
    """Test basic daemon functionality"""
    print("🧪 Testing HALpdesk daemon...")
    
    base_url = "http://127.0.0.1:8080"
    
    # Test health check
    print("1. Testing health endpoint...")
    response = requests.get(f"{base_url}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    print("   ✅ Health check passed")
    
    # Test session creation
    print("2. Testing session creation...")
    response = requests.post(f"{base_url}/session/create", json={
        "pid": 12345,
        "cwd": "/tmp"
    })
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    print(f"   ✅ Session created: {session_id}")
    
    # Test session listing
    print("3. Testing session listing...")
    response = requests.get(f"{base_url}/session/list")
    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert len(sessions) == 1
    print(f"   ✅ Found {len(sessions)} session(s)")
    
    # Test get session
    print("4. Testing get session...")
    response = requests.get(f"{base_url}/session/{session_id}")
    assert response.status_code == 200
    session_data = response.json()["session"]
    assert session_data["session_id"] == session_id
    assert session_data["cwd"] == "/tmp"
    print("   ✅ Session data retrieved")
    
    # Test mode switching
    print("5. Testing mode switching...")
    response = requests.post(f"{base_url}/session/mode", json={
        "session_id": session_id,
        "mode": "chat"
    })
    assert response.status_code == 200
    print("   ✅ Mode switched to chat")
    
    # Test command suggestion (will fail without AI provider, but should return error gracefully)
    print("6. Testing command suggestion...")
    response = requests.post(f"{base_url}/command/suggest", json={
        "session_id": session_id,
        "query": "list files"
    })
    # This might fail due to no AI provider, but shouldn't crash
    print(f"   📝 Command suggestion status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   📝 Suggested command: {data.get('command', 'N/A')}")
    
    # Test session deletion
    print("7. Testing session deletion...")
    response = requests.delete(f"{base_url}/session/{session_id}")
    assert response.status_code == 200
    print("   ✅ Session deleted")
    
    print("\n🎉 All basic tests passed!")

if __name__ == "__main__":
    test_daemon()