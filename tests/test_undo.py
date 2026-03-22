"""Tests for undo/change tracking."""

import pytest
from pathlib import Path

from abu_cli.tools import record_change, undo_last, get_change_count, get_recent_changes, _file_history


@pytest.fixture(autouse=True)
def clean_history():
    _file_history.clear()
    yield
    _file_history.clear()


def test_record_and_undo_edit(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("original")

    record_change(str(f), "original")
    f.write_text("modified")

    assert f.read_text() == "modified"
    result = undo_last()
    assert "Restored" in result
    assert f.read_text() == "original"


def test_undo_new_file(tmp_path):
    f = tmp_path / "new.txt"
    record_change(str(f), None)  # None = new file
    f.write_text("hello")

    result = undo_last()
    assert "Deleted" in result
    assert not f.exists()


def test_undo_empty():
    assert undo_last() is None


def test_change_count():
    assert get_change_count() == 0
    record_change("/a", "x")
    record_change("/b", "y")
    assert get_change_count() == 2


def test_recent_changes():
    record_change("/a", "x")
    record_change("/b", "y")
    record_change("/c", "z")

    recent = get_recent_changes(2)
    assert len(recent) == 2
    assert recent[0]["path"] == "/c"  # most recent first
    assert recent[1]["path"] == "/b"
