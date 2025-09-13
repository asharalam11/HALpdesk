"""Configuration loader for HALpdesk.

Reads `~/.config/halpdesk/config.toml` if present, with environment overrides.

Supported keys:

  [server]
  # Preferred: unified endpoint. Examples: "http://127.0.0.1:8080", "tcp://127.0.0.1:8080"
  endpoint = "http://127.0.0.1:8080"
  # Or separately:
  host = "127.0.0.1"
  port = 8080

  [client]
  daemon_url = "http://127.0.0.1:8080"

Env overrides:
  HALPDESK_DAEMON_ENDPOINT, HALPDESK_DAEMON_HOST, HALPDESK_DAEMON_PORT, HALPDESK_DAEMON_URL
  HALPDESK_PROVIDER, HALPDESK_OPENAI_BASE_URL, HALPDESK_OPENAI_MODEL
  HALPDESK_CLAUDE_BASE_URL, HALPDESK_CLAUDE_MODEL
  HALPDESK_OLLAMA_BASE_URL or OLLAMA_HOST, HALPDESK_OLLAMA_MODEL
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple


# Try Python 3.11+ stdlib first; fallback to tomli on older Python.
try:  # pragma: no cover - import path depends on runtime
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None  # type: ignore


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "halpdesk" / "config.toml"


def _read_toml(path: Path) -> Dict[str, Any]:
    if tomllib is None or not path.exists():
        return {}
    text = path.read_text()
    try:
        data = tomllib.loads(text)
        assert isinstance(data, dict)
        return data
    except Exception:
        return {}


def load() -> Dict[str, Any]:
    path = Path(os.environ.get("HALPDESK_CONFIG", DEFAULT_CONFIG_PATH))
    return _read_toml(path)


def _parse_endpoint(ep: str) -> Tuple[str, int]:
    ep = ep.strip()
    if ep.startswith("http://"):
        ep = ep[len("http://") :]
    if ep.startswith("https://"):
        # We still bind plain TCP even if https is provided in config.
        ep = ep[len("https://") :]
    if ep.startswith("tcp://"):
        ep = ep[len("tcp://") :]
    # Now expect host:port
    if ":" in ep:
        host, port_s = ep.rsplit(":", 1)
        try:
            return host or "127.0.0.1", int(port_s)
        except ValueError:
            return "127.0.0.1", 8080
    return ep or "127.0.0.1", 8080


def server_bind(default_host: str = "127.0.0.1", default_port: int = 8080) -> tuple[str, int]:
    cfg = load()
    env_endpoint = os.environ.get("HALPDESK_DAEMON_ENDPOINT")
    if env_endpoint:
        return _parse_endpoint(env_endpoint)

    server_cfg = cfg.get("server", {}) if isinstance(cfg, dict) else {}
    if isinstance(server_cfg, dict):
        if "endpoint" in server_cfg and server_cfg["endpoint"]:
            return _parse_endpoint(str(server_cfg["endpoint"]))
        host = str(server_cfg.get("host", default_host))
        try:
            port = int(server_cfg.get("port", default_port))
        except Exception:
            port = default_port
        # Allow env vars to tweak individually
        host = os.environ.get("HALPDESK_DAEMON_HOST", host)
        port_env = os.environ.get("HALPDESK_DAEMON_PORT")
        if port_env:
            try:
                port = int(port_env)
            except ValueError:
                pass
        return host, port

    # Fall back to defaults
    host = os.environ.get("HALPDESK_DAEMON_HOST", default_host)
    port_env = os.environ.get("HALPDESK_DAEMON_PORT")
    port = int(port_env) if (port_env and port_env.isdigit()) else default_port
    return host, port


def client_daemon_url(default_url: str = "http://127.0.0.1:8080") -> str:
    # Highest priority: explicit env var
    env_url = os.environ.get("HALPDESK_DAEMON_URL")
    if env_url:
        return env_url

    cfg = load()
    client_cfg = cfg.get("client", {}) if isinstance(cfg, dict) else {}
    if isinstance(client_cfg, dict) and client_cfg.get("daemon_url"):
        return str(client_cfg["daemon_url"]).strip()

    # Fallback to server bind
    host, port = server_bind()
    return f"http://{host}:{port}"


def provider_settings() -> Dict[str, Any]:
    """Return a normalized provider configuration dictionary.

    Structure:
      {
        "default": "openai"|"claude"|"ollama"|None,
        "openai": {"base_url": str|None, "model": str|None, "api_key": str|None},
        "claude": {"base_url": str|None, "model": str|None, "api_key": str|None},
        "ollama": {"base_url": str|None, "model": str|None},
      }
    """
    cfg = load()
    prov = (cfg.get("providers") if isinstance(cfg, dict) else {}) or {}

    result: Dict[str, Any] = {
        "default": None,
        "openai": {"base_url": None, "model": None, "api_key": None},
        "claude": {"base_url": None, "model": None, "api_key": None},
        "ollama": {"base_url": None, "model": None, "binary": None},
    }

    # Default provider selection
    default_from_cfg = None
    if isinstance(prov, dict):
        default_from_cfg = prov.get("default")
        # Nested provider configs
        for name in ("openai", "claude", "ollama"):
            sub = prov.get(name, {}) if isinstance(prov.get(name), dict) else {}
            # Ollama doesn't use api_key; allow optional 'binary'
            keys = ("base_url", "model", "api_key", "binary")
            for key in keys:
                if key in sub:
                    if name == "ollama" and key == "api_key":
                        continue
                    result[name][key] = sub[key]

    # Environment overrides
    result["default"] = os.environ.get("HALPDESK_PROVIDER", default_from_cfg)

    # OpenAI
    if os.environ.get("HALPDESK_OPENAI_BASE_URL"):
        result["openai"]["base_url"] = os.environ["HALPDESK_OPENAI_BASE_URL"]
    if os.environ.get("HALPDESK_OPENAI_MODEL"):
        result["openai"]["model"] = os.environ["HALPDESK_OPENAI_MODEL"]
    if os.environ.get("OPENAI_API_KEY"):
        result["openai"]["api_key"] = os.environ["OPENAI_API_KEY"]

    # Claude / Anthropic
    if os.environ.get("HALPDESK_CLAUDE_BASE_URL"):
        result["claude"]["base_url"] = os.environ["HALPDESK_CLAUDE_BASE_URL"]
    if os.environ.get("HALPDESK_CLAUDE_MODEL"):
        result["claude"]["model"] = os.environ["HALPDESK_CLAUDE_MODEL"]
    if os.environ.get("ANTHROPIC_API_KEY"):
        result["claude"]["api_key"] = os.environ["ANTHROPIC_API_KEY"]

    # Ollama
    ollama_base = os.environ.get("HALPDESK_OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST")
    if ollama_base:
        result["ollama"]["base_url"] = ollama_base
    if os.environ.get("HALPDESK_OLLAMA_MODEL"):
        result["ollama"]["model"] = os.environ["HALPDESK_OLLAMA_MODEL"]
    if os.environ.get("HALPDESK_OLLAMA_BIN"):
        result["ollama"]["binary"] = os.environ["HALPDESK_OLLAMA_BIN"]

    return result
