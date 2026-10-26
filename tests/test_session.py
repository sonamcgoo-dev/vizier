"""Tests for session persistence."""
from __future__ import annotations

from vizier.config import Config
from vizier.core.session import SessionManager
from vizier.core.types import Message, Role


def test_create_save_and_load(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create(name="Test", config=Config())
    assert session.id
    assert (tmp_path / f"{session.id}.json").exists()

    manager.save(session.id, [Message(role=Role.USER, content="hi")])
    loaded = manager.load(session.id)
    assert loaded is not None
    assert loaded.messages[0]["content"] == "hi"


def test_list_sessions_sorted(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    manager.create(name="One")
    manager.create(name="Two")
    sessions = manager.list_sessions()
    assert len(sessions) == 2
    assert all(s.name for s in sessions)


def test_rename_and_delete(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create(name="Old")
    assert manager.rename(session.id, "New")
    assert manager.load(session.id).name == "New"  # type: ignore[union-attr]
    assert manager.delete(session.id)
    assert manager.load(session.id) is None


def test_save_unknown_session_is_noop(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    manager.save("does-not-exist", [])
    assert manager.list_sessions() == []
