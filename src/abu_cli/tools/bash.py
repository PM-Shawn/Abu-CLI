"""Bash tool — aligned with Claude Code's Bash tool.

Executes shell commands with timeout and output capture.
"""

from __future__ import annotations

import asyncio

from agentx.tools import tool


@tool
async def bash(command: str, timeout: int = 120000, description: str = "") -> str:
    """Execute a shell command and return stdout + stderr.

    Args:
        command: The shell command to execute.
        timeout: Timeout in milliseconds. Default 120000 (2 min), max 600000 (10 min).
        description: Brief description of what this command does (for logging).
    """
    timeout_s = min(timeout, 600000) / 1000.0

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=None,  # inherit current working directory
        )

        try:
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_s
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return (
                f"Command timed out after {timeout_s:.0f}s.\n"
                f"Command: {command}\n"
                f"Consider increasing timeout or breaking the command into steps."
            )

        output = stdout.decode("utf-8", errors="replace").rstrip()
        exit_code = proc.returncode

        # Truncate very long output
        max_chars = 50000
        if len(output) > max_chars:
            output = output[:max_chars] + f"\n\n... (output truncated, {len(output) - max_chars:,} chars omitted)"

        if exit_code == 0:
            return output if output else "(no output)"
        else:
            return f"Exit code: {exit_code}\n{output}" if output else f"Exit code: {exit_code}"

    except Exception as e:
        return f"Error executing command: {e}"
