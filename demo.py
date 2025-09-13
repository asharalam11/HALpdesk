#!/usr/bin/env python3
"""Demo script showing HALpdesk functionality"""
import requests
import time
from rich.console import Console

console = Console()

def demo_halpdesk():
    """Demonstrate HALpdesk capabilities"""
    console.print("[bold cyan]🚀 HALpdesk Demo[/bold cyan]\n")
    
    base_url = "http://127.0.0.1:8080"
    
    # 1. Create a session
    console.print("[bold]1. Creating session...[/bold]")
    response = requests.post(f"{base_url}/session/create", json={
        "pid": 99999,
        "cwd": "/Users/demo/project"
    })
    session_id = response.json()["session_id"]
    console.print(f"   Created session: [green]{session_id}[/green]\n")
    
    # 2. List sessions
    console.print("[bold]2. Listing sessions...[/bold]")
    response = requests.get(f"{base_url}/session/list")
    sessions = response.json()["sessions"]
    console.print(f"   Active sessions: [yellow]{len(sessions)}[/yellow]\n")
    
    # 3. Switch to chat mode
    console.print("[bold]3. Switching to chat mode...[/bold]")
    requests.post(f"{base_url}/session/mode", json={
        "session_id": session_id,
        "mode": "chat"
    })
    console.print("   Mode: [blue]Chat[/blue]\n")
    
    # 4. Switch to execution mode  
    console.print("[bold]4. Switching to execution mode...[/bold]")
    requests.post(f"{base_url}/session/mode", json={
        "session_id": session_id,
        "mode": "exec"
    })
    console.print("   Mode: [green]Execution[/green]\n")
    
    # 5. Test command suggestions (will show error due to no AI)
    console.print("[bold]5. Testing command suggestions...[/bold]")
    test_queries = [
        "list files",
        "show disk usage", 
        "find python files",
        "delete temp files"
    ]
    
    for query in test_queries:
        response = requests.post(f"{base_url}/command/suggest", json={
            "session_id": session_id,
            "query": query
        })
        
        if response.status_code == 200:
            data = response.json()
            command = data.get("command", "N/A")
            safety = data.get("safety_level", "❓")
            console.print(f"   [dim]'{query}'[/dim] → {command} {safety}")
        else:
            console.print(f"   [dim]'{query}'[/dim] → [red]Error[/red]")
    
    console.print()
    
    # 6. Show safety examples
    console.print("[bold]6. Safety checking examples...[/bold]")
    from halpdesk.daemon.safety import CommandSafetyChecker
    
    safety_examples = [
        "ls -la",
        "mv important.txt backup.txt", 
        "rm -rf temp/",
        "sudo rm -rf /"
    ]
    
    for cmd in safety_examples:
        level, reason = CommandSafetyChecker.check_command(cmd)
        console.print(f"   [dim]'{cmd}'[/dim] → {level} [dim]({reason})[/dim]")
    
    console.print()
    
    # 7. Clean up
    console.print("[bold]7. Cleaning up session...[/bold]")
    requests.delete(f"{base_url}/session/{session_id}")
    console.print("   Session deleted ✅\n")
    
    console.print("[bold green]🎉 Demo completed![/bold green]")
    console.print("\n[bold]To use HALpdesk:[/bold]")
    console.print("1. Start daemon: [cyan]halpdesk-daemon[/cyan]")
    console.print("2. Start client: [cyan]halp[/cyan]")
    console.print("3. For AI integration, install Ollama or set OPENAI_API_KEY")

if __name__ == "__main__":
    demo_halpdesk()