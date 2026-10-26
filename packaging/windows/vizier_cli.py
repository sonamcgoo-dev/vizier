"""PyInstaller entry point for the Vizier command-line interface."""
from __future__ import annotations

import multiprocessing

from vizier.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
