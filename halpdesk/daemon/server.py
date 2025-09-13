"""HALpdesk daemon server"""
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

from .session import SessionManager, SessionMode
from .ai_provider import AIProviderFactory
from .safety import CommandSafetyChecker

app = FastAPI(title="HALpdesk Daemon", version="0.1.0")
session_manager = SessionManager()
ai_provider = AIProviderFactory.create_provider()

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
    command = ai_provider.get_command_suggestion(request.query, context)
    
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
    response = ai_provider.chat(request.message, context)
    
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

def start_daemon(host: str = "127.0.0.1", port: int = 8080):
    """Start the HALpdesk daemon"""
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    start_daemon()