"""Tests for shell execution."""
from __future__ import annotations

import sys

from vizier.core.shell import ShellManager, ShellResult


def test_echo_success() -> None:
    result = ShellManager().execute("echo hello")
    assert isinstance(result, ShellResult)
    assert result.success
    assert "hello" in result.stdout


def test_failure_returncode() -> None:
    result = ShellManager().execute("exit 3")
    assert result.returncode == 3
    assert not result.success


def test_output_in_str() -> None:
    result = ShellManager().execute("echo vizi")
    text = str(result)
    assert "$ echo vizi" in text
    assert "STDOUT" in text


def test_timeout() -> None:
    command = f'"{sys.executable}" -c "import time; time.sleep(2)"'
    result = ShellManager(default_timeout=1).execute(command, timeout=1)
    assert result.timed_out
    assert result.returncode == -1
