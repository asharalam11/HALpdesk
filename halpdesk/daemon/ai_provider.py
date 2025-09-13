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
import threading
import signal
import sys

logger = logging.getLogger(__name__)

# Track an autostarted Ollama process so we can shut it down on daemon exit
AUTOSTARTED_OLLAMA_PROC: Optional[subprocess.Popen] = None
_OLLAMA_PULLING: set[str] = set()
_OLLAMA_PULL_LOCK = threading.Lock()

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

    def _pull_model_background(self, model: str) -> None:
        def worker():
            try:
                ok = self._pull_model(model)
                logger.info("[provider/ollama] background pull complete ok=%s model=%s", ok, model)
            finally:
                with _OLLAMA_PULL_LOCK:
                    _OLLAMA_PULLING.discard(model)

        with _OLLAMA_PULL_LOCK:
            if model in _OLLAMA_PULLING:
                return
            _OLLAMA_PULLING.add(model)
        t = threading.Thread(target=worker, name=f"ollama-pull-{model}", daemon=True)
        t.start()

    def _ensure_model(self) -> bool:
        """Ensure model is present.

        Returns True if model appears available; otherwise starts a background
        pull (if not already running) and returns False.
        """
        if self.model in self._tags():
            return True
        # Start background pull and report not-ready
        self._pull_model_background(self.model)
        return False

    def _make_request(self, prompt: str) -> str:
        try:
            # Ensure model exists. If not, start background pull and return a hint
            if not self._ensure_model():
                return (
                    f"Downloading Ollama model '{self.model}' in background. "
                    f"Try again shortly or run 'ollama pull {self.model}'."
                )

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
                # Likely missing model; ensure background pull is running and return instructional text
                self._pull_model_background(self.model)
                logger.info("[provider/ollama] model missing; started background pull")
                return (
                    f"Downloading Ollama model '{self.model}' in background. "
                    f"Try again shortly or run 'ollama pull {self.model}'."
                )
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
        os_info = context.get('os', 'unknown OS')
        prompt = (
            'You are HAL Exec Planner. Output one JSON object and nothing else.\n'
            'If enough info: {"action":"command","command":"<one-line POSIX-sh command>"}.\n'
            'If missing info: {"action":"ask","question":"<one short clarifying question>"}.\n'
            'Rules: one line only (no newlines, code fences, or backticks). Use $(...) not backticks. '
            'Quote paths. Use "$PWD" or "$HOME", not "~". OS-specific: use only tools/flags supported on this OS. '
            'On macOS/BSD do NOT use GNU-only options such as find -printf, sed -r, du --block-size, grep -P.\n'
            f'Task: {query}\nCWD: {cwd}\nOS: {os_info}\n'
        )
        response = self._make_request(prompt)
        return response.strip()
    
    def chat(self, message: str, context: Dict[str, Any]) -> str:
        prompt = f"""You are a helpful assistant. Answer the user's question clearly and concisely.

User: {message}

Response:"""
        return self._make_request(prompt)

