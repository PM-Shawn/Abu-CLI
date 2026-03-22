"""Slash commands — aligned with Claude Code's built-in commands."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from abu_cli.repl import REPLState


COMMANDS: dict[str, str] = {
    "/help": "Show available commands",
    "/init": "Create ABU.md project context file",
    "/clear": "Clear conversation history",
    "/compact": "Compress conversation context to save tokens",
    "/yolo": "Toggle auto-approve mode (skip permission prompts)",
    "/cost": "Show token usage and cost",
    "/model": "Switch model: /model <name>",
    "/theme": "Switch theme: /theme <name>",
    "/mcp": "Show connected MCP servers",
    "/resume": "Resume a previous session",
    "/commit": "Generate commit message and commit",
    "/diff": "Show git diff of current changes",
    "/context": "Show loaded context sources",
    "/quit": "Exit the CLI",
}


async def dispatch_command(raw: str, state: "REPLState") -> None:
    """Parse and execute a slash command."""
    parts = raw.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/help", "/h"):
        _cmd_help(state)
    elif cmd == "/init":
        await _cmd_init(state)
    elif cmd in ("/clear", "/reset", "/new"):
        _cmd_clear(state)
    elif cmd == "/cost":
        _cmd_cost(state)
    elif cmd == "/model":
        _cmd_model(state, arg)
    elif cmd == "/theme":
        _cmd_theme(state, arg)
    elif cmd == "/compact":
        _cmd_compact(state)
    elif cmd == "/yolo":
        _cmd_yolo(state)
    elif cmd == "/mcp":
        _cmd_mcp(state)
    elif cmd == "/resume":
        _cmd_resume(state, arg)
    elif cmd == "/commit":
        await _cmd_commit(state, arg)
    elif cmd == "/diff":
        await _cmd_diff(state)
    elif cmd in ("/quit", "/exit", "/q"):
        raise SystemExit(0)
    elif cmd == "/context":
        _cmd_context(state)
    else:
        state.renderer.render_error(f"Unknown command: {cmd}. Type /help for available commands.")


def _cmd_help(state: "REPLState") -> None:
    state.renderer.console.print()
    state.renderer.console.print("[bold]Available commands:[/bold]")
    for cmd, desc in COMMANDS.items():
        state.renderer.console.print(f"  [cyan]{cmd:<12}[/cyan] {desc}")
    state.renderer.console.print()


def _cmd_clear(state: "REPLState") -> None:
    state.messages.clear()
    state.renderer.render_info("Conversation cleared.")


def _cmd_cost(state: "REPLState") -> None:
    u = state.total_usage
    state.renderer.console.print()
    state.renderer.console.print("[bold]Token Usage:[/bold]")
    state.renderer.console.print(f"  Input:  {u.input_tokens:>10,}")
    state.renderer.console.print(f"  Output: {u.output_tokens:>10,}")
    if u.cache_read_tokens:
        state.renderer.console.print(f"  Cache:  {u.cache_read_tokens:>10,} (read)")
    state.renderer.console.print(f"  Cost:   ${state.total_cost:>10.4f}")
    state.renderer.console.print()


async def _cmd_commit(state: "REPLState", arg: str) -> None:
    """Let Abu generate a commit message from git diff and commit."""
    from abu_cli.repl import _process_turn

    prompt = (
        "Look at the current git diff (staged and unstaged changes), "
        "then create a concise commit message following conventional commits format. "
        "Stage all changed files and make the commit. "
        "Show me the commit message before committing."
    )
    if arg:
        prompt = f"Commit with this context: {arg}. " + prompt

    await _process_turn(state, prompt)


async def _cmd_diff(state: "REPLState") -> None:
    """Show git diff with syntax highlighting."""
    import asyncio

    proc = await asyncio.create_subprocess_exec(
        "git", "diff", "--stat",
        cwd=str(state.cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        state.renderer.render_error("Not a git repository or git not available")
        return

    stat = stdout.decode().strip()
    if not stat:
        # Check staged
        proc2 = await asyncio.create_subprocess_exec(
            "git", "diff", "--cached", "--stat",
            cwd=str(state.cwd),
            stdout=asyncio.subprocess.PIPE,
        )
        stdout2, _ = await proc2.communicate()
        stat = stdout2.decode().strip()
        if not stat:
            state.renderer.render_info("No changes detected.")
            return
        state.renderer.console.print("\n[bold]Staged changes:[/bold]")
    else:
        state.renderer.console.print("\n[bold]Unstaged changes:[/bold]")

    state.renderer.console.print(f"[dim]{stat}[/dim]")

    # Full diff
    proc3 = await asyncio.create_subprocess_exec(
        "git", "diff",
        cwd=str(state.cwd),
        stdout=asyncio.subprocess.PIPE,
    )
    stdout3, _ = await proc3.communicate()
    diff = stdout3.decode()

    if diff:
        from rich.syntax import Syntax
        syntax = Syntax(diff[:3000], "diff", theme="monokai", line_numbers=False)
        state.renderer.console.print(syntax)
        if len(diff) > 3000:
            state.renderer.console.print(f"[dim]... ({len(diff) - 3000} more chars)[/dim]")
    state.renderer.console.print()


def _cmd_model(state: "REPLState", arg: str) -> None:
    if not arg:
        state.renderer.console.print(f"Current model: [cyan]{state.model}[/cyan]")
        state.renderer.console.print("Usage: /model <name>  (e.g., /model gpt-4o)")
        return

    state.model = arg.strip()
    from abu_cli.agent import build_agent
    state.agent = build_agent(model=state.model, cwd=state.cwd)
    state.renderer.render_info(f"Switched to model: {state.model}")


def _cmd_theme(state: "REPLState", arg: str) -> None:
    from abu_cli.themes import list_themes, get_theme

    available = list_themes()

    if not arg:
        state.renderer.console.print()
        state.renderer.console.print(f"[bold]Current theme:[/bold] {state.renderer.theme.name}")
        state.renderer.console.print(f"[bold]Available:[/bold] {', '.join(available)}")
        state.renderer.console.print("Usage: /theme <name>")
        state.renderer.console.print()
        return

    name = arg.strip().lower()
    if name not in available:
        state.renderer.render_error(
            f"Unknown theme: {name}. Available: {', '.join(available)}"
        )
        return

    theme = get_theme(name)
    state.renderer.set_theme(theme)

    # Save to config
    import json
    from pathlib import Path
    config_file = Path.home() / ".abu" / "config.json"
    config = {}
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text())
        except Exception:
            pass
    config["theme"] = name
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config, indent=2))

    state.renderer.render_info(f"Theme switched to: {name}")


async def _cmd_init(state: "REPLState") -> None:
    """Scan project and create ABU.md — like Claude Code's /init."""
    from pathlib import Path
    import subprocess

    abu_md = state.cwd / "ABU.md"
    if abu_md.exists():
        state.renderer.render_info("ABU.md already exists. Delete it first to re-init.")
        return

    state.renderer.render_info("Scanning project...")

    # Gather project info
    sections = []
    sections.append("# Project Context\n")

    # Project name from directory
    project_name = state.cwd.name
    sections.append(f"## {project_name}\n")

    # Detect project type from files
    markers = {
        "pyproject.toml": "Python (uv/pip)",
        "package.json": "Node.js",
        "Cargo.toml": "Rust",
        "go.mod": "Go",
        "pom.xml": "Java (Maven)",
        "build.gradle": "Java (Gradle)",
        "Gemfile": "Ruby",
        "requirements.txt": "Python (pip)",
    }
    detected = []
    for marker, lang in markers.items():
        if (state.cwd / marker).exists():
            detected.append(lang)

    if detected:
        sections.append(f"**Tech stack:** {', '.join(detected)}\n")

    # Read pyproject.toml or package.json for description
    if (state.cwd / "pyproject.toml").exists():
        try:
            content = (state.cwd / "pyproject.toml").read_text()
            for line in content.splitlines():
                if line.strip().startswith("description"):
                    desc = line.split("=", 1)[1].strip().strip('"').strip("'")
                    sections.append(f"**Description:** {desc}\n")
                    break
        except Exception:
            pass
    elif (state.cwd / "package.json").exists():
        try:
            import json
            pkg = json.loads((state.cwd / "package.json").read_text())
            if "description" in pkg:
                sections.append(f"**Description:** {pkg['description']}\n")
        except Exception:
            pass

    # Directory structure (top-level only)
    sections.append("\n## Project Structure\n")
    sections.append("```")
    try:
        entries = sorted(state.cwd.iterdir())
        for entry in entries:
            if entry.name.startswith(".") and entry.name not in (".github", ".env.example"):
                continue
            if entry.name in ("node_modules", "__pycache__", ".venv", "venv", "dist", "build"):
                continue
            suffix = "/" if entry.is_dir() else ""
            sections.append(f"{entry.name}{suffix}")
    except Exception:
        sections.append("(unable to scan)")
    sections.append("```\n")

    # Add template sections
    sections.append("""
## Key Conventions

<!-- Add your project's coding standards here -->
<!-- Example: -->
<!-- - Use async/await for all I/O -->
<!-- - Tests go in tests/ directory -->
<!-- - Use Pydantic for data validation -->

## Important Notes

<!-- Add things Abu should know about this project -->
<!-- Example: -->
<!-- - Main entry point is src/main.py -->
<!-- - Run tests with: uv run pytest -->
<!-- - Database migrations in db/migrations/ -->
""")

    # Write file
    abu_md.write_text("\n".join(sections), encoding="utf-8")
    line_count = len(sections)

    state.renderer.console.print()
    state.renderer.console.print(
        f"  [bold green]✓[/bold green] Created [bold]ABU.md[/bold] ({line_count} lines)"
    )
    state.renderer.console.print(
        "  [dim]Edit it to add project-specific context for Abu.[/dim]"
    )
    state.renderer.console.print()


