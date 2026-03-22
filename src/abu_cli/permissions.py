"""Permission system — aligned with Claude Code's permission model.

Implements allow/ask/deny rules with wildcard matching.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PermissionRule:
    tool_name: str  # e.g., "bash", "edit_file", "*"
    pattern: str  # e.g., "git *", "/safe/path/*", "*"
    action: str  # "allow" or "deny"
    scope: str = "session"  # "session" or "always"


class PermissionManager:
    """Manages tool execution permissions."""

    DEFAULT_RULES: list[tuple[str, str, str]] = [
        # ── Catch-all defaults (lowest priority, checked last) ──
        ("bash", "*", "ask"),
        ("write_file", "*", "ask"),
        ("edit_file", "*", "ask"),
        # ── Read-only tools: always allow ──
        ("read_file", "*", "allow"),
        ("glob_search", "*", "allow"),
        ("grep_search", "*", "allow"),
        # ── Safe bash commands (higher priority, checked first) ──
        ("bash", "git status*", "allow"),
        ("bash", "git diff*", "allow"),
        ("bash", "git log*", "allow"),
        ("bash", "git branch*", "allow"),
        ("bash", "git show*", "allow"),
        ("bash", "ls*", "allow"),
        ("bash", "cat *", "allow"),
        ("bash", "head *", "allow"),
        ("bash", "tail *", "allow"),
        ("bash", "pwd", "allow"),
        ("bash", "echo *", "allow"),
        ("bash", "which *", "allow"),
        ("bash", "type *", "allow"),
        ("bash", "wc *", "allow"),
        ("bash", "find *", "allow"),
        ("bash", "python*--version*", "allow"),
        ("bash", "node*--version*", "allow"),
        ("bash", "uv *", "allow"),
        ("bash", "npm list*", "allow"),
        ("bash", "pip list*", "allow"),
        ("bash", "tree*", "allow"),
        ("bash", "file *", "allow"),
        ("bash", "du *", "allow"),
        ("bash", "df *", "allow"),
    ]

    def __init__(self) -> None:
        self._rules: list[PermissionRule] = []
        self._session_rules: list[PermissionRule] = []

        # Load default rules
        for tool_name, pattern, action in self.DEFAULT_RULES:
            self._rules.append(PermissionRule(tool_name, pattern, action))

    def check(self, tool_name: str, args: dict) -> str:
        """Check if a tool call is allowed.

        Returns: 'allow', 'deny', or 'ask'
        """
        # Get the value to match against (command for bash, path for file tools)
        match_value = self._get_match_value(tool_name, args)

        # Check session rules first (higher priority)
        for rule in reversed(self._session_rules):
            if self._matches(rule, tool_name, match_value):
                return rule.action

        # Then check persistent rules
        for rule in reversed(self._rules):
            if self._matches(rule, tool_name, match_value):
                return rule.action

        return "ask"  # Default: ask

    def add_session_rule(self, tool_name: str, pattern: str, action: str) -> None:
        """Add a rule that lasts for this session only."""
        self._session_rules.append(
            PermissionRule(tool_name, pattern, action, scope="session")
        )

    def add_persistent_rule(self, tool_name: str, pattern: str, action: str) -> None:
        """Add a rule that persists across sessions."""
        self._rules.append(
            PermissionRule(tool_name, pattern, action, scope="always")
        )

    def _get_match_value(self, tool_name: str, args: dict) -> str:
        """Extract the value to match against from tool arguments."""
        if tool_name == "bash":
            return args.get("command", "")
        elif tool_name in ("read_file", "write_file", "edit_file"):
            return args.get("file_path", "")
        elif tool_name == "glob_search":
            return args.get("pattern", "")
        elif tool_name == "grep_search":
            return args.get("pattern", "")
        return ""

    def _matches(self, rule: PermissionRule, tool_name: str, value: str) -> bool:
        """Check if a rule matches the given tool call."""
        if rule.tool_name != "*" and rule.tool_name != tool_name:
            return False
        return fnmatch.fnmatch(value, rule.pattern)

    def format_approval_prompt(self, tool_name: str, args: dict) -> str:
        """Format a compact approval prompt — Claude Code style."""
        names = {"bash": "Bash", "edit_file": "Edit", "write_file": "Write"}
        display = names.get(tool_name, tool_name)

        if tool_name == "bash":
            cmd = args.get("command", "?")
            if len(cmd) > 100:
                cmd = cmd[:97] + "..."
            return f"[bold]{display}[/bold]([dim]{cmd}[/dim])"
        elif tool_name == "edit_file":
            path = args.get("file_path", "?")
            return f"[bold]{display}[/bold]([dim]{path}[/dim])"
        elif tool_name == "write_file":
            path = args.get("file_path", "?")
            content = args.get("content", "")
            lines = content.count("\n") + 1
            return f"[bold]{display}[/bold]([dim]{path}, {lines} lines[/dim])"
        else:
            return f"[bold]{display}[/bold]"

    def save(self, path: Path) -> None:
        """Save persistent rules to JSON."""
        rules = [
            {"tool": r.tool_name, "pattern": r.pattern, "action": r.action}
            for r in self._rules
            if r.scope == "always"
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rules, indent=2))

    def load(self, path: Path) -> None:
        """Load persistent rules from JSON."""
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            for r in data:
                self._rules.append(
                    PermissionRule(r["tool"], r["pattern"], r["action"], "always")
                )
        except Exception:
            pass
