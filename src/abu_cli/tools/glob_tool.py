"""Glob tool — aligned with Claude Code's Glob tool.

Fast file pattern matching, sorted by modification time.
"""

from __future__ import annotations

from pathlib import Path

from agentx.tools import tool


@tool
def glob_search(pattern: str, path: str = ".") -> str:
    """Find files matching a glob pattern. Returns paths sorted by modification time.

    Args:
        pattern: Glob pattern (e.g., '**/*.py', 'src/**/*.ts').
        path: Directory to search in. Default is current directory.
    """
    base = Path(path).expanduser().resolve()

    if not base.exists():
        return f"Error: Directory not found: {path}"
    if not base.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        matches = list(base.glob(pattern))
    except Exception as e:
        return f"Error in glob pattern: {e}"

    # Filter to files only, exclude hidden/vcs directories
    files = []
    for m in matches:
        if m.is_file():
            parts = m.relative_to(base).parts
            if not any(p.startswith(".") and p not in (".", "..") for p in parts):
                files.append(m)

    if not files:
        return f"No files matching '{pattern}' in {path}"

    # Sort by modification time (most recent first)
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    # Limit results
    limit = 50
    results = []
    for f in files[:limit]:
        try:
            rel = f.relative_to(base)
        except ValueError:
            rel = f
        results.append(str(rel))

    output = "\n".join(results)
    if len(files) > limit:
        output += f"\n\n... ({len(files) - limit} more files not shown)"

    return output