def _cmd_compact(state: "REPLState") -> None:
    """Compress conversation context — summarize old messages to save tokens."""
    if len(state.messages) < 4:
        state.renderer.render_info("Conversation too short to compact.")
        return

    before = sum(
        len(m.content) if isinstance(m.content, str)
        else sum(len(getattr(b, "text", "")) for b in m.content if hasattr(m.content, "__iter__"))
        for m in state.messages
    )
    before_count = len(state.messages)

    # Keep last 2 turns, summarize the rest
    keep_count = 4  # 2 user + 2 assistant
    if len(state.messages) <= keep_count:
        state.renderer.render_info("Conversation too short to compact.")
        return

    old_messages = state.messages[:-keep_count]
    recent_messages = state.messages[-keep_count:]

    # Build summary of old messages
    summary_parts = []
    for m in old_messages:
        role = "User" if m.role == "user" else "Abu"
        if isinstance(m.content, str):
            text = m.content[:200]
        elif isinstance(m.content, list):
            texts = []
            for b in m.content:
                if hasattr(b, "text"):
                    texts.append(b.text[:100])
            text = " ".join(texts)[:200]
        else:
            text = str(m.content)[:200]
        summary_parts.append(f"[{role}]: {text}")

    summary = "[Conversation summary]\n" + "\n".join(summary_parts)

    from agentx.types import TextContent, Message
    state.messages = [
        Message.user(summary),
        Message.assistant([TextContent(text="Understood, I have the context from our previous conversation.")]),
    ] + recent_messages

    after_count = len(state.messages)
    state.renderer.console.print()
    state.renderer.console.print(
        f"  [bold green]✓[/bold green] Compacted: {before_count} → {after_count} messages"
    )
    state.renderer.console.print()


