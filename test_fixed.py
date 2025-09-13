#!/usr/bin/env python3
"""Test fixed command cleaning"""
import requests

def test_cleaned_commands():
    """Test that commands are properly cleaned"""
    base_url = "http://127.0.0.1:8080"
    
    # Create session
    response = requests.post(f"{base_url}/session/create", json={
        "pid": 12345,
        "cwd": "/tmp"
    })
    session_id = response.json()["session_id"]
    
    # Test command suggestions that might have formatting issues
    test_queries = [
        "list all files in this repo",
        "show disk usage", 
        "find python files"
    ]
    
    print("🧪 Testing cleaned command suggestions:")
    for query in test_queries:
        response = requests.post(f"{base_url}/command/suggest", json={
            "session_id": session_id,
            "query": query
        })
        
        if response.status_code == 200:
            data = response.json()
            command = data["command"]
            safety = data["safety_level"]
            print(f"Query: '{query}'")
            print(f"Command: '{command}' {safety}")
            
            # Check for problematic characters
            if '`' in command:
                print("  ❌ Still has backticks!")
            elif command.startswith('```') or '```' in command:
                print("  ❌ Still has code blocks!")
            else:
                print("  ✅ Clean command")
            print()
        else:
            print(f"Error: {response.status_code}")
    
    # Clean up
    requests.delete(f"{base_url}/session/{session_id}")

if __name__ == "__main__":
    test_cleaned_commands()