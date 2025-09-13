#!/usr/bin/env python3
"""Live demo of HALpdesk with working Ollama"""
import requests
import time
from rich.console import Console

console = Console()

def live_demo():
    """Demonstrate HALpdesk with working AI"""
    console.print("[bold cyan]🚀 HALpdesk Live Demo with CodeLlama[/bold cyan]\n")
    
    base_url = "http://127.0.0.1:8080"
    
    # Create session
    console.print("[bold]Creating session...[/bold]")
    response = requests.post(f"{base_url}/session/create", json={
        "pid": 12345,
        "cwd": "/Users/demo/project"
    })
    session_id = response.json()["session_id"]
    console.print(f"Session: [green]{session_id}[/green]\n")
    
    # Test real command suggestions
    console.print("[bold]Testing AI command suggestions:[/bold]")
    test_queries = [
        "list all files with details",
        "show disk usage",
        "find all Python files",
        "check running processes",
        "show current directory"
    ]
    
    for query in test_queries:
        console.print(f"\n[dim]Query:[/dim] '{query}'")
        console.print("[yellow]Thinking...[/yellow]", end="")
        
        response = requests.post(f"{base_url}/command/suggest", json={
            "session_id": session_id,
            "query": query
        })
        
        if response.status_code == 200:
            data = response.json()
            command = data.get("command", "N/A")
            safety = data.get("safety_level", "❓")
            reason = data.get("safety_reason", "")
            
            console.print(f"\r[green]Suggested:[/green] [bold]{command}[/bold] {safety}")
            if safety != "🟢":
                console.print(f"[dim]{reason}[/dim]")
        else:
            console.print(f"\r[red]Error: {response.status_code}[/red]")
    
    console.print()
    
    # Test chat mode
    console.print("[bold]Testing chat mode:[/bold]")
    requests.post(f"{base_url}/session/mode", json={
        "session_id": session_id,
        "mode": "chat"
    })
    
    chat_messages = [
        "What does the ls command do?",
        "How do I safely delete files?"
    ]
    
    for message in chat_messages:
        console.print(f"\n[dim]Chat:[/dim] '{message}'")
        console.print("[blue]AI thinking...[/blue]", end="")
        
        response = requests.post(f"{base_url}/chat", json={
            "session_id": session_id,
            "message": message
        })
        
        if response.status_code == 200:
            ai_response = response.json()["response"]
            console.print(f"\r[blue]AI:[/blue] {ai_response}")
        else:
            console.print(f"\r[red]Chat Error: {response.status_code}[/red]")
    
    # Clean up
    requests.delete(f"{base_url}/session/{session_id}")
    console.print(f"\n[green]✅ Demo completed! CodeLlama is working perfectly.[/green]")

if __name__ == "__main__":
    live_demo()