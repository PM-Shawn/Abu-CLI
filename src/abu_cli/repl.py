"""Async REPL — Claude Code quality interactive loop.

The main loop: read input → stream agent response → render output.
Features: bottom status bar, permission system, multi-turn conversation.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PTStyle

from agentx.loop.agent import Agent
from agentx.loop.runner import Runner
from agentx.types import (
    CancellationToken,
    Message,
    Usage,
    TextContent,
)

from abu_cli.renderer import Renderer
from abu_cli.permissions import PermissionManager
from abu_cli.commands import dispatch_command


@dataclass
class REPLState:
    """Mutable state for the REPL session."""

    agent: Agent
    model: str
    cwd: Path
    renderer: Renderer
    permissions: PermissionManager
    messages: list[Message] = field(default_factory=list)
    total_cost: float = 0.0
    total_usage: Usage = field(default_factory=Usage)
    plan_mode: bool = False
    config: dict = field(default_factory=dict)
    mcp_manager: Any = None
    session_id: str = ""
    yolo_mode: bool = False
    quiet_mode: bool = False


# ── Permission prompt ───────────────────────────────────────────

def _restore_terminal_echo() -> None:
    """Re-enable terminal echo (in case it was disabled during streaming)."""
    try:
        import termios, sys
        fd = sys.stdin.fileno()
        attrs = termios.tcgetattr(fd)
        attrs[3] |= termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except Exception:
        pass


async def _prompt_permission(
    pm: PermissionManager,
    renderer: Renderer,
    tool_name: str,
    args: dict,
) -> bool:
    """Ask the user for permission to execute a tool."""
    _restore_terminal_echo()

    prompt_text = pm.format_approval_prompt(tool_name, args)
    renderer.render_permission_prompt(prompt_text)
    renderer.console.print(
        "  [dim]Allow?[/dim] "
        "[bold green]y[/bold green][dim]es[/dim] · "
        "[bold red]n[/bold red][dim]o[/dim] · "
        "[bold blue]a[/bold blue][dim]lways[/dim] · "
        "[bold yellow]s[/bold yellow][dim]ession[/dim]",
        highlight=False,
    )

    try:
        choice = await asyncio.to_thread(input, "  › ")
    except (EOFError, KeyboardInterrupt):
        return False

    choice = choice.strip().lower()

    if choice in ("y", "yes", ""):
        return True
    elif choice in ("a", "always"):
        match_value = pm._get_match_value(tool_name, args)
        pm.add_persistent_rule(tool_name, match_value, "allow")
        return True
    elif choice in ("s", "session"):
        match_value = pm._get_match_value(tool_name, args)
        pm.add_session_rule(tool_name, match_value, "allow")
        return True
    else:
        return False


# ── Permission wrapping ─────────────────────────────────────────

def _wrap_tools_with_permissions(
    agent: Agent,
    pm: PermissionManager,
    renderer: Renderer,
) -> Agent:
    """Wrap each tool with permission checking."""
    from agentx.tools.decorator import ToolDefinition
    import inspect

    wrapped_tools = []
    for td in agent.tools:
        tool_name = td.name

        if tool_name in ("read_file", "glob_search", "grep_search", "web_search"):
            wrapped_tools.append(td)
            continue

        orig = td._func
        tname = tool_name

        async def permission_wrapper(_orig=orig, _tname=tname, **kwargs):
            decision = pm.check(_tname, kwargs)
            if decision == "deny":
                return f"Permission denied for {_tname}."
            elif decision == "ask":
                allowed = await _prompt_permission(pm, renderer, _tname, kwargs)
                if not allowed:
                    return f"User denied permission for {_tname}."

            if inspect.iscoroutinefunction(_orig):
                return await _orig(**kwargs)
            else:
                return _orig(**kwargs)

        new_td = ToolDefinition(
            permission_wrapper,
            name=td.name,
            description=td.description,
        )
        new_td._schema = td._schema
        wrapped_tools.append(new_td)

    return Agent(
        name=agent.name,
        instructions=agent.instructions,
        model=agent.model,
        tools=wrapped_tools,
        max_tokens=agent.max_tokens,
        retry_policy=agent.retry_policy,
        hooks=agent.hooks,
    )


# ── Turn processing ─────────────────────────────────────────────

async def _process_turn(state: REPLState, user_input: str) -> None:
    """Process one conversation turn: send to model, stream response."""
    state.messages.append(Message.user(user_input))

    token = CancellationToken()
    original_handler = signal.getsignal(signal.SIGINT)

    def cancel_handler(sig, frame):
        token.cancel()
        state.renderer.render_info("\n  Cancelling...")

    signal.signal(signal.SIGINT, cancel_handler)

    try:
        stream = Runner.stream(
            state.agent,
            state.messages,
            cancellation_token=token,
        )
        done = await state.renderer.render_stream(stream)

        if done:
            state.total_cost += done.cost_usd
            state.total_usage = Usage(
                input_tokens=state.total_usage.input_tokens + done.usage.input_tokens,
                output_tokens=state.total_usage.output_tokens + done.usage.output_tokens,
                cache_read_tokens=state.total_usage.cache_read_tokens + done.usage.cache_read_tokens,
                cache_write_tokens=state.total_usage.cache_write_tokens + done.usage.cache_write_tokens,
            )

            if done.final_output:
                state.messages.append(
                    Message.assistant([TextContent(text=done.final_output)])
                )

            # Context window warning
            total_tokens = done.usage.input_tokens + done.usage.output_tokens
            if total_tokens > 100_000:
                state.renderer.console.print(
                    f"  [bold yellow]⚠ Context: {total_tokens:,} tokens — "
                    f"consider /compact to reduce[/bold yellow]"
                )
            elif total_tokens > 50_000:
                state.renderer.console.print(
                    f"  [dim yellow]Context: {total_tokens:,} tokens[/dim yellow]"
                )

            # Auto-save session
            if state.session_id:
                from abu_cli.sessions import save_session
                try:
                    save_session(
                        state.session_id,
                        state.messages,
                        state.model,
                        str(state.cwd),
                        state.total_cost,
                    )
                except Exception:
                    pass

    except Exception as e:
        state.renderer.render_error(str(e))
    finally:
        signal.signal(signal.SIGINT, original_handler)


# ── Main REPL ───────────────────────────────────────────────────

def _make_bottom_toolbar(state: REPLState) -> HTML:
    """Bottom status bar."""
    turns = len([m for m in state.messages if m.role == "user"])
    cost = f"${state.total_cost:.4f}" if state.total_cost > 0 else "$0"
    yolo = " · <ansired><b>YOLO</b></ansired>" if state.yolo_mode else ""
    return HTML(
        f'<b>/help</b> for commands'
        f'{yolo}'
        f'                    '
        f'<ansiyellow>{state.model}</ansiyellow> · cost: {cost}'
    )


# prompt-toolkit style
PT_STYLE = PTStyle.from_dict({
    "bottom-toolbar": "noinherit",
    "bottom-toolbar.text": "#888888",
})


def _make_key_bindings() -> KeyBindings:
    """Key bindings: Enter=submit, Shift+Enter/Option+Enter=newline."""
    kb = KeyBindings()

    @kb.add("escape", "enter")
    def _(event):
        """Alt+Enter / Option+Enter → insert newline."""
        event.current_buffer.insert_text("\n")

    return kb


async def start(state: REPLState, initial_prompt: str | None = None) -> None:
    """Main REPL loop."""
    from abu_cli import __version__
    from abu_cli.sessions import generate_session_id

    # Assign session ID for auto-save
    if not state.session_id:
        state.session_id = generate_session_id()

    # Wrap tools with permissions
    state.agent = _wrap_tools_with_permissions(
        state.agent, state.permissions, state.renderer
    )

    if not state.quiet_mode:
        state.renderer.render_welcome(
            model=state.model,
            cwd=str(state.cwd),
            version=__version__,
        )

    # Handle initial prompt
    if initial_prompt:
        await _process_turn(state, initial_prompt)

    # Setup history
    history_dir = Path.home() / ".abu"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_file = history_dir / "history"

    # Auto-complete for slash commands
    from abu_cli.commands import COMMANDS
    cmd_completer = WordCompleter(
        list(COMMANDS.keys()),
        sentence=True,  # complete whole command
    )

    session: PromptSession = PromptSession(
        history=FileHistory(str(history_file)),
        bottom_toolbar=lambda: _make_bottom_toolbar(state),
        style=PT_STYLE,
        key_bindings=_make_key_bindings(),
        multiline=False,
        completer=cmd_completer,
        complete_while_typing=False,  # only complete on Tab
    )

    while True:
        try:
            user_input = await session.prompt_async("› ")
        except EOFError:
            state.renderer.render_info("Goodbye!")
            break
        except KeyboardInterrupt:
            continue

        user_input = user_input.strip()
        if not user_input:
            continue

        # Move cursor up and overwrite the prompt line with styled version
        sys.stdout.write("\033[A\033[2K")  # up one line, clear it
        sys.stdout.flush()
        state.renderer.render_user_message(user_input)

        if user_input.startswith("/"):
            try:
                await dispatch_command(user_input, state)
            except SystemExit:
                state.renderer.render_info("Goodbye!")
                break
            continue

        await _process_turn(state, user_input)
