"""Grep tool — aligned with Claude Code's Grep tool.

Content search using ripgrep with 3 output modes.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from agentx.tools import tool


def _try_ripgrep(
    pattern: str,
    path: str,
    file_type: str,
    glob_filter: str,
    output_mode: str,
    context: int,
    head_limit: int,
) -> str | None:
    """Try using ripgrep (rg) if available. Returns None if rg not found."""
    cmd = ["rg"]

    if output_mode == "files_with_matches":
        cmd.append("-l")
    elif output_mode == "count":
        cmd.append("-c")
    else:  # content
        cmd.append("-n")  # line numbers
        if context > 0:
            cmd.extend(["-C", str(context)])

    if file_type:
        cmd.extend(["--type", file_type])
    if glob_filter:
        cmd.extend(["--glob", glob_filter])

    cmd.extend(["--max-count", "1000"])
    cmd.append(pattern)
    cmd.append(path)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 2:
            # rg error (bad pattern, etc.)
            return f"Error: {result.stderr.strip()}"

        output = result.stdout.strip()
        if not output:
            return f"No matches found for pattern '{pattern}'"

        # Apply head_limit
        lines = output.splitlines()
        if len(lines) > head_limit:
            output = "\n".join(lines[:head_limit])
            output += f"\n\n... ({len(lines) - head_limit} more results not shown)"

        return output
    except FileNotFoundError:
        return None  # rg not installed
    except subprocess.TimeoutExpired:
        return "Search timed out after 30 seconds."
    except Exception as e:
        return f"Error: {e}"


def _python_grep(
    pattern: str,
    path: str,
    output_mode: str,
    head_limit: int,
) -> str:
    """Fallback grep using Python regex."""
    base = Path(path).expanduser().resolve()

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    matches: list[str] = []
    file_counts: dict[str, int] = {}

    for fp in sorted(base.rglob("*")):
        if not fp.is_file():
            continue
        # Skip hidden/binary
        parts = fp.relative_to(base).parts
        if any(p.startswith(".") for p in parts):
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        rel = str(fp.relative_to(base))
        for i, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                if output_mode == "content":
                    matches.append(f"{rel}:{i}: {line}")
                elif output_mode == "files_with_matches":
                    if rel not in file_counts:
                        matches.append(rel)
                        file_counts[rel] = 0
                    file_counts[rel] += 1
                elif output_mode == "count":
                    file_counts[rel] = file_counts.get(rel, 0) + 1

        if len(matches) >= head_limit * 10:
            break

    if output_mode == "count":
        matches = [f"{f}:{c}" for f, c in file_counts.items()]

    if not matches:
        return f"No matches found for pattern '{pattern}'"

    if len(matches) > head_limit:
        result = "\n".join(matches[:head_limit])
        result += f"\n\n... ({len(matches) - head_limit} more results not shown)"
        return result

    return "\n".join(matches)


@tool
def grep_search(
    pattern: str,
    path: str = ".",
    type: str = "",
    glob: str = "",
    output_mode: str = "files_with_matches",
    context: int = 0,
    head_limit: int = 50,
) -> str:
    """Search file contents using regex. Built on ripgrep.

    Args:
        pattern: Regular expression pattern to search for.
        path: File or directory to search in. Default current directory.
        type: File type filter (e.g., 'py', 'js', 'rust').
        glob: Glob pattern to filter files (e.g., '*.py', '*.{ts,tsx}').
        output_mode: 'files_with_matches' (default), 'content', or 'count'.
        context: Lines of context around matches (for content mode).
        head_limit: Max results to return. Default 50.
    """
    base = Path(path).expanduser().resolve()
    if not base.exists():
        return f"Error: Path not found: {path}"

    # Try ripgrep first
    rg_result = _try_ripgrep(
        pattern, str(base), type, glob, output_mode, context, head_limit
    )
    if rg_result is not None:
        return rg_result

    # Fallback to Python
    return _python_grep(pattern, str(base), output_mode, head_limit)
