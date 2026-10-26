"""PyInstaller entry point for the Vizier desktop application."""
from __future__ import annotations

import multiprocessing
import sys


def _enable_windows_integration() -> None:
    """Give the process its own taskbar identity so the icon groups correctly."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "VizierProject.Vizier.1"
        )
    except Exception:
        pass


def main() -> int:
    _enable_windows_integration()
    from vizier.ui.main_window import main as gui_main

    model = sys.argv[1] if len(sys.argv) > 1 else None
    return gui_main(model)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
