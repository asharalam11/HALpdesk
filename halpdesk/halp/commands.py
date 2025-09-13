"""Session commands for HALpdesk CLI"""
import os
import sys
import subprocess
from typing import Optional
from rich.console import Console
from rich.table import Table

console = Console()

class SessionCommands:
    def __init__(self, client):
        self.client = client
    
    def handle_command(self, command: str) -> bool:
        """Handle special session commands. Returns True if handled, False otherwise."""
        command = command.strip()
        
        if command == "/sessions" or command == "/list":
            self._list_sessions()
            return True
        elif command.startswith("/switch "):
            session_id = command.split(" ", 1)[1]
            self._switch_session(session_id)
            return True
        elif command == "/detach":
            self._detach_session()
            return True
        elif command.startswith("/mode "):
            mode = command.split(" ", 1)[1]
            self._switch_mode(mode)
            return True
        elif command == "/chat":
            self._switch_mode("chat")
            return True
        elif command == "/exec":
            self._switch_mode("exec")
            return True
        elif command == "/help":
            self._show_help()
            return True
        elif command == "exit" or command == "/exit":
            self._exit_session()
            return True
        
        return False
    
    def _list_sessions(self):
        """List all active sessions"""
        try:
            response = self.client.get("/session/list")
            if response.status_code == 200:
                data = response.json()
                sessions = data.get("sessions", [])
                
                if not sessions:
                    console.print("[yellow]No active sessions[/yellow]")
                    return
                
                table = Table(title="Active Sessions")
                table.add_column("ID", style="cyan")
                table.add_column("Mode", style="green")
                table.add_column("Directory", style="blue")
                table.add_column("Attached", style="magenta")
                
                for session in sessions:
                    is_current = session.get("session_id") == self.client.current_session_id
                    current_marker = "→ " if is_current else "  "
                    attached = str(session.get("attached_count", 0))
                    table.add_row(
                        f"{current_marker}{session.get('session_id')}",
                        session.get("mode", ""),
                        session.get("cwd", ""),
                        attached,
                    )
                
                console.print(table)
            else:
                console.print("[red]Failed to list sessions[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
    
    def _switch_session(self, session_id: str):
        """Switch to a different session"""
        try:
            response = self.client.get(f"/session/{session_id}")
            if response.status_code == 200:
                self.client.current_session_id = session_id
                session_data = response.json()["session"]
                console.print(f"[green]Switched to session {session_id}[/green]")
                console.print(f"[blue]Directory: {session_data['cwd']}[/blue]")
                console.print(f"[blue]Mode: {session_data['mode']}[/blue]")
            else:
                console.print(f"[red]Session {session_id} not found[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
    
    def _detach_session(self):
        """Detach from current session (keep it running)"""
        console.print("[yellow]Detaching from session (it will keep running)[/yellow]")
        # Notify daemon of a detach (do not close if last)
        try:
            self.client.detach_session()
        except Exception:
            pass
        # Mark intent so client does not 'leave' in finally
        self.client.exiting_detached = True
        console.print("[yellow]Use 'halp list' and 'halp join <id>' to reconnect[/yellow]")
        sys.exit(0)
    
    def _switch_mode(self, mode: str):
        """Switch session mode between chat and exec"""
        if mode not in ["chat", "exec"]:
            console.print("[red]Invalid mode. Use 'chat' or 'exec'[/red]")
            return
        
        try:
            response = self.client.post("/session/mode", json={
                "session_id": self.client.current_session_id,
                "mode": mode
            })
            
            if response.status_code == 200:
                self.client.current_mode = mode
                mode_name = "Chat" if mode == "chat" else "Execution"
                console.print(f"[green]Switched to {mode_name} mode[/green]")
            else:
                console.print("[red]Failed to switch mode[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
    
    def _show_help(self):
        """Show help information"""
        help_text = """
[bold cyan]HALpdesk Commands:[/bold cyan]

[bold]Session Management:[/bold]
  /sessions, /list     - List all active sessions
  /switch <id>         - Switch to a different session  
  /detach              - Detach from current session (keeps running)
  exit, /exit          - Exit current session

[bold]Mode Switching:[/bold]
  /chat                - Switch to chat mode
  /exec                - Switch to execution mode  
  /mode <chat|exec>    - Switch to specified mode

[bold]Command Input:[/bold]
  list files               - Natural language → AI suggests command
  $ls -la                  - Direct command execution (prefix with $)
  $find . -name "*.py" \\   - Multi-line commands (end with \\)
  -type f
  ↑↓ Arrow keys           - Navigate command history

[bold]Modes:[/bold]
  [green]Execution Mode[/green] - Natural language + direct commands
  [blue]Chat Mode[/blue]      - Direct conversation with AI

[bold]Other:[/bold]
  /help                - Show this help
        """
        console.print(help_text)
    
    def _exit_session(self):
        """Exit the current session"""
        console.print("[yellow]Exiting HAL session...[/yellow]")
        sys.exit(0)
    
    def execute_command(self, command: str):
        """Execute a shell command"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=os.getcwd()
            )
            
            if result.stdout:
                console.print(result.stdout, end="")
            if result.stderr:
                console.print(f"[red]{result.stderr}[/red]", end="")
            
            return result.returncode == 0
        except Exception as e:
            console.print(f"[red]Error executing command: {e}[/red]")
            return False
