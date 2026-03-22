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


def mark_file_read(path: str) -> None:
    _read_files.add(str(path))


def has_been_read(path: str) -> bool:
    return str(path) in _read_files


def reset_read_tracking() -> None:
    _read_files.clear()
