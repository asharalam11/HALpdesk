"""HALpdesk CLI client"""
import os
import sys
import requests
import time
from typing import Optional
from rich.console import Console
from rich.prompt import Confirm
from rich.panel import Panel
from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.formatted_text import HTML

from .commands import SessionCommands
from ..config import client_daemon_url

console = Console()

class HALpClient:
    def __init__(self, daemon_url: str | None = None):
        # Determine URL from arg, env or config
        self.daemon_url = daemon_url or client_daemon_url()
        self.current_session_id: Optional[str] = None
        self.current_mode: str = "exec"
        self.commands = SessionCommands(self)
        # Command history for arrow key support
        self.history = InMemoryHistory()
    
    def get(self, endpoint: str):
        """Make GET request to daemon"""
        return requests.get(f"{self.daemon_url}{endpoint}")
    
    def post(self, endpoint: str, json: dict):
        """Make POST request to daemon"""
        return requests.post(f"{self.daemon_url}{endpoint}", json=json)
    
    def delete(self, endpoint: str):
        """Make DELETE request to daemon"""
        return requests.delete(f"{self.daemon_url}{endpoint}")
    
    def check_daemon(self) -> bool:
        """Check if daemon is running"""
        try:
            response = self.get("/health")
            return response.status_code == 200
        except:
            return False
    
    def create_session(self) -> bool:
        """Create a new session"""
        try:
            pid = os.getpid()
            cwd = os.getcwd()
            
            response = self.post("/session/create", {
                "pid": pid,
                "cwd": cwd
            })
            
            if response.status_code == 200:
                data = response.json()
                self.current_session_id = data["session_id"]
                return True
            return False
        except Exception as e:
            console.print(f"[red]Error creating session: {e}[/red]")
            return False
    
    def join_session(self, session_id: str) -> bool:
        """Join an existing session"""
        try:
            response = self.get(f"/session/{session_id}")
            if response.status_code == 200:
                self.current_session_id = session_id
                session_data = response.json()["session"]
                self.current_mode = session_data["mode"]
                return True
            return False
        except:
            return False
    
    def list_sessions(self):
        """List all sessions and return to shell"""
        self.commands._list_sessions()
    
    def get_command_suggestion(self, query: str) -> Optional[dict]:
        """Get command suggestion from AI"""
        try:
            response = self.post("/command/suggest", {
                "session_id": self.current_session_id,
                "query": query
            })
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            console.print(f"[red]Error getting suggestion: {e}[/red]")
            return None
    
    def chat(self, message: str) -> Optional[str]:
        """Send chat message to AI"""
        try:
            response = self.post("/chat", {
                "session_id": self.current_session_id,
                "message": message
            })
            
            if response.status_code == 200:
                return response.json()["response"]
            return None
        except Exception as e:
            console.print(f"[red]Error in chat: {e}[/red]")
            return None
    
    def show_welcome(self):
        """Show welcome message"""
        mode_color = "blue" if self.current_mode == "chat" else "green"
        mode_name = "Chat" if self.current_mode == "chat" else "Execution"
        
        welcome_text = f"""
[bold cyan]🤖 HALpdesk AI Terminal Assistant[/bold cyan]

[bold]Session ID:[/bold] {self.current_session_id}
[bold]Mode:[/bold] [{mode_color}]{mode_name}[/{mode_color}]
[bold]Directory:[/bold] {os.getcwd()}

Type '/help' for commands, 'exit' to quit.
        """
        console.print(Panel(welcome_text.strip(), expand=False))
    
    def run_interactive(self):
        """Run interactive session"""
        self.show_welcome()
        
        while True:
            try:
                # Show appropriate prompt based on mode
                if self.current_mode == "chat":
                    prompt_text = HTML('<ansiblue>HAL (chat)></ansiblue> ')
                else:
                    prompt_text = HTML('<ansigreen>HAL></ansigreen> ')
                
                user_input = prompt(prompt_text, history=self.history).strip()
                
                if not user_input:
                    continue
                
                # Handle session commands first
                if self.commands.handle_command(user_input):
                    continue
                
                # Handle based on current mode
                if self.current_mode == "chat":
                    self._handle_chat_mode(user_input)
                else:
                    self._handle_exec_mode(user_input)
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit HAL[/yellow]")
            except EOFError:
                break
    
    def _handle_chat_mode(self, message: str):
        """Handle chat mode input"""
        response = self.chat(message)
        if response:
            console.print(f"[blue]{response}[/blue]")
    
    def _handle_exec_mode(self, query: str):
        """Handle execution mode input"""
        if query.startswith('$'):
            # Direct command execution
            self._handle_direct_command(query[1:].strip())
        else:
            # AI suggestion mode (existing behavior)
            self._handle_ai_suggestion(query)
    
    def _handle_direct_command(self, command: str):
        """Handle direct command execution with $ prefix"""
        from halpdesk.daemon.safety import CommandSafetyChecker
        from rich.prompt import Confirm
        
        # Handle multi-line commands with \ continuation
        if command.endswith('\\'):
            command = self._collect_multiline_command(command)
        
        # Check command safety
        safety_level, safety_reason = CommandSafetyChecker.check_command(command)
        
        console.print(f"Command: [bold]{command}[/bold] {safety_level}")
        if safety_level != "🟢":
            console.print(f"[yellow]Warning: {safety_reason}[/yellow]")
            if not Confirm.ask("Continue?", default=False):
                return
        
        # Execute directly
        console.print(f"[dim]$ {command}[/dim]")
        self.commands.execute_command(command)
    
    def _collect_multiline_command(self, initial_command: str):
        """Collect multi-line command with \ continuation"""
        command_parts = [initial_command.rstrip('\\')]
        
        while True:
            try:
                next_line = prompt(HTML('<ansidim>&gt; </ansidim>'), history=self.history)
                if not next_line:
                    break
                if next_line.endswith('\\'):
                    command_parts.append(next_line.rstrip('\\'))
                else:
                    command_parts.append(next_line)
                    break
            except (KeyboardInterrupt, EOFError):
                break
        
        return ' '.join(command_parts)
    
    def _handle_ai_suggestion(self, query: str):
        """Handle AI command suggestion (original behavior)"""
        suggestion = self.get_command_suggestion(query)
        
        if not suggestion:
            console.print("[red]Failed to get command suggestion[/red]")
            return
        
        command = suggestion["command"]
        safety_level = suggestion["safety_level"]
        safety_reason = suggestion["safety_reason"]
        
        # Show suggested command with safety indicator
        console.print(f"Suggested: [bold]{command}[/bold] {safety_level}")
        if safety_level != "🟢":
            console.print(f"[yellow]Warning: {safety_reason}[/yellow]")
        
        # Ask user for confirmation (prompt_toolkit does not support 'choices' kw)
        while True:
            choice = prompt(
                "Press Enter to execute, 'e' to edit, or 's' to skip: ",
                default="",
                history=self.history,
            ).strip().lower()
            if choice in ("", "e", "s", "execute", "edit", "skip"):
                break
            console.print("[yellow]Please type Enter, 'e', or 's'.[/yellow]")
        
        if choice in ("", "execute"):
            # Execute the suggested command
            console.print(f"[dim]$ {command}[/dim]")
            self.commands.execute_command(command)
        elif choice in ("e", "edit"):
            # Let user edit the command
            edited_command = prompt("Edit command: ", default=command, history=self.history)
            console.print(f"[dim]$ {edited_command}[/dim]")
            self.commands.execute_command(edited_command)
        # Skip does nothing

