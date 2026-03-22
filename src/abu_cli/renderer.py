"""Rich-based streaming renderer — Claude Code quality terminal UX.

Uses Rich Live + Markdown, themed colors, ● bullet markers.
"""

from __future__ import annotations

import os
import sys
import time
from typing import AsyncIterator

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.table import Table

from agentx.types import (
    StreamEvent,
    TextDeltaEvent,
    ThinkingDeltaEvent,
    ToolCallStartEvent,
    ToolCallEndEvent,
    ToolResultEvent,
    DoneEvent,
    ErrorEvent,
    HandoffEvent,
)

from abu_cli.themes import Theme, get_theme


class Renderer:
    """Renders streaming agent output to the terminal."""

    def __init__(self, console: Console | None = None, theme: Theme | None = None) -> None:
        self.console = console or Console()
        self.theme = theme or get_theme("default")
        self.compact_mode: bool = False

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme

    # ── Welcome banner ──────────────────────────────────────────────

    def render_welcome(self, model: str, cwd: str, version: str) -> None:
        """Display welcome banner — two-column panel."""
        home = os.path.expanduser("~")
        display_cwd = cwd.replace(home, "~") if cwd.startswith(home) else cwd
        t = self.theme

        left_lines = [
            "",
            f"[{t.brand_text}]Welcome to Abu![/{t.brand_text}]",
            "",
            f"[{t.dim}]{model}[/{t.dim}]",
            f"[{t.dim}]{display_cwd}[/{t.dim}]",
            "",
        ]
        left_text = Text.from_markup("\n".join(left_lines), justify="center")

        right_lines = [
            f"[bold {t.status_accent}]Tips[/bold {t.status_accent}]",
            f"Create [bold]ABU.md[/bold] for project context",
            "",
            f"[bold {t.status_accent}]Commands[/bold {t.status_accent}]",
            "[bold]/help[/bold]   Show commands",
            "[bold]/model[/bold]  Switch model",
            "[bold]/theme[/bold]  Switch theme",
        ]
        right_text = Text.from_markup("\n".join(right_lines))

        table = Table.grid(padding=(0, 2))
        table.add_column(width=36, justify="center")
        table.add_column()
        table.add_row(left_text, right_text)

        panel = Panel(
            table,
            title=f"[bold {t.brand_color}]Abu[/bold {t.brand_color}] v{version}",
            title_align="left",
            border_style=t.brand_color,
            padding=(0, 1),
        )
        self.console.print(panel)
        self.console.print()

    # ── User message ────────────────────────────────────────────────

    def render_user_message(self, text: str) -> None:
        """Render user message — bold with › prefix, full-width light background."""
        width = self.console.width
        line = f" › {text}"
        # Pad to full width and use a very subtle background
        self.console.print(
            Text(line.ljust(width), style=self.theme.user_msg_style),
            highlight=False,
        )

    # ── Terminal echo control ───────────────────────────────────────

    def _set_terminal_echo(self, enabled: bool) -> None:
        try:
            import termios
            fd = sys.stdin.fileno()
            attrs = termios.tcgetattr(fd)
            if enabled:
                attrs[3] |= termios.ECHO
            else:
                attrs[3] &= ~termios.ECHO
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
        except (ImportError, termios.error, ValueError, OSError):
            pass

    # ── Streaming renderer ──────────────────────────────────────────

    async def render_stream(
        self, stream: AsyncIterator[StreamEvent]
    ) -> DoneEvent | None:
        self._set_terminal_echo(False)
        try:
            return await self._render_stream_inner(stream)
        finally:
            self._set_terminal_echo(True)

    async def _render_stream_inner(
        self, stream: AsyncIterator[StreamEvent]
    ) -> DoneEvent | None:
        t = self.theme
        text_buffer = ""
        thinking_buffer = ""
        current_tool = ""
        done_event: DoneEvent | None = None
        pending_panels: list = []
        last_render = 0.0

        with Live(
            "",
            console=self.console,
            refresh_per_second=12,
            vertical_overflow="visible",
        ) as live:
            async for event in stream:
                if isinstance(event, ThinkingDeltaEvent):
                    thinking_buffer += event.delta
                    # Show thinking indicator
                    if len(thinking_buffer) < 20:
                        live.update(
                            Text("● thinking…", style=f"{t.dim} italic")
                        )

                elif isinstance(event, TextDeltaEvent):
                    text_buffer += event.delta
                    now = time.monotonic()
                    if now - last_render > 0.08:
                        live.update(self._build_display(text_buffer, pending_panels))
                        last_render = now

                elif isinstance(event, ToolCallStartEvent):
                    if text_buffer:
                        live.update(self._build_display(text_buffer, pending_panels))
                    current_tool = event.tool_name
                    spinner = self._make_tool_spinner(current_tool)
                    pending_panels.append(spinner)
                    live.update(self._build_display(text_buffer, pending_panels))

                elif isinstance(event, ToolCallEndEvent):
                    args = event.arguments
                    summary = self._summarize_args(current_tool, args)
                    if pending_panels:
                        pending_panels.pop()
                    tool_label = self._make_tool_label(current_tool, summary)
                    pending_panels.append(tool_label)
                    live.update(self._build_display(text_buffer, pending_panels))

                elif isinstance(event, ToolResultEvent):
                    result_line = self._make_result_line(
                        event.output, event.is_error, current_tool
                    )
                    pending_panels.append(result_line)
                    live.update(self._build_display(text_buffer, pending_panels))

                elif isinstance(event, ErrorEvent):
                    pending_panels.append(
                        Text.from_markup(
                            f"  [{t.error}]✗ Error: {event.message}[/{t.error}]"
                        )
                    )
                    live.update(self._build_display(text_buffer, pending_panels))

                elif isinstance(event, HandoffEvent):
                    pending_panels.append(
                        Text.from_markup(
                            f"  [magenta]→ {event.from_agent} → {event.to_agent}[/magenta]"
                        )
                    )
                    live.update(self._build_display(text_buffer, pending_panels))

                elif isinstance(event, DoneEvent):
                    done_event = event

            live.update(self._build_display(text_buffer, pending_panels, final=True))

        if done_event:
            usage = done_event.usage
            cost = done_event.cost_usd
            self.console.print(
                f"  [{t.dim}]tokens: {usage.input_tokens:,}/{usage.output_tokens:,}"
                f" | cost: ${cost:.4f}[/{t.dim}]",
                highlight=False,
            )
            self.console.print()

        return done_event

    def _build_display(self, text: str, panels: list, final: bool = False):
        t = self.theme
        parts = []
        for p in panels:
            parts.append(p)
        if text:
            md = Markdown(text)
            bullet = Text("● ", style=t.ai_bullet, end="")
            parts.append(Group(bullet, md))
        elif not panels:
            parts.append(Text("● ", style=f"{t.ai_bullet} blink"))
        if not final and text:
            parts.append(Text("  ▍", style=t.brand_color))
        if not parts:
            return Text("● ", style=f"{t.ai_bullet} blink")
        return Group(*parts)

    # ── Tool display ────────────────────────────────────────────────

    def _make_tool_spinner(self, tool_name: str) -> Text:
        t = self.theme
        label = Text()
        label.append("● ", style=t.ai_bullet)
        label.append(f"{self._tool_display_name(tool_name)}", style="bold")
        label.append("  …", style=t.dim)
        return label

    def _make_tool_label(self, tool_name: str, summary: str) -> Text:
        t = self.theme
        label = Text()
        label.append("● ", style=t.ai_bullet)
        display_name = self._tool_display_name(tool_name)
        label.append(f"{display_name}", style="bold")
        if summary:
            label.append(f"({summary})", style=t.dim)
        return label

    def _make_result_line(self, output: str, is_error: bool, tool_name: str) -> Text:
        t = self.theme
        result = Text()
        result.append("  └ ", style=t.dim)
        if not output or not output.strip():
            result.append("(No output)", style=f"{t.dim} italic")
            return result
        lines = output.strip().splitlines()
        if is_error:
            first = lines[0][:100]
            result.append(first, style=t.error)
        elif self.compact_mode:
            # Compact: always show summary
            if len(lines) == 1:
                truncated = lines[0][:60] + "..." if len(lines[0]) > 60 else lines[0]
                result.append(truncated, style=t.dim)
            else:
                result.append(f"({len(lines)} lines)", style=f"{t.dim} italic")
        elif len(lines) == 1 and len(lines[0]) <= 100:
            result.append(lines[0], style=t.dim)
        else:
            result.append(f"({len(lines)} lines)", style=f"{t.dim} italic")
        return result

    def _tool_display_name(self, tool_name: str) -> str:
        names = {
            "bash": "Bash",
            "read_file": "Read",
            "write_file": "Write",
            "edit_file": "Edit",
            "glob_search": "Glob",
            "grep_search": "Grep",
            "web_search": "WebSearch",
        }
        return names.get(tool_name, tool_name)

    # ── Simple renders ──────────────────────────────────────────────

    def render_separator(self) -> None:
        self.console.print(Rule(style=self.theme.dim))

    def render_error(self, message: str) -> None:
        self.console.print(f"  [{self.theme.error}]✗ Error:[/{self.theme.error}] {message}")

    def render_info(self, message: str) -> None:
        self.console.print(f"  [{self.theme.dim}]{message}[/{self.theme.dim}]")

    def render_permission_prompt(self, text: str) -> None:
        self.console.print()
        self.console.print(f"  {text}", highlight=False)

    def _summarize_args(self, tool_name: str, args: dict) -> str:
        if tool_name == "bash":
            cmd = args.get("command", "")
            if len(cmd) > 80:
                cmd = cmd[:77] + "..."
            return cmd
        elif tool_name in ("read_file", "edit_file", "write_file"):
            return args.get("file_path", "")
        elif tool_name == "glob_search":
            return args.get("pattern", "")
        elif tool_name == "grep_search":
            return f'/{args.get("pattern", "")}/'
        elif tool_name == "web_search":
            return args.get("query", "")
        return ""
