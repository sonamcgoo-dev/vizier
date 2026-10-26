"""
Shell command execution.

Runs commands with optional timeout, captures stdout/stderr, and reports
exit codes.  Shell execution is marked as ``dangerous`` at the tool level
because arbitrary code execution can harm the user's machine.
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("vizier.shell")


@dataclass
class ShellResult:
    """Result of a shell command execution."""
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.returncode == 0

    def __str__(self) -> str:
        lines = [f"$ {self.command}", f"[exit: {self.returncode}, {self.duration:.2f}s]"]
        if self.stdout:
            lines.append("STDOUT:")
            lines.append(self.stdout)
        if self.stderr:
            lines.append("STDERR:")
            lines.append(self.stderr)
        if self.timed_out:
            lines.append("[TIMED OUT]")
        return "\n".join(lines)


class ShellManager:
    """Execute shell commands with safety measures."""

    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(self, default_timeout: int | None = None):
        self.default_timeout = default_timeout or self.DEFAULT_TIMEOUT

    def execute(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int | None = None,
        env: dict[str, Any] | None = None,
        shell: bool = True,
    ) -> ShellResult:
        """Execute a shell command and return the result."""
        timeout = timeout or self.default_timeout
        start = time.time()
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        log.info(f"Executing: {command}")
        try:
            proc = subprocess.run(
                command, shell=shell, cwd=cwd or str(Path.cwd()),
                capture_output=True, text=True, timeout=timeout, env=full_env,
            )
            duration = time.time() - start
            return ShellResult(
                command=command, returncode=proc.returncode,
                stdout=proc.stdout, stderr=proc.stderr, duration=duration,
            )
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start
            log.warning(f"Command timed out after {timeout}s: {command}")
            return ShellResult(
                command=command, returncode=-1,
                stdout=e.stdout.decode() if e.stdout else "",
                stderr=e.stderr.decode() if e.stderr else "",
                duration=duration, timed_out=True,
            )
        except Exception as e:
            duration = time.time() - start
            log.error(f"Shell error: {e}")
            return ShellResult(
                command=command, returncode=-1, stdout="",
                stderr=str(e), duration=duration,
            )

    def execute_async(
        self, command: str, callback=None,
        cwd: str | None = None, timeout: int | None = None,
    ) -> threading.Thread:
        """Run a command in a background thread."""
        def _run():
            result = self.execute(command, cwd=cwd, timeout=timeout)
            if callback:
                callback(result)
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t

