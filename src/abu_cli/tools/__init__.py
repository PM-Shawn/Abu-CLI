"""Abu built-in tools — aligned with Claude Code's tool system."""

from abu_cli.tools.read import read_file
from abu_cli.tools.write import write_file
from abu_cli.tools.edit import edit_file
from abu_cli.tools.bash import bash
from abu_cli.tools.glob_tool import glob_search
from abu_cli.tools.grep import grep_search
from abu_cli.tools.web_search import web_search

ALL_TOOLS = [read_file, write_file, edit_file, bash, glob_search, grep_search, web_search]
READ_ONLY_TOOLS = [read_file, glob_search, grep_search, web_search]

# Track which files have been read (for read-before-write validation)
_read_files: set[str] = set()

# Track file changes for /undo (path -> previous content or None if new file)
_file_history: list[dict] = []


def mark_file_read(path: str) -> None:
    _read_files.add(str(path))


def has_been_read(path: str) -> bool:
    return str(path) in _read_files


def reset_read_tracking() -> None:
    _read_files.clear()


def record_change(path: str, old_content: str | None) -> None:
    """Record a file change for undo. old_content=None means new file."""
    _file_history.append({"path": path, "old_content": old_content})


def undo_last() -> str | None:
    """Undo the last file change. Returns description or None."""
    if not _file_history:
        return None
    change = _file_history.pop()
    path = change["path"]
    old = change["old_content"]
    from pathlib import Path
    p = Path(path)
    if old is None:
        # Was a new file — delete it
        if p.exists():
            p.unlink()
            return f"Deleted {path} (was newly created)"
    else:
        p.write_text(old, encoding="utf-8")
        return f"Restored {path}"
    return None


def get_change_count() -> int:
    return len(_file_history)


def get_recent_changes(n: int = 5) -> list[dict]:
    return list(reversed(_file_history[-n:]))