class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", base_url: str = "https://generativelanguage.googleapis.com"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
    
    def _make_request(self, messages: list) -> str:
        try:
            # Convert messages to Gemini format
            contents = []
            for msg in messages:
                if msg["role"] == "system":
                    # Gemini doesn't have system role, prepend to user message
                    continue
                elif msg["role"] == "user":
                    # Combine system message if present
                    system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
                    content = f"{system_msg}\n\n{msg['content']}" if system_msg else msg["content"]
                    contents.append({"parts": [{"text": content}]})
                elif msg["role"] == "assistant":
                    contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
            
            url = f"{self.base_url}/v1beta/models/{self.model}:generateContent"
            headers = {
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 150,
                    "candidateCount": 1,
                }
            }
            logger.info(
                "[provider/gemini] → POST %s model=%s messages=%s",
                url,
                self.model,
                len(messages),
            )
            t0 = time.perf_counter()
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            dt = (time.perf_counter() - t0) * 1000
            logger.info("[provider/gemini] ← %s %sms", response.status_code, int(dt))
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except requests.exceptions.HTTPError as e:
            # Handle specific HTTP errors more clearly
            if response.status_code == 429:
                return f"Gemini rate limit exceeded: {str(e)}"
            elif response.status_code == 401:
                return f"Gemini authentication failed: Invalid API key"
            elif response.status_code == 403:
                return f"Gemini access denied: Check API key permissions"
            else:
                return f"Gemini HTTP error: {str(e)}"
        except Exception as e:
            return f"Error connecting to Gemini: {str(e)}"
    
    def get_command_suggestion(self, query: str, context: Dict[str, Any]) -> str:
        cwd = context.get('cwd', '.')
        os_info = context.get('os', 'unknown OS')
        prompt = f"""
You are a terminal assistant that outputs structured JSON decisions.
You are running on {os_info} in directory {cwd}.

If enough information is provided, reply with EXACTLY:
{{"action":"command","command":"<bash command>"}}

If you need more details to produce a safe command, reply with EXACTLY:
{{"action":"ask","question":"<one short clarifying question>"}}

No explanations or text outside the JSON object.

User request: {query}
"""
        messages = [
            {
                "role": "system",
                "content": (f"{prompt}"),
            },
            {"role": "user", "content": f"Request: {query}\nCurrent directory: {cwd}\nOperating system: {os_info}"},
        ]
        response = self._make_request(messages)
        return response.strip()
    
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
        def build_gemini() -> Optional[AIProvider]:
            key = cfg.get("gemini", {}).get("api_key") or os.getenv("GEMINI_API_KEY")
            if not key:
                return None
            model = cfg.get("gemini", {}).get("model") or "gemini-1.5-flash"
            base = cfg.get("gemini", {}).get("base_url") or "https://generativelanguage.googleapis.com"
            return GeminiProvider(key, model=model, base_url=base)

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
                logger.info("[provider/ollama] already running at %s", base)
                return
            if not _is_local(base):
                logger.info("[provider/ollama] skip autostart: non-local base %s", base)
                return  # Do not attempt to start remote endpoints
            if str(os.environ.get("HALPDESK_OLLAMA_AUTOSTART", "1")).lower() in {"0", "false", "no"}:
                logger.info("[provider/ollama] autostart disabled by env")
                return
            bin_path = binary or shutil.which("ollama")
            if not bin_path:
                logger.warning("[provider/ollama] 'ollama' binary not found; cannot autostart")
                return  # Not installed; skip
            env = os.environ.copy()
            env.setdefault("OLLAMA_HOST", _ollama_hostport_from_base(base))
            global AUTOSTARTED_OLLAMA_PROC
            try:
                AUTOSTARTED_OLLAMA_PROC = subprocess.Popen(
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
            # Read from config file, use reasonable defaults if not configured
            base = cfg["ollama"].get("base_url") or "http://localhost:11434"
            base = _normalize_http_base(base)
            model = cfg["ollama"].get("model")
            if not model:
                raise RuntimeError(
                    "No Ollama model specified in config. "
                    "Please set 'providers.ollama.model' in ~/.config/halpdesk/config.toml "
                    "or use the example config from examples/config.toml"
                )
            binary = cfg["ollama"].get("binary")
            
            # Attempt to auto-start the Ollama server if not reachable
            _try_start_ollama(base, binary)
            
            # Create provider instance to check model availability
            provider = OllamaProvider(base_url=base, model=model)
            
            # Check if Ollama server is reachable and get available models
            try:
                available_models = provider._tags()
            except Exception as e:
                error_msg = (
                    f"Cannot connect to Ollama server at {base}. "
                    f"Make sure Ollama is running. Error: {e}"
                )
                logger.error("[provider/ollama] %s", error_msg)
                raise RuntimeError(error_msg)
            
            # Check if the configured model exists
            if model not in available_models:
                available_str = ", ".join(available_models) if available_models else "none"
                error_msg = (
                    f"FATAL: Ollama model '{model}' not found. "
                    f"Available models: [{available_str}]. "
                    f"Install with: ollama pull {model}"
                )
                logger.error("[provider/ollama] %s", error_msg)
                raise RuntimeError(error_msg)
                
            logger.info("[provider/ollama] Model '%s' is available ✓", model)
            return provider

        # If explicitly configured, honor it
        def _raise_provider_error(name: str, reason: str) -> None:
            msg = (
                f"Provider '{name}' selected in config but is not available: {reason}. "
                "Update ~/.config/halpdesk/config.toml or set the required env vars."
            )
            logger.error("[provider/select] %s", msg)
            raise RuntimeError(msg)

        if default == "gemini":
            prov = build_gemini()
            if prov is None:
                _raise_provider_error(
                    "gemini",
                    "missing GEMINI_API_KEY or invalid gemini configuration",
                )
        elif default == "claude":
            prov = build_claude()
            if prov is None:
                _raise_provider_error(
                    "claude",
                    "missing ANTHROPIC_API_KEY or invalid claude configuration",
                )
        elif default == "ollama":
            prov = build_ollama()
            # No strict precondition here; the daemon can autostart and pull models later.
        else:
            # Auto: Gemini > Claude > Ollama default
            prov = build_gemini() or build_claude() or build_ollama()

        # Log selection
        try:
            name = prov.__class__.__name__  # type: ignore[attr-defined]
            model = getattr(prov, "model", None)
            base = getattr(prov, "base_url", None)
            logger.info("[provider/select] %s model=%s base=%s", name, model, base)
        except Exception:
            pass
        return prov


def stop_autostarted_ollama(timeout: float = 3.0) -> None:
    """Terminate an autostarted Ollama server if we launched it.

    Sends SIGTERM to the process group on POSIX or terminate() on Windows.
    Safe to call multiple times.
    """
    global AUTOSTARTED_OLLAMA_PROC
    proc = AUTOSTARTED_OLLAMA_PROC
    if not proc:
        return
    if proc.poll() is not None:
        AUTOSTARTED_OLLAMA_PROC = None
        return
    try:
        logger.info("[shutdown] stopping autostarted Ollama (pid=%s)", proc.pid)
        if os.name == "posix":
            try:
                os.killpg(proc.pid, signal.SIGTERM)  # type: ignore[arg-type]
            except Exception:
                proc.terminate()
        else:
            proc.terminate()
        # Wait a bit, then force kill if still alive
        t0 = time.time()
        while (time.time() - t0) < timeout and proc.poll() is None:
            time.sleep(0.1)
        if proc.poll() is None:
            logger.warning("[shutdown] forcing kill of Ollama (pid=%s)", proc.pid)
            if os.name == "posix":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)  # type: ignore[arg-type]
                except Exception:
                    proc.kill()
            else:
                proc.kill()
    finally:
        AUTOSTARTED_OLLAMA_PROC = None
    
    @staticmethod
    def create_ollama(model: str = "codellama:7b") -> OllamaProvider:
        return OllamaProvider(model=model)
    
    @staticmethod
    def create_gemini(api_key: str, model: str = "gemini-1.5-flash") -> GeminiProvider:
        return GeminiProvider(api_key, model)


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
        os_info = context.get('os', 'unknown OS')
        system = (
            'You are a terminal assistant that outputs structured JSON decisions.\n'
            'If enough information: {"action":"command","command":"<bash>"}.\n'
            'If ambiguous: {"action":"ask","question":"<short question>"}.\n'
            'No extra text outside JSON.'
        )
        user = f"Request: {query}\nCurrent directory: {cwd}\nOperating system: {os_info}"
        response = self._make_request(system, user)
        return response.strip()

    def chat(self, message: str, context: Dict[str, Any]) -> str:
        system = "You are a helpful assistant. Answer questions clearly and concisely."
        return self._make_request(system, message)
