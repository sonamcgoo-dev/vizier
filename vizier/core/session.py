"""
Session management — ties together the LLM provider, tools, and conversation
history for a single agent session.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from vizier.config import Config
from vizier.core.types import Message

log = logging.getLogger("vizier.session")


@dataclass
class Session:
    """Represents a single agent session (conversation + metadata)."""

    id: str
    name: str
    created: str
    updated: str
    messages: list[dict] = field(default_factory=list)
    model_path: str = ""
    config_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created": self.created,
            "updated": self.updated,
            "messages": self.messages,
            "model_path": self.model_path,
            "config_snapshot": self.config_snapshot,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Session:
        return cls(
            id=d.get("id", ""),
            name=d.get("name", "Untitled"),
            created=d.get("created", ""),
            updated=d.get("updated", ""),
            messages=d.get("messages", []) or [],
            model_path=d.get("model_path", ""),
            config_snapshot=d.get("config_snapshot", {}) or {},
        )


class SessionManager:
    """Manages creation, listing, and persistence of agent sessions."""

    def __init__(self, sessions_dir: str | Path | None = None):
        from vizier.utils import get_data_dir

        self.sessions_dir = (
            Path(sessions_dir) if sessions_dir else get_data_dir() / "sessions"
        )
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, Session] = {}

    def create(
        self,
        name: str = "New Session",
        model_path: str = "",
        config: Config | None = None,
    ) -> Session:
        import uuid

        sid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        session = Session(
            id=sid,
            name=name,
            created=now,
            updated=now,
            model_path=model_path,
            config_snapshot=config.to_dict() if config else {},
        )
        self._sessions[sid] = session
        self._save(session)
        return session

    def load(self, session_id: str) -> Session | None:
        if session_id in self._sessions:
            return self._sessions[session_id]
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Could not load session %s: %s", path, exc)
            return None
        session = Session.from_dict(data)
        self._sessions[session_id] = session
        return session

    def list_sessions(self) -> list[Session]:
        sessions: list[Session] = []
        for f in sorted(self.sessions_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append(Session.from_dict(data))
            except Exception as exc:
                log.warning("Could not load session %s: %s", f, exc)
        sessions.sort(key=lambda s: s.updated, reverse=True)
        return sessions

    def save(self, session_id: str, messages: list[Message]) -> None:
        session = self._sessions.get(session_id) or self.load(session_id)
        if session is None:
            log.warning("Attempted to save unknown session %s", session_id)
            return
        session.messages = [m.to_dict() for m in messages]
        session.updated = datetime.now().isoformat()
        self._save(session)

    def _save(self, session: Session) -> None:
        path = self.sessions_dir / f"{session.id}.json"
        payload = json.dumps(session.to_dict(), indent=2, ensure_ascii=False)
        temp_path = path.with_name(path.name + ".tmp")
        temp_path.write_text(payload, encoding="utf-8")
        os.replace(temp_path, path)

    def delete(self, session_id: str) -> bool:
        path = self.sessions_dir / f"{session_id}.json"
        self._sessions.pop(session_id, None)
        if path.exists():
            path.unlink()
            return True
        return False

    def rename(self, session_id: str, new_name: str) -> bool:
        session = self._sessions.get(session_id) or self.load(session_id)
        if session is None:
            return False
        session.name = new_name
        session.updated = datetime.now().isoformat()
        self._save(session)
        return True