def _cmd_yolo(state: "REPLState") -> None:
    """Toggle yolo mode — auto-approve all tool calls."""
    state.yolo_mode = not state.yolo_mode
    if state.yolo_mode:
        state.permissions.add_session_rule("*", "*", "allow")
        state.renderer.render_info("YOLO mode: ON — all tools auto-approved ⚡")
    else:
        # Remove the wildcard session rule
        state.permissions._session_rules = [
            r for r in state.permissions._session_rules
            if not (r.tool_name == "*" and r.pattern == "*")
        ]
        state.renderer.render_info("YOLO mode: OFF — permission prompts restored")


def _cmd_resume(state: "REPLState", arg: str) -> None:
    """Resume a previous session — show numbered list for selection."""
    import asyncio
    from abu_cli.sessions import list_sessions, load_session, restore_messages

    sessions = list_sessions(limit=10)
    if not sessions:
        state.renderer.render_info("No saved sessions.")
        return

    # If arg is a number, select by index
    if arg and arg.strip().isdigit():
        idx = int(arg.strip()) - 1
        if 0 <= idx < len(sessions):
            arg = sessions[idx]["id"]
        else:
            state.renderer.render_error(f"Invalid number. Choose 1-{len(sessions)}")
            return

    if not arg:
        # Show numbered list
        state.renderer.console.print()
        state.renderer.console.print("[bold]Recent sessions:[/bold]")
        state.renderer.console.print()
        for i, s in enumerate(sessions, 1):
            ts = s.get("updated_at", "")[:16].replace("T", " ")
            cwd_short = s.get("cwd", "").replace(str(Path.home()), "~")
            # Extract first user message as preview
            session_data = load_session(s["id"])
            preview = ""
            if session_data:
                for m in session_data.get("messages", []):
                    if m.get("role") == "user":
                        preview = m.get("content", "")[:40]
                        if len(m.get("content", "")) > 40:
                            preview += "…"
                        break

            state.renderer.console.print(
                f"  [bold cyan]{i}.[/bold cyan] [dim]{ts}[/dim]  "
                f"{s['turns']} turns  [dim]{cwd_short}[/dim]"
            )
            if preview:
                state.renderer.console.print(
                    f"     [dim]› {preview}[/dim]"
                )
        state.renderer.console.print()
        state.renderer.console.print(
            "[dim]Type [bold]/resume <number>[/bold] to restore (e.g. /resume 1)[/dim]"
        )
        state.renderer.console.print()
        return

    # Resume specific session
    session_data = load_session(arg.strip())
    if not session_data:
        state.renderer.render_error(f"Session not found: {arg}")
        return

    state.messages = restore_messages(session_data)
    state.session_id = session_data.get("id", arg.strip())
    state.total_cost = session_data.get("cost", 0.0)

    turns = len([m for m in state.messages if m.role == "user"])
    state.renderer.console.print()
    state.renderer.console.print(
        f"  [bold green]✓[/bold green] Resumed session [cyan]{state.session_id}[/cyan] "
        f"({turns} turns)"
    )
    state.renderer.console.print()


