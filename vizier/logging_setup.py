"""
Logging and crash reporting for Vizier.

Every release build writes rotating log files to the user data directory so
problems can be diagnosed without a debugger.  The helpers here are shared by
the GUI, the CLI, and the MCP server.
"""
from __future__ import annotations

import contextlib
import faulthandler
import logging
import logging.handlers
import sys
import traceback
from datetime import datetime
from pathlib import Path

from vizier.utils import get_data_dir

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 3

_configured = False


def get_log_dir() -> Path:
    """Return the directory that holds Vizier log files."""
    path = get_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_log_file() -> Path:
    """Return the main log file path."""
    return get_log_dir() / "vizier.log"


def setup_logging(
    verbose: bool = False,
    *,
    log_name: str = "vizier",
    console: bool = True,
) -> logging.Logger:
    """
    Configure application-wide logging.

    Installs a rotating file handler plus (when available) a console handler.
    Safe to call more than once; later calls only adjust the level.
    """
    global _configured

    root = logging.getLogger()
    level = logging.DEBUG if verbose else logging.INFO

    if _configured:
        root.setLevel(level)
        return logging.getLogger(log_name)
    root.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT)

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            get_log_file(),
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        file_handler._vizier = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)
    except OSError:
        # A read-only data directory should never stop the application.
        pass

    # Windowed (PyInstaller --noconsole) builds have no usable stderr.
    stream = sys.stderr
    if console and stream is not None:
        try:
            stream.write("")
            console_handler = logging.StreamHandler(stream)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
            console_handler._vizier = True  # type: ignore[attr-defined]
            root.addHandler(console_handler)
        except (OSError, ValueError):
            pass

    # Keep third-party logs quiet unless the user asked for detail.
    for noisy in ("urllib3", "requests", "httpx", "httpcore", "mcp", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True
    return logging.getLogger(log_name)


def install_faulthandler() -> Path | None:
    """Write native crashes (segfaults in llama.cpp) to a durable log file."""
    try:
        path = get_log_dir() / "crash.log"
        handle = open(path, "a", encoding="utf-8")  # noqa: SIM115 - kept alive
        faulthandler.enable(file=handle, all_threads=True)
        return path
    except Exception:
        return None


def install_exception_hook(parent=None) -> None:
    """
    Log uncaught exceptions and show a dialog when a Qt parent is available.

    ``parent`` is optional so the CLI can use this too.
    """
    previous = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc_value, exc_tb)
            return
        logging.getLogger("vizier.crash").critical(
            "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb)
        )
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                box = QMessageBox(parent)
                box.setIcon(QMessageBox.Critical)
                box.setWindowTitle("Vizier — unexpected error")
                box.setText(
                    "Vizier hit an unexpected problem. The details below were "
                    "written to the log file."
                )
                box.setInformativeText(f"Log file:\n{get_log_file()}")
                box.setDetailedText(details)
                box.exec()
                return
        except Exception:
            pass
        sys.stderr.write(details)

    sys.excepthook = _hook


def log_startup_banner(component: str) -> None:
    """Record the environment for support requests."""
    from vizier.__version__ import __codename__, __version__

    log = logging.getLogger("vizier.startup")
    log.info("=" * 68)
    log.info(
        "Vizier %s (%s) starting — %s — %s",
        __version__,
        __codename__,
        component,
        datetime.now().isoformat(timespec="seconds"),
    )
    log.info("Python %s on %s", sys.version.split()[0], sys.platform)
    log.info("Executable: %s", sys.executable)
    log.info("Data directory: %s", get_data_dir())


def read_log_tail(lines: int = 200) -> str:
    """Return the tail of the main log file (used by the About dialog)."""
    try:
        content = get_log_file().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(no log file yet)"
    return "\n".join(content.splitlines()[-lines:])


def reset_logging() -> None:
    """Tear down handlers installed by :func:`setup_logging` (tests only)."""
    global _configured
    root = logging.getLogger()
    for handler in list(root.handlers):
        if not getattr(handler, "_vizier", False):
            continue
        root.removeHandler(handler)
        with contextlib.suppress(Exception):
            handler.close()
    _configured = False
