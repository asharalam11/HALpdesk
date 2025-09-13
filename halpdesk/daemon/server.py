"""HALpdesk daemon server"""
import os
import time
import logging
import uvicorn
import platform
from fastapi import FastAPI, HTTPException, Request
import requests
from pydantic import BaseModel
from typing import Dict, List, Optional
import json as _json
import re
import sys as _sys

from .session import SessionManager, SessionMode
from .ai_provider import AIProviderFactory, OllamaProvider, GeminiProvider, ClaudeProvider, stop_autostarted_ollama
from .safety import CommandSafetyChecker
from ..config import (
    server_bind,
    provider_settings,
    config_path,
    sanitized_file_config,
    sanitized_provider_settings,
    client_daemon_url,
)

app = FastAPI(title="HALpdesk Daemon", version="0.1.0")
session_manager = SessionManager()
ai_provider = AIProviderFactory.create_provider()
safety_checker = CommandSafetyChecker(ai_provider)
logger = logging.getLogger("halpdesk.daemon")

# Gather basic system information for provider context
OS_INFO = f"{platform.system()} {platform.release()} ({platform.machine()})"

# Basic request/response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    path = request.url.path
    method = request.method
    clen = request.headers.get("content-length")
    logger.info("[http] → %s %s content-length=%s", method, path, clen)
    try:
        response = await call_next(request)
    except Exception:
        dt = (time.perf_counter() - t0) * 1000
        logger.exception("[http] ← exception after %sms %s %s", int(dt), method, path)
        raise
    dt = (time.perf_counter() - t0) * 1000
    logger.info("[http] ← %s %s %s %sms", response.status_code, method, path, int(dt))
    return response


def _ensure_logger():
    """Attach a stream handler so our logs always show under uvicorn.

    Uvicorn config may not emit non-uvicorn loggers by default. We attach a
    handler to the halpdesk logger if none exist.
    """
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


@app.on_event("startup")
async def _on_startup():
    _ensure_logger()
    # Log provider summary again once logging is configured
    name = ai_provider.__class__.__name__
    model = getattr(ai_provider, "model", None)
    base = getattr(ai_provider, "base_url", None)
    logger.info("[startup] provider=%s model=%s base=%s", name, model, base)
    # Log config path and selected provider settings
    cfgp = config_path()
    logger.info("[startup] config path=%s exists=%s", cfgp, cfgp.exists())
    try:
        ps = provider_settings()
        logger.info(
            "[startup] provider_settings default=%s openai.model=%s claude.model=%s ollama.model=%s",
            ps.get("default"),
            ps.get("openai", {}).get("model"),
            ps.get("claude", {}).get("model"),
            ps.get("ollama", {}).get("model"),
        )
        # Log sanitized file config and effective config
        try:
            import json as _json
            cfg_dump = _json.dumps(sanitized_file_config(), separators=(",",":"))
            logger.info("[startup] file_config=%s", cfg_dump)
            eff = {
                "server": {
                    "bind": {
                        "host": server_bind()[0],
                        "port": server_bind()[1],
                    },
                    "client_url": client_daemon_url(),
                },
                "providers": sanitized_provider_settings(),
            }
            eff_dump = _json.dumps(eff, separators=(",",":"))
            logger.info("[startup] effective_config=%s", eff_dump)
        except Exception:
            pass
    except Exception:
        pass

# Request/Response models
class CreateSessionRequest(BaseModel):
    pid: int
    cwd: str

class SessionResponse(BaseModel):
    session_id: str
    status: str = "success"

class QueryRequest(BaseModel):
    session_id: str
    query: str

class CommandResponse(BaseModel):
    command: str
    safety_level: str
    safety_reason: str
    status: str = "success"

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    response: str
    status: str = "success"

class ModeRequest(BaseModel):
    session_id: str
    mode: str

class AttachRequest(BaseModel):
    session_id: str
    client_pid: int

class DetachRequest(BaseModel):
    session_id: str
    client_pid: int

