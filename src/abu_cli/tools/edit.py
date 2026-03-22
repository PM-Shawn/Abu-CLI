"""Edit tool — aligned with Claude Code's Edit tool.

Performs exact string replacement with uniqueness validation.
"""

from __future__ import annotations

from pathlib import Path

from agentx.tools import tool

import abu_cli.tools as tools_tracker


@tool
def edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    """Edit a file by replacing old_string with new_string.

    The old_string must be unique in the file (unless replace_all is True).
    You must read the file first using read_file before editing.

    Args:
        file_path: Absolute path to the file to edit.
        old_string: The exact text to find and replace. Must be unique.
        new_string: The replacement text. Must differ from old_string.
        replace_all: If True, replace all occurrences. Default False.
    """
    p = Path(file_path).expanduser().resolve()

    if not p.exists():
        return f"Error: File not found: {file_path}"

    if not tools_tracker.has_been_read(str(p)):
        return (
            f"Error: You must read {file_path} before editing it. "
            f"Use read_file first."
        )

    if old_string == new_string:
        return "Error: old_string and new_string are identical. No changes needed."

    try:
        content = p.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"

    # Count occurrences
    count = content.count(old_string)

    if count == 0:
        # Help the user find similar text
        lines = content.splitlines()
        first_words = old_string.split()[:3]
        search_hint = " ".join(first_words) if first_words else old_string[:30]
        similar = [
            f"  L{i + 1}: {line.strip()}"
            for i, line in enumerate(lines)
            if search_hint.lower() in line.lower()
        ][:5]

        msg = f"Error: old_string not found in {file_path}."
        if similar:
            msg += "\n\nSimilar lines found:\n" + "\n".join(similar)
        msg += "\n\nMake sure old_string matches exactly (including whitespace/indentation)."
        return msg

    if count > 1 and not replace_all:
        return (
            f"Error: old_string found {count} times in {file_path}. "
            f"It must be unique for a safe replacement. "
            f"Either provide more surrounding context to make it unique, "
            f"or set replace_all=True to replace all occurrences."
        )

    # Record for undo
    tools_tracker.record_change(str(p), content)

    # Perform replacement
    new_content = content.replace(old_string, new_string, -1 if replace_all else 1)

    try:
        p.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return f"Error writing file: {e}"

    # Generate diff summary
    old_lines = old_string.splitlines()
    new_lines = new_string.splitlines()
    replaced = count if replace_all else 1

    summary = f"Edited {file_path}: replaced {replaced} occurrence(s)\n"
    summary += f"  - {len(old_lines)} line(s) → {len(new_lines)} line(s)"

    return summary
