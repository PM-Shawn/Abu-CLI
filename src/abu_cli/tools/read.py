"""Read tool — aligned with Claude Code's Read tool.

Returns file contents with line numbers in cat -n format.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from agentx.tools import tool

import abu_cli.tools as tools_tracker


@tool
def read_file(file_path: str, offset: int = 0, limit: int = 2000) -> str:
    """Read a file from the filesystem. Returns content with line numbers.

    Args:
        file_path: Absolute path to the file to read.
        offset: Line number to start reading from (0-based). Default 0.
        limit: Maximum number of lines to read. Default 2000.
    """
    p = Path(file_path).expanduser().resolve()

    if not p.exists():
        return f"Error: File not found: {file_path}"
    if not p.is_file():
        return f"Error: Not a file: {file_path}"

    # Binary file detection
    mime, _ = mimetypes.guess_type(str(p))
    if mime and not mime.startswith("text") and mime != "application/json":
        size = p.stat().st_size
        return f"Binary file: {mime} ({size:,} bytes). Cannot display contents."

    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"

    lines = text.splitlines()
    total = len(lines)

    # Track that this file has been read
    tools_tracker.mark_file_read(str(p))

    # Apply offset and limit
    start = max(0, offset)
    end = min(total, start + limit)
    selected = lines[start:end]

    if not selected and total == 0:
        return f"(empty file: {file_path})"

    # Format with line numbers (cat -n style)
    width = len(str(end))
    numbered = []
    for i, line in enumerate(selected, start=start + 1):
        numbered.append(f"{i:>{width}}\t{line}")

    result = "\n".join(numbered)

    if end < total:
        result += f"\n\n... ({total - end} more lines. Use offset={end} to continue reading)"

    return result
