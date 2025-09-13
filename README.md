# HALpdesk

AI-powered terminal assistant that provides command suggestions and chat capabilities.

## Features

- 🤖 **Natural Language to Commands**: Convert natural language requests to bash commands
- 💬 **Chat Mode**: Direct conversation with AI
- ⚡ **Multi-Session Support**: Run multiple terminal sessions simultaneously  
- 🛡️ **Safety Indicators**: Visual warnings for dangerous commands
- 🔄 **Mode Switching**: Switch between execution and chat modes
- 📝 **Session Management**: Join, detach, and switch between sessions

## Installation

### From Source

```bash
git clone <repository-url>
cd halpdesk
pip install -e .
```

### Requirements

- Python 3.8+
- Either Ollama running locally OR OpenAI API key

## Quick Start

1. **Start the daemon**:
   ```bash
   halpdesk-daemon
   ```

2. **Start HAL in a terminal**:
   ```bash
   halp
   ```

3. **Try some commands**:
   ```
   HAL> list files
   Suggested: ls -la 🟢
   Press Enter to execute, or type your own command
   
   HAL> /chat
   HAL (chat)> What does ls do?
   ```

## Usage

### Basic Commands

- `halp` - Start new session or join existing
- `halp list` - List all active sessions  
- `halp join <session_id>` - Join existing session
- `halp new` - Force create new session

### Session Commands

- `/sessions` - List all sessions
- `/switch <id>` - Switch to different session
- `/detach` - Detach from session (keeps running)
- `/chat` - Switch to chat mode
- `/exec` - Switch to execution mode
- `/help` - Show help
- `exit` - Exit session

### Configuration

Set environment variables:

```bash
export OPENAI_API_KEY="your-key-here"  # For OpenAI
# OR use local Ollama (default)
```

## Architecture

```
Terminal 1 ─┐
Terminal 2 ─┼─→ HALpdesk Daemon ─→ Ollama/OpenAI
Terminal 3 ─┘
```

Each terminal maintains its own session with independent context and history.

## Safety Features

Commands are analyzed for safety:
- 🟢 Safe commands  
- 🟡 Caution required
- 🔴 Potentially dangerous

## Development

```bash
pip install -e ".[dev]"
pytest
```