class LeaveRequest(BaseModel):
    session_id: str
    client_pid: int

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/session/create", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    logger.info("[api/session/create] pid=%s cwd=%s", request.pid, request.cwd)
    session_id = session_manager.create_session(request.pid, request.cwd)
    logger.info("[api/session/create] created session_id=%s", session_id)
    return SessionResponse(session_id=session_id)

@app.get("/session/list")
async def list_sessions():
    sessions = session_manager.list_sessions()
    logger.info("[api/session/list] count=%s", len(sessions))
    return {"sessions": sessions}

@app.get("/session/{session_id}")
async def get_session(session_id: str):
    logger.info("[api/session/get] session_id=%s", session_id)
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session.to_dict()}

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    logger.info("[api/session/delete] session_id=%s", session_id)
    success = session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}

@app.post("/session/mode", response_model=SessionResponse)
async def switch_mode(request: ModeRequest):
    try:
        mode = SessionMode(request.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'exec' or 'chat'")
    logger.info("[api/session/mode] session_id=%s mode=%s", request.session_id, request.mode)
    success = session_manager.switch_mode(request.session_id, mode)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    logger.info("[api/session/mode] switched session_id=%s", request.session_id)
    return SessionResponse(session_id=request.session_id)

@app.post("/session/attach")
async def attach_session(request: AttachRequest):
    logger.info("[api/session/attach] session_id=%s client_pid=%s", request.session_id, request.client_pid)
    count = session_manager.attach(request.session_id, request.client_pid)
    if count < 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "attached", "attached": count}

@app.post("/session/detach")
async def detach_session(request: DetachRequest):
    logger.info("[api/session/detach] session_id=%s client_pid=%s", request.session_id, request.client_pid)
    result = session_manager.detach(request.session_id, request.client_pid)
    if not result["found"]:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "detached", "closed": False}

@app.post("/session/leave")
async def leave_session(request: LeaveRequest):
    logger.info("[api/session/leave] session_id=%s client_pid=%s", request.session_id, request.client_pid)
    result = session_manager.leave(request.session_id, request.client_pid)
    if not result["found"]:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "closed" if result["closed"] else "left", "closed": result["closed"]}