def main():
    """Main entry point for halp command"""
    import argparse
    
    parser = argparse.ArgumentParser(description="HALpdesk AI Terminal Assistant")
    parser.add_argument("command", nargs="?", choices=["list", "join", "new"], help="Command to run")
    parser.add_argument("session_id", nargs="?", help="Session ID for join command")
    
    args = parser.parse_args()
    
    client = HALpClient()
    
    # Check if daemon is running
    if not client.check_daemon():
        console.print("[red]❌ HALpdesk daemon is not running![/red]")
        console.print("[yellow]Start it with: halpdesk-daemon[/yellow]")
        sys.exit(1)
    
    # Handle non-interactive commands
    if args.command == "list":
        client.list_sessions()
        return
    
    if args.command == "join":
        if not args.session_id:
            console.print("[red]Session ID required for join command[/red]")
            sys.exit(1)
        
        if client.join_session(args.session_id):
            console.print(f"[green]Joined session {args.session_id}[/green]")
        else:
            console.print(f"[red]Failed to join session {args.session_id}[/red]")
            sys.exit(1)
    
    elif args.command == "new" or args.command is None:
        # Create new session (default behavior)
        if not client.create_session():
            console.print("[red]Failed to create session[/red]")
            sys.exit(1)
    
    # Run interactive session
    try:
        client.run_interactive()
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")

if __name__ == "__main__":
    main()
