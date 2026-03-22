"""Tests for session persistence."""

import pytest
from agentx.types import Message, TextContent

from abu_cli.sessions import (
    save_session,
    load_session,
    restore_messages,
    list_sessions,
    generate_session_id,
    SESSIONS_DIR,
)


@pytest.fixture(autouse=True)
def clean_sessions(tmp_path, monkeypatch):
    """Use temp dir for sessions."""
    monkeypatch.setattr("abu_cli.sessions.SESSIONS_DIR", tmp_path)
    yield


def test_generate_session_id():
    sid = generate_session_id()
    assert sid.startswith("s-")
    assert len(sid) > 3


def test_save_and_load():
    messages = [
        Message.user("hello"),
        Message.assistant([TextContent(text="hi there")]),
    ]
    save_session("test-1", messages, "gpt-4", "/tmp", cost=0.05)

    data = load_session("test-1")
    assert data is not None
    assert data["id"] == "test-1"
    assert data["model"] == "gpt-4"
    assert data["turn_count"] == 1
    assert len(data["messages"]) == 2


def test_restore_messages():
    messages = [
        Message.user("what is 2+2"),
        Message.assistant([TextContent(text="4")]),
    ]
    save_session("test-2", messages, "gpt-4", "/tmp")

    data = load_session("test-2")
    restored = restore_messages(data)
    assert len(restored) == 2
    assert restored[0].role == "user"
    assert restored[1].role == "assistant"


def test_list_sessions():
    for i in range(3):
        save_session(f"s-{i}", [Message.user(f"msg {i}")], "gpt-4", "/tmp")

    sessions = list_sessions(limit=10)
    assert len(sessions) == 3


def test_load_nonexistent():
    assert load_session("nonexistent") is None
