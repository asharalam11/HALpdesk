"""AI provider integration for HALpdesk"""
import os
import json
import requests
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import subprocess
import time
import urllib.parse
import shutil
from ..config import provider_settings
import logging

logger = logging.getLogger(__name__)

class AIProvider(ABC):
    @abstractmethod
    def get_command_suggestion(self, query: str, context: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def chat(self, message: str, context: Dict[str, Any]) -> str:
        pass

class OllamaProvider(AIProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "codellama:7b"):
        self.base_url = base_url.rstrip('/')
        self.model = model

    def _tags(self) -> list[str]:
        try:
            url = f"{self.base_url}/api/tags"
            t0 = time.perf_counter()
            logger.info("[provider/ollama] → GET %s", url)
            r = requests.get(url, timeout=5)
            dt = (time.perf_counter() - t0) * 1000
            logger.info("[provider/ollama] ← %s %sms", r.status_code, int(dt))
            r.raise_for_status()
            data = r.json() or {}
            models = data.get("models", [])
            names = []
            for m in models:
                name = m.get("name") or m.get("model")
                if name:
                    names.append(name)
            return names
        except Exception:
            return []

    def _pull_model(self, model: str) -> bool:
        try:
            url = f"{self.base_url}/api/pull"
            payload = {"model": model, "stream": False}
            logger.info("[provider/ollama] → POST %s model=%s (pull)", url, model)
            t0 = time.perf_counter()
            r = requests.post(url, json=payload, timeout=600)
            dt = (time.perf_counter() - t0) * 1000
            logger.info("[provider/ollama] ← %s %sms (pull)", r.status_code, int(dt))
            return r.status_code == 200
        except Exception:
            return False

    def _ensure_model(self) -> None:
        if self.model in self._tags():
            return
        # Attempt to pull configured model name
        self._pull_model(self.model)

    def _make_request(self, prompt: str) -> str:
        try:
            # Ensure model exists before generation; if not present, try to pull
            self._ensure_model()

            url = f"{self.base_url}/api/generate"
            payload = {"model": self.model, "prompt": prompt, "stream": False}
            logger.info(
                "[provider/ollama] → POST %s model=%s prompt_len=%s",
                url,
                self.model,
                len(prompt),
            )
            t0 = time.perf_counter()
            response = requests.post(url, json=payload, timeout=60)
            dt = (time.perf_counter() - t0) * 1000
            logger.info("[provider/ollama] ← %s %sms", response.status_code, int(dt))
            if response.status_code == 404:
                # Likely missing model, try pull then retry once
                self._ensure_model()
                logger.info("[provider/ollama] ↻ retry generate after pull")
                t0 = time.perf_counter()
                response = requests.post(url, json=payload, timeout=60)
                dt = (time.perf_counter() - t0) * 1000
                logger.info("[provider/ollama] ← %s %sms (retry)", response.status_code, int(dt))
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            installed = ", ".join(self._tags())
            msg = str(e)
            if "404" in msg or "Not Found" in msg:
                hint = f"Ollama model '{self.model}' not found. Installed: [{installed}]"
                return f"{hint}"
            return f"Error connecting to Ollama: {msg}"
    
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
        # Extract and clean the command
        lines = response.strip().split('\n')
        command = lines[0].strip() if lines else "echo 'No command generated'"
        
        # Clean up common formatting issues
        command = command.strip('`"\'')  # Remove backticks and quotes
        command = command.replace('```bash', '').replace('```', '')  # Remove code blocks
        command = command.strip()
        
        return command if command else "echo 'No command generated'"
    
    def chat(self, message: str, context: Dict[str, Any]) -> str:
        prompt = f"""You are a helpful assistant. Answer the user's question clearly and concisely.

User: {message}

Response:"""
        return self._make_request(prompt)

class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo", base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
    
    def _make_request(self, messages: list) -> str:
        try:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 150,
                "temperature": 0.1,
            }
            logger.info(
                "[provider/openai] → POST %s model=%s messages=%s",
                url,
                self.model,
                len(messages),
            )
            t0 = time.perf_counter()
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            dt = (time.perf_counter() - t0) * 1000
            logger.info("[provider/openai] ← %s %sms", response.status_code, int(dt))
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
        # Extract and clean the command
        lines = response.strip().split('\n')
        command = lines[0].strip() if lines else "echo 'No command generated'"
        
        # Clean up common formatting issues
        command = command.strip('`"\'')  # Remove backticks and quotes
        command = command.replace('```bash', '').replace('```', '')  # Remove code blocks
        command = command.strip()
        
        return command if command else "echo 'No command generated'"
    
    def chat(self, message: str, context: Dict[str, Any]) -> str:
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Answer questions clearly and concisely."},
            {"role": "user", "content": message}
        ]
        return self._make_request(messages)

