"""CLI entry point — the `Abu` command."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click

from abu_cli.agent import build_agent
from abu_cli.permissions import PermissionManager
from abu_cli.renderer import Renderer
from abu_cli.repl import REPLState, start

CONFIG_DIR = Path.home() / ".abu"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _register_providers_from_config(config: dict) -> None:
    from agentx.providers.registry import ModelRegistry
    from agentx.providers.claude import ClaudeProvider
    from agentx.providers.openai import OpenAIProvider

    providers = config.get("providers", {})
    for prefix, prov_cfg in providers.items():
        api_key = prov_cfg.get("api_key")
        base_url = prov_cfg.get("base_url")
        fmt = prov_cfg.get("format", "anthropic")
        if not api_key:
            continue
        if fmt == "anthropic":
            def _factory(m, _key=api_key, _url=base_url):
                return ClaudeProvider(model=m, api_key=_key, base_url=_url)
            ModelRegistry.register(prefix, _factory)
        elif fmt == "openai":
            def _factory(m, _key=api_key, _url=base_url):
                return OpenAIProvider(model=m, api_key=_key, base_url=_url)
            ModelRegistry.register(prefix, _factory)


def _ensure_project_dir(cwd: Path) -> None:
    """Auto-create .abu/ project directory (like Claude Code's .claude/)."""
    abu_dir = cwd / ".abu"
    if not abu_dir.exists():
        abu_dir.mkdir(parents=True, exist_ok=True)
        # Create default project settings
        settings = {
            "version": "0.1.0",
            "permissions": [],
            "notes": "Project-specific Abu settings. Add to .gitignore if needed.",
        }
        (abu_dir / "settings.json").write_text(
            json.dumps(settings, indent=2, ensure_ascii=False)
        )


@click.command(context_settings={"ignore_unknown_options": True})
@click.argument("prompt", required=False, nargs=-1)
@click.option("-m", "--model", default=None, help="Model to use")
@click.option("-p", "--print", "pipe_mode", is_flag=True, help="Print and exit")
@click.option("-r", "--resume", "resume_id", default=None, help="Resume session by ID")
@click.option("-c", "--continue", "continue_last", is_flag=True, help="Continue last session")
@click.option("--yolo", is_flag=True, help="Auto-approve all tool calls (no permission prompts)")
@click.option("-q", "--quiet", is_flag=True, help="Minimal output (no welcome banner)")
def main(
    prompt: tuple[str, ...],
    model: str | None,
    pipe_mode: bool,
    resume_id: str | None,
    continue_last: bool,
    yolo: bool,
    quiet: bool,
) -> None:
    """Abu — Interactive AI coding assistant, powered by AgentX.

    \b
    Examples:
        abu                          # interactive REPL
        abu "fix the login bug"      # start with a prompt
        abu -p "explain main.py"     # pipe mode
        abu --resume s-1742672400    # resume session
        abu -c                       # continue last session
        abu --yolo "refactor this"   # auto-approve everything
    """
    config = _load_config()
    _register_providers_from_config(config)

    if model is None:
        model = config.get("model", "claude-sonnet-4-6")

    cwd = Path.cwd()
    initial_prompt = " ".join(prompt) if prompt else None

    # Pipe input: cat file.py | abu "explain this"
    if not sys.stdin.isatty():
        stdin_text = sys.stdin.read().strip()
        if stdin_text:
            if initial_prompt:
                initial_prompt = f"{initial_prompt}\n\n```\n{stdin_text}\n```"
            else:
                initial_prompt = stdin_text
            pipe_mode = True  # auto pipe mode when stdin is piped

    # Auto-create .abu/ project directory
    _ensure_project_dir(cwd)

    agent = build_agent(model=model, cwd=cwd)

    from abu_cli.themes import get_theme
    theme_name = config.get("theme", "default")
    renderer = Renderer(theme=get_theme(theme_name))

    permissions = PermissionManager()
    perm_path = CONFIG_DIR / "permissions.json"
    permissions.load(perm_path)

    # Yolo mode: auto-approve everything
    if yolo:
        permissions.add_session_rule("*", "*", "allow")

    state = REPLState(
        agent=agent,
        model=model,
        cwd=cwd,
        renderer=renderer,
        permissions=permissions,
        config=config,
        yolo_mode=yolo,
        quiet_mode=quiet,
    )

    # Handle --resume / --continue
    if resume_id or continue_last:
        from abu_cli.sessions import load_session, restore_messages, list_sessions
        if continue_last:
            sessions = list_sessions(limit=1)
            if sessions:
                resume_id = sessions[0]["id"]
        if resume_id:
            session_data = load_session(resume_id)
            if session_data:
                state.messages = restore_messages(session_data)
                state.session_id = resume_id
                state.total_cost = session_data.get("cost", 0.0)

    if pipe_mode and initial_prompt:
        asyncio.run(_pipe_mode(state, initial_prompt))
    else:
        try:
            asyncio.run(_run_with_mcp(state, config, initial_prompt))
        except KeyboardInterrupt:
            renderer.render_info("\nGoodbye!")


async def _run_with_mcp(
    state: REPLState,
    config: dict,
    initial_prompt: str | None,
) -> None:
    """Start REPL with MCP server lifecycle management."""
    from abu_cli.mcp_manager import MCPManager

    mcp = MCPManager()
    state.mcp_manager = mcp

    try:
        await mcp.connect_from_config(
            config,
            project_dir=state.cwd,
            renderer=state.renderer,
        )

        if mcp.tools:
            all_tools = list(state.agent.tools) + mcp.tools
            from agentx.loop.agent import Agent
            state.agent = Agent(
                name=state.agent.name,
                instructions=state.agent.instructions,
                model=state.agent.model,
                tools=all_tools,
                max_tokens=state.agent.max_tokens,
                retry_policy=state.agent.retry_policy,
                hooks=state.agent.hooks,
            )

        await start(state, initial_prompt)
    finally:
        await mcp.disconnect_all()


async def _pipe_mode(state: REPLState, prompt: str) -> None:
    from agentx.loop.runner import Runner
    from agentx.types import Message
    messages = [Message.user(prompt)]
    result = await Runner.run(state.agent, messages)
    print(result.final_output)


if __name__ == "__main__":
    main()
