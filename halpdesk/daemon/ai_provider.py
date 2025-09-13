"""AI provider integration for HALpdesk"""
import os
import json
import requests
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

class AIProvider(ABC):
    @abstractmethod
    def get_command_suggestion(self, query: str, context: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def chat(self, message: str, context: Dict[str, Any]) -> str:
        pass

class OllamaProvider(AIProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2"):
        self.base_url = base_url
        self.model = model
    
    def _make_request(self, prompt: str) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            return f"Error connecting to Ollama: {str(e)}"
    
    def get_command_suggestion(self, query: str, context: Dict[str, Any]) -> str:
        cwd = context.get('cwd', '.')
        prompt = f"""You are a helpful terminal assistant. Convert the user's request into a bash command.

User request: {query}
Current directory: {cwd}

Respond with ONLY the bash command, no explanations or extra text.

Examples:
User: "list files" → ls -la
User: "show disk usage" → df -h
User: "find python files" → find . -name "*.py"

Command:"""
        
        response = self._make_request(prompt)
        # Extract just the command part if there's extra text
        lines = response.strip().split('\n')
        return lines[0].strip() if lines else "echo 'No command generated'"
    
    def chat(self, message: str, context: Dict[str, Any]) -> str:
        prompt = f"""You are a helpful assistant. Answer the user's question clearly and concisely.

User: {message}

Response:"""
        return self._make_request(prompt)

class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"
    
    def _make_request(self, messages: list) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 150,
                    "temperature": 0.1
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"Error connecting to OpenAI: {str(e)}"
    
    def get_command_suggestion(self, query: str, context: Dict[str, Any]) -> str:
        cwd = context.get('cwd', '.')
        messages = [
            {"role": "system", "content": "You are a terminal assistant. Convert user requests into bash commands. Respond with ONLY the command, no explanations."},
            {"role": "user", "content": f"Request: {query}\nCurrent directory: {cwd}\nCommand:"}
        ]
        response = self._make_request(messages)
        # Extract just the command part
        lines = response.strip().split('\n')
        return lines[0].strip() if lines else "echo 'No command generated'"
    
    def chat(self, message: str, context: Dict[str, Any]) -> str:
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Answer questions clearly and concisely."},
            {"role": "user", "content": message}
        ]
        return self._make_request(messages)

class AIProviderFactory:
    @staticmethod
    def create_provider() -> AIProvider:
        # Check for OpenAI API key first
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            return OpenAIProvider(openai_key)
        
        # Fall back to Ollama
        return OllamaProvider()
    
    @staticmethod
    def create_ollama(model: str = "llama2") -> OllamaProvider:
        return OllamaProvider(model=model)
    
    @staticmethod
    def create_openai(api_key: str, model: str = "gpt-3.5-turbo") -> OpenAIProvider:
        return OpenAIProvider(api_key, model)