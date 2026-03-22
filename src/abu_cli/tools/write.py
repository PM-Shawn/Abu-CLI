"""Write tool — aligned with Claude Code's Write tool.

Creates or overwrites files. Enforces read-before-write safety.
"""

from __future__ import annotations

from pathlib import Path

from agentx.tools import tool

import abu_cli.tools as tools_tracker


@tool
def write_file(file_path: str, content: str) -> str:
    """Create or overwrite a file with the given content.

    IMPORTANT: You must read the file first (using read_file) before overwriting
    an existing file. Prefer edit_file for modifying existing files.

    Args:
        file_path: Absolute path to the file to write.
        content: The complete content to write to the file.
    """
    p = Path(file_path).expanduser().resolve()

    # Read-before-write safety check
    if p.exists() and not tools_tracker.has_been_read(str(p)):
        return (
            f"Error: You must read {file_path} before overwriting it. "
            f"Use read_file first, or use edit_file for targeted changes."
        )

    try:
        # Create parent directories if needed
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except Exception as e:
        return f"Error writing file: {e}"

    lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
    size = len(content.encode("utf-8"))

    tools_tracker.mark_file_read(str(p))

    return f"Successfully wrote {file_path} ({lines} lines, {size:,} bytes)"
