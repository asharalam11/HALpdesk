"""Session management for HALpdesk daemon"""
import os
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class SessionMode(Enum):
    EXECUTION = "exec"
    CHAT = "chat"

@dataclass
class Session:
    session_id: str
    pid: int
    cwd: str
    mode: SessionMode = SessionMode.EXECUTION
    created_at: float = None
    last_active: float = None
    history: List[Dict] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.last_active is None:
            self.last_active = time.time()
        if self.history is None:
            self.history = []
    
    def update_activity(self):
        self.last_active = time.time()
    
    def add_to_history(self, entry: Dict):
        self.history.append(entry)
        self.update_activity()
    
    def to_dict(self):
        data = asdict(self)
        data['mode'] = self.mode.value
        return data

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
    
    def create_session(self, pid: int, cwd: str) -> str:
        session_id = f"term_{pid}_{int(time.time())}"
        session = Session(session_id=session_id, pid=pid, cwd=cwd)
        self.sessions[session_id] = session
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)
    
    def get_session_by_pid(self, pid: int) -> Optional[Session]:
        for session in self.sessions.values():
            if session.pid == pid:
                return session
        return None
    
    def list_sessions(self) -> List[Dict]:
        return [session.to_dict() for session in self.sessions.values()]
    
    def delete_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    def switch_mode(self, session_id: str, mode: SessionMode) -> bool:
        session = self.get_session(session_id)
        if session:
            session.mode = mode
            session.update_activity()
            return True
        return False
    
    def cleanup_stale_sessions(self, max_age: float = 3600):  # 1 hour
        current_time = time.time()
        stale_sessions = []
        
        for session_id, session in self.sessions.items():
            if current_time - session.last_active > max_age:
                stale_sessions.append(session_id)
        
        for session_id in stale_sessions:
            del self.sessions[session_id]
        
        return len(stale_sessions)