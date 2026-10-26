"""PyInstaller entry point for the Vizier MCP server (stdio / HTTP)."""
from __future__ import annotations

import multiprocessing

from vizier.servers.mcp_server import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
