"""Tests for rotating logs, startup banners, and log-tail helpers."""
from __future__ import annotations

import logging
import logging.handlers

import pytest

import vizier.logging_setup as logging_setup


@pytest.fixture()
def log_env(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_setup, "get_data_dir", lambda: tmp_path)
    root = logging.getLogger()
    previous_level = root.level
    logging_setup.reset_logging()
    before = set(root.handlers)
    try:
        yield logging_setup, tmp_path
    finally:
        logging_setup.reset_logging()
        for handler in list(root.handlers):
            if handler not in before:
                root.removeHandler(handler)
                handler.close()
        root.setLevel(previous_level)


def test_setup_logging_writes_rotating_file(log_env) -> None:
    setup, tmp_path = log_env

    log = setup.setup_logging(console=False)
    log.info("hello from the test")

    log_file = tmp_path / "logs" / "vizier.log"
    assert log_file.exists()
    assert "hello from the test" in log_file.read_text(encoding="utf-8")

    rotating = [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, logging.handlers.RotatingFileHandler)
    ]
    assert len(rotating) == 1
    assert rotating[0].maxBytes == setup.MAX_BYTES


def test_setup_logging_is_idempotent(log_env) -> None:
    setup, _ = log_env

    setup.setup_logging(verbose=False, console=False)
    setup.setup_logging(verbose=True, console=False)

    rotating = [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, logging.handlers.RotatingFileHandler)
    ]
    assert len(rotating) == 1
    assert logging.getLogger().level == logging.DEBUG


def test_startup_banner_and_log_tail(log_env) -> None:
    setup, _ = log_env
    setup.setup_logging(console=False)

    setup.log_startup_banner("test-suite")
    tail = setup.read_log_tail(lines=5)

    assert "Vizier 1.0.0" in tail
    assert "test-suite" in tail
    assert len(tail.splitlines()) <= 5
    assert "Data directory" in tail


def test_read_log_tail_without_log_file(log_env) -> None:
    setup, _ = log_env
    assert setup.read_log_tail() == "(no log file yet)"


def test_reset_logging_removes_handlers(log_env) -> None:
    setup, _ = log_env
    setup.setup_logging(console=False)
    assert logging.getLogger().handlers

    setup.reset_logging()

    assert setup._configured is False
