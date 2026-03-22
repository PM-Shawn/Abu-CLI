"""Theme system — switchable color schemes for Abu CLI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Theme:
    """Color scheme definition."""
    name: str
    # Welcome panel
    brand_color: str        # brand accent (panel border, bullets)
    brand_text: str         # brand name color
    # User message
    user_msg_style: str     # style for user message bar
    # AI response
    ai_bullet: str          # ● bullet color
    # Tool calls
    tool_name: str          # tool name color
    tool_icon: str          # ⚡ icon color
    tool_result_border: str # result panel border
    # Status bar
    status_accent: str      # model name color in status bar
    # General
    dim: str                # dim/secondary text
    error: str              # error color


# ── Built-in themes ─────────────────────────────────────────────

THEMES: dict[str, Theme] = {
    "default": Theme(
        name="default",
        brand_color="cyan",
        brand_text="bold white",
        user_msg_style="bold",
        ai_bullet="bold cyan",
        tool_name="bold yellow",
        tool_icon="yellow",
        tool_result_border="dim",
        status_accent="yellow",
        dim="dim",
        error="red",
    ),
    "dark": Theme(
        name="dark",
        brand_color="bright_blue",
        brand_text="bold bright_white",
        user_msg_style="bold",
        ai_bullet="bold bright_blue",
        tool_name="bold bright_yellow",
        tool_icon="bright_yellow",
        tool_result_border="bright_black",
        status_accent="bright_yellow",
        dim="bright_black",
        error="bright_red",
    ),
    "ocean": Theme(
        name="ocean",
        brand_color="dodger_blue2",
        brand_text="bold white",
        user_msg_style="bold",
        ai_bullet="bold dodger_blue2",
        tool_name="bold dark_orange3",
        tool_icon="dark_orange3",
        tool_result_border="grey50",
        status_accent="dodger_blue2",
        dim="grey50",
        error="red1",
    ),
    "rose": Theme(
        name="rose",
        brand_color="deep_pink2",
        brand_text="bold white",
        user_msg_style="bold",
        ai_bullet="bold deep_pink2",
        tool_name="bold medium_purple1",
        tool_icon="medium_purple1",
        tool_result_border="grey50",
        status_accent="deep_pink2",
        dim="grey50",
        error="red1",
    ),
    "mono": Theme(
        name="mono",
        brand_color="white",
        brand_text="bold white",
        user_msg_style="bold",
        ai_bullet="bold white",
        tool_name="bold white",
        tool_icon="white",
        tool_result_border="bright_black",
        status_accent="white",
        dim="bright_black",
        error="red",
    ),
}

DEFAULT_THEME = "default"


def get_theme(name: str) -> Theme:
    """Get a theme by name, falling back to default."""
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def list_themes() -> list[str]:
    """List available theme names."""
    return list(THEMES.keys())
