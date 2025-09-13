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

### Diagnostics

- Check daemon health: `curl -s http://127.0.0.1:8080/health`
- Inspect provider and connectivity: `curl -s http://127.0.0.1:8080/diagnostics | jq` (or omit `| jq`)

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

You can configure the daemon endpoint and the CLI via a config file or environment variables.

Config file (optional): `~/.config/halpdesk/config.toml`

Example:

```toml
[server]
# Preferred: set a unified endpoint
endpoint = "http://127.0.0.1:8080"
# Or set host/port individually
# host = "127.0.0.1"
# port = 8080

[client]
# Where the `halp` CLI reaches the daemon
daemon_url = "http://127.0.0.1:8080"
```

Environment overrides:

```bash
export HALPDESK_DAEMON_ENDPOINT="http://127.0.0.1:8080"  # or use HALPDESK_DAEMON_HOST/PORT
export HALPDESK_DAEMON_URL="http://127.0.0.1:8080"       # used by halp CLI
export OPENAI_API_KEY="your-key-here"                     # if using OpenAI
export ANTHROPIC_API_KEY="your-key-here"                  # if using Claude
export OLLAMA_HOST="http://localhost:11434"               # if using Ollama
export HALPDESK_OLLAMA_BIN="/usr/local/bin/ollama"         # optional: binary path for auto-start
export HALPDESK_OLLAMA_AUTOSTART=1                         # set 0/false to disable

Provider configuration (optional) in `~/.config/halpdesk/config.toml`:

```toml
[providers]
default = "ollama"  # or "openai" / "claude"

  [providers.openai]
  base_url = "https://api.openai.com/v1"
  model = "gpt-3.5-turbo"

  [providers.claude]
  base_url = "https://api.anthropic.com"
  model = "claude-3-haiku-20240307"

  [providers.ollama]
  base_url = "http://localhost:11434"
  model = "llama2"
  # optional: where to find the 'ollama' binary; if omitted, PATH is used
  # binary = "/usr/local/bin/ollama"

Ollama auto-start: When the default or selected provider is Ollama and the server
is not reachable at `providers.ollama.base_url`, the daemon attempts to launch
`ollama serve` in the background (respecting `OLLAMA_HOST` derived from the URL).
```
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