@app.post("/command/suggest")
async def suggest_command(request: QueryRequest):
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get command suggestion from AI, include OS info
    context = {"cwd": session.cwd, "history": session.history, "os": OS_INFO}
    prov_name = ai_provider.__class__.__name__
    model = getattr(ai_provider, "model", None)
    logger.info("[api/suggest] → provider=%s model=%s query_len=%s", prov_name, model, len(request.query))
    t0 = time.perf_counter()
    raw = ai_provider.get_command_suggestion(request.query, context)
    dt = (time.perf_counter() - t0) * 1000
    logger.info("[api/suggest] ← %sms", int(dt))
    
    # Attempt to parse an action decision from provider output
    def _parse_decision(text: str) -> Dict[str, Optional[str]]:
        text = (text or "").strip()
        # Strip common code fences like ```json ... ``` or ``` ... ```
        if text.startswith("```"):
            # remove leading ```lang (optional)
            text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
            # remove trailing ```
            text = re.sub(r"\s*```$", "", text)
        try:
            obj = _json.loads(text)
            if isinstance(obj, dict) and "action" in obj:
                return {
                    "action": str(obj.get("action", "")).lower(),
                    "command": obj.get("command"),
                    "question": obj.get("question"),
                    "reason": obj.get("reason"),
                }
        except Exception:
            pass
        # Find first JSON object anywhere in the text (even if code fences remain)
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                obj = _json.loads(m.group(0))
                if isinstance(obj, dict) and "action" in obj:
                    return {
                        "action": str(obj.get("action", "")).lower(),
                        "command": obj.get("command"),
                        "question": obj.get("question"),
                        "reason": obj.get("reason"),
                    }
            except Exception:
                pass
        if text.lower().startswith("ask:"):
            return {"action": "ask", "question": text.partition(":")[2].strip(), "command": None, "reason": None}
        return {"action": "command", "command": text, "question": None, "reason": None}

    decision = _parse_decision(raw)
    action = decision.get("action")
    if action == "ask":
        q = decision.get("question") or "Could you provide more details?"
        session.add_to_history({"type": "clarify_request", "question": q})
        return {"status": "need_more_info", "question": q}
    if action == "refuse":
        reason = decision.get("reason") or "Cannot proceed with the request."
        session.add_to_history({"type": "refuse", "reason": reason})
        raise HTTPException(status_code=400, detail=reason)

    command = decision.get("command") or "echo 'No command generated'"

    # Validate formatting and OS compatibility before proceeding
    def _balanced_quotes_and_parens(s: str) -> bool:
        in_s = False
        in_d = False
        esc = False
        paren = 0
        for ch in s:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if not in_d and ch == "'":
                in_s = not in_s
                continue
            if not in_s and ch == '"':
                in_d = not in_d
                continue
            if not in_s and not in_d:
                if ch == "(":
                    paren += 1
                elif ch == ")":
                    paren -= 1
                    if paren < 0:
                        return False
        return (not in_s) and (not in_d) and paren == 0

    # One-line and fence checks
    if "\n" in command or "\r" in command or "```" in command:
        msg = (
            "Reformat: Return one JSON object only with action=command and a single-line command. "
            "Do not include code fences, backticks, or newlines."
        )
        session.add_to_history({"type": "clarify_request", "question": msg})
        return {"status": "need_more_info", "question": msg}

    # Balanced quotes/parens
    if not _balanced_quotes_and_parens(command):
        msg = "Reformat: The command has unbalanced quotes or parentheses. Return a corrected one-line command."
        session.add_to_history({"type": "clarify_request", "question": msg})
        return {"status": "need_more_info", "question": msg}

    # macOS GNU-only guardrails
    if _sys.platform == "darwin":
        forbidden_patterns = [r"find\s+[^\n]*-printf", r"\bsed\s+[^\n]*-r\b", r"\bdu\s+[^\n]*--", r"\bgrep\s+[^\n]*-P\b"]
        for pat in forbidden_patterns:
            if re.search(pat, command):
                msg = (
                    "Reformat: This macOS system does not support GNU-only options (e.g., find -printf, sed -r, du --, grep -P). "
                    "Return a POSIX/macOS-compatible one-line command."
                )
                session.add_to_history({"type": "clarify_request", "question": msg})
                return {"status": "need_more_info", "question": msg}
    # Check safety
    safety_level, safety_reason = safety_checker.check_command(command)
    # Record final suggestion
    session.add_to_history({
        "type": "command_suggestion",
        "query": request.query,
        "assistant_decision": decision,
        "command": command,
        "safety_level": safety_level,
    })
    return {
        "status": "success",
        "command": command,
        "safety_level": safety_level,
        "safety_reason": safety_reason,
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get chat response from AI
    context = {"cwd": session.cwd, "history": session.history, "os": OS_INFO}
    prov_name = ai_provider.__class__.__name__
    model = getattr(ai_provider, "model", None)
    logger.info("[api/chat] → provider=%s model=%s message_len=%s", prov_name, model, len(request.message))
    t0 = time.perf_counter()
    response = ai_provider.chat(request.message, context)
    dt = (time.perf_counter() - t0) * 1000
    logger.info("[api/chat] ← %sms", int(dt))
    
    # Add to session history
    session.add_to_history({
        "type": "chat",
        "message": request.message,
        "response": response
    })
    
    return ChatResponse(response=response)

@app.post("/cleanup")
async def cleanup_sessions():
    cleaned = session_manager.cleanup_stale_sessions()
    return {"cleaned_sessions": cleaned}

def start_daemon(host: str = "", port: int = 0):
    """Start the HALpdesk daemon.

    Host/port can be provided via args, env, or config file. If not provided,
    values are resolved in this order:
    1) `HALPDESK_DAEMON_ENDPOINT` or `HALPDESK_DAEMON_HOST`/`HALPDESK_DAEMON_PORT`
    2) `~/.config/halpdesk/config.toml` (see README)
    3) Defaults: 127.0.0.1:8080
    """
    if not host or not port:
        cfg_host, cfg_port = server_bind(default_host="127.0.0.1", default_port=8080)
        host = host or cfg_host
        port = port or cfg_port
    logger.info("[startup] binding daemon on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")

@app.on_event("shutdown")
async def _on_shutdown():
    logger.info("[shutdown] daemon is stopping; cleaning up background services")
    try:
        stop_autostarted_ollama()
    except Exception:
        logger.exception("[shutdown] error stopping autostarted Ollama")

@app.get("/diagnostics")
async def diagnostics():
    """Return provider and connectivity diagnostics.

    - For Ollama: checks /api/version and /api/tags and whether selected model exists.
    - For OpenAI: attempts GET/HEAD /models (auth required for detailed data).
    - For Claude: HEAD /v1/messages just to test reachability; auth presence is reported.
    """
    name = ai_provider.__class__.__name__
    model = getattr(ai_provider, "model", None)
    base = getattr(ai_provider, "base_url", None)

    info = {
        "provider": {"name": name, "model": model, "base_url": base},
        "connectivity": {"reachable": False, "http_status": None, "status": "unknown"},
        "details": {},
    }

    # Include sessions summary with attached counts
    try:
        active = [
            {
                "session_id": s.session_id,
                "mode": s.mode.value if hasattr(s, "mode") else None,
                "cwd": getattr(s, "cwd", None),
                "attached_count": len(getattr(s, "attached_clients", []) or []),
            }
            for s in session_manager.sessions.values()
        ]
        info["sessions"] = {"count": len(active), "active": active}
    except Exception:
        info["sessions"] = {"count": 0, "active": []}

    try:
        if isinstance(ai_provider, OllamaProvider) and base:
            version_url = base.rstrip("/") + "/api/version"
            t0 = time.perf_counter()
            r = requests.get(version_url, timeout=2)
            info["connectivity"]["http_status"] = r.status_code
            info["connectivity"]["reachable"] = r.ok
            info["connectivity"]["status"] = "ok" if r.ok else "error"

            tags_url = base.rstrip("/") + "/api/tags"
            r2 = requests.get(tags_url, timeout=2)
            if r2.ok:
                data = r2.json() or {}
                models = data.get("models", [])
                names = []
                for m in models:
                    nm = m.get("name") or m.get("model")
                    if nm:
                        names.append(nm)
                info["details"]["installed_models"] = names
                info["details"]["selected_model_present"] = bool(model in names)
        elif isinstance(ai_provider, GeminiProvider) and base:
            url = base.rstrip("/") + "/models"
            headers = {"Authorization": f"Bearer {getattr(ai_provider, 'api_key', '')}"}
            try:
                r = requests.get(url, headers=headers, timeout=2)
            except Exception:
                r = requests.head(url, timeout=2)
            info["connectivity"]["http_status"] = getattr(r, "status_code", None)
            info["connectivity"]["reachable"] = bool(getattr(r, "status_code", 0))
            info["connectivity"]["status"] = "ok" if getattr(r, "ok", False) else "warn"
            info["details"]["auth_present"] = bool(getattr(ai_provider, "api_key", None))
        elif isinstance(ai_provider, ClaudeProvider) and base:
            url = base.rstrip("/") + "/v1/messages"
            try:
                r = requests.head(url, timeout=2)
            except Exception as e:
                info["connectivity"]["status"] = f"error: {e}"
            else:
                info["connectivity"]["http_status"] = r.status_code
                info["connectivity"]["reachable"] = True
                info["connectivity"]["status"] = "ok" if r.ok else "warn"
            info["details"]["auth_present"] = bool(getattr(ai_provider, "api_key", None))
        else:
            info["connectivity"]["status"] = "unknown-provider"
    except Exception as e:  # noqa: BLE001
        info["connectivity"]["status"] = f"exception: {e}"

    return info

if __name__ == "__main__":
    start_daemon()
