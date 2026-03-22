"""Session persistence — save and restore conversations.

Sessions are stored as JSON files in ~/.abu/sessions/.
Each session contains: messages, model, cwd, timestamp.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from agentx.types import Message, TextContent, ToolUseContent, ToolResultContent

SESSIONS_DIR = Path.home() / ".abu" / "sessions"


def _ensure_dir() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def save_session(
    session_id: str,
    messages: list[Message],
    model: str,
    cwd: str,
    cost: float = 0.0,
) -> Path:
    """Save a session to disk."""
    _ensure_dir()

    data = {
        "id": session_id,
        "model": model,
        "cwd": cwd,
        "cost": cost,
        "updated_at": datetime.now().isoformat(),
        "turn_count": len([m for m in messages if m.role == "user"]),
        "messages": [_serialize_message(m) for m in messages],
    }

    path = SESSIONS_DIR / f"{session_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return path


def load_session(session_id: str) -> dict | None:
    """Load a session from disk. Returns None if not found."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def restore_messages(session_data: dict) -> list[Message]:
    """Convert saved session data back to Message objects."""
    messages = []
    for m in session_data.get("messages", []):
        role = m.get("role", "user")
        content = m.get("content", "")

        if role == "user":
            messages.append(Message.user(content))
        elif role == "assistant":
            messages.append(Message.assistant([TextContent(text=content)]))

    return messages


def list_sessions(limit: int = 10) -> list[dict]:
    """List recent sessions, sorted by updated_at desc."""
    _ensure_dir()
    sessions = []

    for path in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            sessions.append({
                "id": data.get("id", path.stem),
                "model": data.get("model", "?"),
                "cwd": data.get("cwd", "?"),
                "turns": data.get("turn_count", 0),
                "cost": data.get("cost", 0),
                "updated_at": data.get("updated_at", ""),
            })
        except Exception:
            continue

    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions[:limit]


def generate_session_id() -> str:
    """Generate a short session ID based on timestamp."""
    return f"s-{int(time.time())}"


# ── Serialization helpers ───────────────────────────────────────

def _serialize_message(msg: Message) -> dict:
    """Serialize a Message to a JSON-safe dict."""
    if msg.role == "user":
        # User messages: extract text
        if isinstance(msg.content, str):
            return {"role": "user", "content": msg.content}
        elif isinstance(msg.content, list):
            texts = []
            for block in msg.content:
                if isinstance(block, TextContent):
                    texts.append(block.text)
                elif hasattr(block, "text"):
                    texts.append(block.text)
            return {"role": "user", "content": " ".join(texts)}
        return {"role": "user", "content": str(msg.content)}

    elif msg.role == "assistant":
        # Assistant messages: extract text content only
        if isinstance(msg.content, list):
            texts = []
            for block in msg.content:
                if isinstance(block, TextContent):
                    texts.append(block.text)
            return {"role": "assistant", "content": " ".join(texts)}
        return {"role": "assistant", "content": str(msg.content)}

    return {"role": msg.role, "content": str(msg.content)}
