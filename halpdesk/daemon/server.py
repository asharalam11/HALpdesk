"""HALpdesk daemon server"""
import os
import time
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

from .session import SessionManager, SessionMode
from .ai_provider import AIProviderFactory
from .safety import CommandSafetyChecker
from ..config import server_bind

app = FastAPI(title="HALpdesk Daemon", version="0.1.0")
session_manager = SessionManager()
ai_provider = AIProviderFactory.create_provider()
logger = logging.getLogger("halpdesk.daemon")

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

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/session/create", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    session_id = session_manager.create_session(request.pid, request.cwd)
    return SessionResponse(session_id=session_id)

@app.get("/session/list")
async def list_sessions():
    return {"sessions": session_manager.list_sessions()}

@app.get("/session/{session_id}")
async def get_session(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session.to_dict()}

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
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
    
    success = session_manager.switch_mode(request.session_id, mode)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse(session_id=request.session_id)

@app.post("/command/suggest", response_model=CommandResponse)
async def suggest_command(request: QueryRequest):
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get command suggestion from AI
    context = {"cwd": session.cwd, "history": session.history}
    prov_name = ai_provider.__class__.__name__
    model = getattr(ai_provider, "model", None)
    logger.info("[api/suggest] → provider=%s model=%s query_len=%s", prov_name, model, len(request.query))
    t0 = time.perf_counter()
    command = ai_provider.get_command_suggestion(request.query, context)
    dt = (time.perf_counter() - t0) * 1000
    logger.info("[api/suggest] ← %sms", int(dt))
    
    # Check safety
    safety_level, safety_reason = CommandSafetyChecker.check_command(command)
    
    # Add to session history
    session.add_to_history({
        "type": "command_suggestion",
        "query": request.query,
        "command": command,
        "safety_level": safety_level
    })
    
    return CommandResponse(
        command=command,
        safety_level=safety_level,
        safety_reason=safety_reason
    )

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get chat response from AI
    context = {"cwd": session.cwd, "history": session.history}
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
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    start_daemon()