class AIProviderFactory:
    @staticmethod
    def create_provider() -> AIProvider:
        cfg = provider_settings()
        default = (cfg.get("default") or "").lower()

        # Candidate builders based on availability
        def build_openai() -> Optional[AIProvider]:
            key = cfg["openai"].get("api_key") or os.getenv("OPENAI_API_KEY")
            if not key:
                return None
            model = cfg["openai"].get("model") or "gpt-3.5-turbo"
            base = cfg["openai"].get("base_url") or "https://api.openai.com/v1"
            return OpenAIProvider(key, model=model, base_url=base)

        def build_claude() -> Optional[AIProvider]:
            key = cfg["claude"].get("api_key") or os.getenv("ANTHROPIC_API_KEY")
            if not key:
                return None
            model = cfg["claude"].get("model") or "claude-3-haiku-20240307"
            base = cfg["claude"].get("base_url") or "https://api.anthropic.com"
            return ClaudeProvider(key, model=model, base_url=base)

        def _ollama_hostport_from_base(base: str) -> str:
            # Convert http://host:port to host:port for OLLAMA_HOST
            try:
                u = urllib.parse.urlparse(base)
                if u.scheme in ("http", "https") and u.hostname and u.port:
                    return f"{u.hostname}:{u.port}"
            except Exception:
                pass
            # Fallback: assume already host:port
            return base.replace("http://", "").replace("https://", "")

        def _is_ollama_up(base: str, timeout: float = 0.5) -> bool:
            url = base.rstrip("/") + "/api/version"
            try:
                r = requests.get(url, timeout=timeout)
                return r.ok
            except Exception:
                return False

        def _is_local(base: str) -> bool:
            try:
                u = urllib.parse.urlparse(base)
                host = u.hostname or ""
                return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
            except Exception:
                return True

        def _try_start_ollama(base: str, binary: str | None) -> None:
            # If already up, nothing to do
            if _is_ollama_up(base):
                return
            if not _is_local(base):
                return  # Do not attempt to start remote endpoints
            if str(os.environ.get("HALPDESK_OLLAMA_AUTOSTART", "1")).lower() in {"0", "false", "no"}:
                return
            bin_path = binary or shutil.which("ollama")
            if not bin_path:
                return  # Not installed; skip
            env = os.environ.copy()
            env.setdefault("OLLAMA_HOST", _ollama_hostport_from_base(base))
            try:
                subprocess.Popen(
                    [bin_path, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    env=env,
                )
                logger.info("Starting Ollama server via '%s serve' on %s", bin_path, env.get("OLLAMA_HOST"))
            except Exception:
                return
            # Poll for readiness up to ~8s
            for _ in range(16):
                if _is_ollama_up(base, timeout=0.5):
                    logger.info("Ollama server is up at %s", base)
                    break
                time.sleep(0.5)

        def _normalize_http_base(base: str) -> str:
            if base.startswith("http://") or base.startswith("https://"):
                return base
            return f"http://{base}"

        def build_ollama() -> Optional[AIProvider]:
            base = cfg["ollama"].get("base_url") or os.getenv("HALPDESK_OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST") or "http://localhost:11434"
            base = _normalize_http_base(base)
            model = cfg["ollama"].get("model") or "llama2"
            binary = cfg["ollama"].get("binary")
            # Attempt to auto-start the Ollama server if not reachable
            _try_start_ollama(base, binary)
            return OllamaProvider(base_url=base, model=model)

        # If explicitly configured, honor it
        if default == "openai":
            return build_openai() or build_ollama()
        if default == "claude":
            return build_claude() or build_ollama()
        if default == "ollama":
            return build_ollama()

        # Auto: OpenAI > Claude > Ollama default
        return build_openai() or build_claude() or build_ollama()
    
    @staticmethod
    def create_ollama(model: str = "codellama:7b") -> OllamaProvider:
        return OllamaProvider(model=model)
    
    @staticmethod
    def create_openai(api_key: str, model: str = "gpt-3.5-turbo") -> OpenAIProvider:
        return OpenAIProvider(api_key, model)


class ClaudeProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307", base_url: str = "https://api.anthropic.com"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _make_request(self, system: str, user: str) -> str:
        try:
            # Anthropics messages API
            url = f"{self.base_url}/v1/messages"
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": self.model,
                "max_tokens": 256,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            logger.info(
                "[provider/claude] → POST %s model=%s system_len=%s user_len=%s",
                url,
                self.model,
                len(system),
                len(user),
            )
            t0 = time.perf_counter()
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            dt = (time.perf_counter() - t0) * 1000
            logger.info("[provider/claude] ← %s %sms", resp.status_code, int(dt))
            resp.raise_for_status()
            data = resp.json()
            # Extract text content
            parts = data.get("content", [])
            for p in parts:
                if p.get("type") == "text" and p.get("text"):
                    return p["text"].strip()
            return ""
        except Exception as e:
            return f"Error connecting to Claude: {str(e)}"

    def get_command_suggestion(self, query: str, context: Dict[str, Any]) -> str:
        cwd = context.get("cwd", ".")
        system = "You are a terminal assistant. Convert user requests into bash commands. Respond with ONLY the command, no explanations."
        user = f"Request: {query}\nCurrent directory: {cwd}\nCommand:"
        response = self._make_request(system, user)
        return response.strip().split("\n")[0].strip() if response else "echo 'No command generated'"

    def chat(self, message: str, context: Dict[str, Any]) -> str:
        system = "You are a helpful assistant. Answer questions clearly and concisely."
        return self._make_request(system, message)
