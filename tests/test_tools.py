"""Tests for built-in tools."""

import pytest
from pathlib import Path

from abu_cli.tools.read import read_file
from abu_cli.tools.write import write_file
from abu_cli.tools.edit import edit_file
from abu_cli.tools.glob_tool import glob_search
from abu_cli.tools import mark_file_read, has_been_read, reset_read_tracking


@pytest.fixture(autouse=True)
def clean_tracking():
    reset_read_tracking()
    yield
    reset_read_tracking()


@pytest.mark.asyncio
async def test_read_file(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("line1\nline2\nline3")

    result = await read_file(file_path=str(f))
    assert "line1" in result
    assert "line2" in result


@pytest.mark.asyncio
async def test_read_file_not_found():
    result = await read_file(file_path="/nonexistent/file.txt")
    assert "Error" in result or "error" in result.lower()


@pytest.mark.asyncio
async def test_write_file_requires_read(tmp_path):
    f = tmp_path / "new.txt"
    f.write_text("original")

    # Should fail without reading first
    result = await write_file(file_path=str(f), content="new content")
    assert "read" in result.lower() or "first" in result.lower()


@pytest.mark.asyncio
async def test_write_new_file(tmp_path):
    f = tmp_path / "brand_new.txt"
    result = await write_file(file_path=str(f), content="hello world")
    assert f.read_text() == "hello world"


@pytest.mark.asyncio
async def test_edit_file(tmp_path):
    f = tmp_path / "edit_me.txt"
    f.write_text("foo bar baz")
    mark_file_read(str(f))

    result = await edit_file(
        file_path=str(f),
        old_string="bar",
        new_string="qux",
    )
    assert f.read_text() == "foo qux baz"


@pytest.mark.asyncio
async def test_glob_search(tmp_path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("y")
    (tmp_path / "c.txt").write_text("z")

    result = await glob_search(pattern="*.py", path=str(tmp_path))
    assert "a.py" in result
    assert "b.py" in result
    assert "c.txt" not in result