def _cmd_mcp(state: "REPLState") -> None:
    """Show connected MCP servers and their tools."""
    state.renderer.console.print()
    if not state.mcp_manager or not state.mcp_manager.server_info:
        state.renderer.console.print("[bold]MCP Servers:[/bold] none connected")
        state.renderer.console.print()
        state.renderer.console.print("[dim]Configure in ~/.abu/config.json:[/dim]")
        state.renderer.console.print('[dim]  "mcp_servers": {[/dim]')
        state.renderer.console.print('[dim]    "name": {"transport": "stdio", "command": ["..."]}[/dim]')
        state.renderer.console.print('[dim]  }[/dim]')
    else:
        state.renderer.console.print("[bold]MCP Servers:[/bold]")
        for name, count in state.mcp_manager.server_info.items():
            state.renderer.console.print(
                f"  [green]●[/green] {name}: {count} tools"
            )
    state.renderer.console.print()


def _cmd_context(state: "REPLState") -> None:
    state.renderer.console.print()
    state.renderer.console.print("[bold]Context Sources:[/bold]")
    state.renderer.console.print(f"  Messages: {len(state.messages)} turns")
    state.renderer.console.print(f"  Model:    {state.model}")
    state.renderer.console.print(f"  CWD:      {state.cwd}")

    from abu_cli.agent import _get_context_section
    ctx = _get_context_section(state.cwd)
    if ctx:
        lines = ctx.strip().splitlines()
        state.renderer.console.print(f"  ABU.md:   loaded ({len(lines)} lines)")
    else:
        state.renderer.console.print("  ABU.md:   [dim]not found[/dim]")
    state.renderer.console.print()
