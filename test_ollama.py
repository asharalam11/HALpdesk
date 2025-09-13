#!/usr/bin/env python3
"""Test Ollama connection directly"""
import requests
from halpdesk.daemon.ai_provider import OllamaProvider

def test_ollama_direct():
    """Test direct Ollama connection"""
    print("🔗 Testing Ollama connection...")
    
    # Test 1: Direct requests call
    print("1. Testing direct requests call...")
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "codellama:7b",
                "prompt": "Convert this to bash: list files",
                "stream": False
            },
            timeout=30
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data.get('response', 'No response')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    print()
    
    # Test 2: Our OllamaProvider class
    print("2. Testing OllamaProvider class...")
    try:
        provider = OllamaProvider()
        print(f"   Model: {provider.model}")
        response = provider.get_command_suggestion("list files", {"cwd": "/tmp"})
        print(f"   Command suggestion: {response}")
    except Exception as e:
        print(f"   Exception: {e}")

if __name__ == "__main__":
    test_ollama_direct()