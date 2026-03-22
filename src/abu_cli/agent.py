"""Agent construction — dynamic system prompt aligned with Claude Code patterns."""

from __future__ import annotations

import os
import platform
from pathlib import Path

from agentx.loop.agent import Agent
from agentx.loop.hooks import RunHooks, RunContext
from agentx.loop.retry import RetryPolicy
from agentx.types import Usage

from abu_cli.tools import ALL_TOOLS, READ_ONLY_TOOLS


SYSTEM_PROMPT_TEMPLATE = """\
You are Abu, an expert AI coding assistant running in the user's terminal. \
You help with any programming task: writing code, fixing bugs, \
refactoring, debugging, explaining code, running tests, and more. \
When asked who you are, introduce yourself as Abu.

# Working Environment
- Working directory: {cwd}
- Platform: {platform}
- Shell: {shell}

# Tool Usage Guidelines
- Read files before modifying them. Use read_file to understand code before making changes.
- Prefer edit_file over write_file for existing files — it sends only the diff.
- Use glob_search to find files by pattern before using grep_search for content.
- Use grep_search to find relevant code when you don't know which file to look in.
- Run bash commands after edits to verify changes work (tests, linters, build).
- Chain multiple edit_file calls for coordinated changes across files.

# Coding Standards
- Write clean, simple, correct code. Don't over-engineer.
- Don't add features, refactoring, or "improvements" beyond what was asked.
- Be careful not to introduce security vulnerabilities.
- Only add comments where the logic isn't self-evident.
- Keep solutions focused and minimal.

# Output Style
- Be concise. Lead with the answer or action, not the reasoning.
- Use GitHub-flavored Markdown for formatting.
- When referencing code, include file_path:line_number.
{context_section}\
{todo_section}\
"""


def _get_context_section(cwd: Path) -> str:
    """Load ABU.md project context (like Claude Code's CLAUDE.md)."""
    # Search upward for ABU.md
    current = cwd
    for _ in range(20):
        md_path = current / "ABU.md"
        if md_path.exists():
            try:
                text = md_path.read_text(encoding="utf-8")
                # Limit to first 200 lines
                lines = text.splitlines()[:200]
                content = "\n".join(lines)
                return f"\n# Project Context (ABU.md)\n{content}\n"
            except Exception:
                pass

        # Also check .agentx/context.md
        ctx_path = current / ".agentx" / "context.md"
        if ctx_path.exists():
            try:
                text = ctx_path.read_text(encoding="utf-8")
                lines = text.splitlines()[:200]
                content = "\n".join(lines)
                return f"\n# Project Context\n{content}\n"
            except Exception:
                pass

        parent = current.parent
        if parent == current:
            break

        # Stop at project root markers
        if (current / ".git").exists() or (current / "pyproject.toml").exists():
            break
        current = parent

    return ""


def _get_todo_section() -> str:
    """Placeholder for TodoWrite state injection."""
    return ""


def build_agent(
    model: str = "claude-sonnet-4-6",
    cwd: Path | None = None,
    plan_mode: bool = False,
    hooks: RunHooks | None = None,
) -> Agent:
    """Build the coding agent with dynamic system prompt.

    Args:
        model: Model name (resolved via ModelRegistry).
        cwd: Working directory. Defaults to os.getcwd().
        plan_mode: If True, only include read-only tools.
        hooks: Optional lifecycle hooks.
    """
    if cwd is None:
        cwd = Path.cwd()

    def dynamic_instructions(ctx: dict | None = None) -> str:
        context_section = _get_context_section(cwd)
        todo_section = _get_todo_section()
        plan_note = ""
        if plan_mode:
            plan_note = (
                "\n# PLAN MODE (READ-ONLY)\n"
                "You are in read-only plan mode. Explore the codebase and create "
                "implementation plans. Do NOT modify any files or run destructive commands.\n"
            )

        return SYSTEM_PROMPT_TEMPLATE.format(
            cwd=str(cwd),
            platform=platform.system(),
            shell=os.environ.get("SHELL", "unknown"),
            context_section=context_section + plan_note,
            todo_section=todo_section,
        )

    tools = READ_ONLY_TOOLS if plan_mode else ALL_TOOLS

    return Agent(
        name="Abu",
        instructions=dynamic_instructions,
        model=model,
        tools=tools,
        max_tokens=8192,
        retry_policy=RetryPolicy(max_attempts=3),
        hooks=hooks,
    )
