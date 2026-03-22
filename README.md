# Abu CLI

**Interactive AI coding assistant in your terminal — powered by [AgentX](https://github.com/PM-Shawn/AgentX) framework.**

Abu is a model-agnostic CLI tool inspired by Claude Code. It connects to any LLM (Claude, GPT, DeepSeek, Qwen, etc.) and provides a complete coding assistant experience with file operations, terminal commands, web search, and more.

## Features

- **Model Agnostic** — Works with Claude, OpenAI, DeepSeek, Ollama, and any Anthropic/OpenAI-compatible API
- **7 Built-in Tools** — Read, Write, Edit, Bash, Glob, Grep, WebSearch
- **MCP Support** — Connect to any MCP server (stdio + HTTP)
- **Smart Permissions** — Auto-approve safe commands, ask for dangerous ones, or `--yolo` mode
- **Streaming Markdown** — Real-time rendered output with syntax highlighting
- **Session Persistence** — Auto-save conversations, resume anytime with `/resume`
- **Theme System** — 5 built-in themes, switchable with `/theme`
- **Git Integration** — `/commit` generates commit messages, `/diff` shows changes
- **Pipe Support** — `cat file.py | abu "explain this"`

## Quick Start

```bash
# Install (requires Python 3.11+ and uv)
git clone https://github.com/PM-Shawn/Abu-CLI.git
cd Abu-CLI
uv tool install -e .

# Configure your model
mkdir -p ~/.abu
cat > ~/.abu/config.json << 'EOF'
{
  "model": "claude-sonnet-4-6",
  "providers": {
    "claude": {
      "api_key": "sk-xxx",
      "format": "anthropic"
    }
  }
}
EOF

# Start
abu
```

## Usage

```bash
abu                          # Interactive REPL
abu "fix the login bug"      # Start with a prompt
abu -p "explain main.py"     # Pipe mode (print and exit)
abu --yolo "refactor this"   # Auto-approve all tool calls
abu -c                       # Continue last session
abu --resume s-1742672400    # Resume specific session
cat file.py | abu "review"   # Pipe file content
```

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/init` | Create ABU.md project context |
| `/compact` | Compress conversation context |
| `/yolo` | Toggle auto-approve mode |
| `/commit` | Auto-generate commit message |
| `/diff` | Show git diff with highlighting |
| `/cost` | Show token usage and cost |
| `/model <name>` | Switch model |
| `/theme <name>` | Switch theme (default/dark/ocean/rose/mono) |
| `/mcp` | Show connected MCP servers |
| `/resume` | List and restore previous sessions |
| `/context` | Show loaded context sources |
| `/quit` | Exit |

## Configuration

`~/.abu/config.json`:

```json
{
  "model": "MiniMax-M2.7",
  "theme": "ocean",
  "providers": {
    "MiniMax": {
      "api_key": "sk-xxx",
      "base_url": "https://api.minimaxi.com/anthropic",
      "format": "anthropic"
    },
    "OpenAI": {
      "api_key": "sk-xxx",
      "format": "openai"
    },
    "DeepSeek": {
      "api_key": "sk-xxx",
      "base_url": "https://api.deepseek.com/v1",
      "format": "openai"
    }
  },
  "mcp_servers": {
    "filesystem": {
      "transport": "stdio",
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  }
}
```

## Project Context

Create `ABU.md` in your project root (like Claude Code's `CLAUDE.md`):

```bash
abu
› /init    # Auto-generates ABU.md from project structure
```

Abu reads this file on startup and includes it in the system prompt for project-aware assistance.

## Architecture

Abu CLI is built on [AgentX](https://github.com/PM-Shawn/AgentX), a lightweight model-agnostic AI agent framework:

```
Abu CLI (this repo)
  ├── REPL + Renderer (prompt-toolkit + Rich)
  ├── Permission System
  ├── Theme System
  ├── Session Manager
  └── AgentX Framework
        ├── Provider abstraction (Claude/OpenAI/Gemini/Ollama)
        ├── Tool system (@tool decorator)
        ├── Agent loop (Runner/StreamingRunner)
        ├── MCP client (stdio + HTTP)
        └── Guardrails, Hooks, Tracing
```

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- An LLM API key (Claude, OpenAI, or compatible)

## License

MIT
