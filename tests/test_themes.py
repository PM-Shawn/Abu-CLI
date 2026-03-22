"""Tests for theme system."""

from abu_cli.themes import get_theme, list_themes, THEMES


def test_list_themes():
    themes = list_themes()
    assert "default" in themes
    assert "dark" in themes
    assert "ocean" in themes
    assert "rose" in themes
    assert "mono" in themes


def test_get_theme():
    theme = get_theme("ocean")
    assert theme.name == "ocean"
    assert theme.brand_color
    assert theme.ai_bullet


def test_get_unknown_theme_falls_back():
    theme = get_theme("nonexistent")
    assert theme.name == "default"


def test_all_themes_have_required_fields():
    for name, theme in THEMES.items():
        assert theme.brand_color, f"{name} missing brand_color"
        assert theme.ai_bullet, f"{name} missing ai_bullet"
        assert theme.tool_name, f"{name} missing tool_name"
        assert theme.error, f"{name} missing error"
