"""Common MCP server catalog for Vizier.

This module bundles a small, practical set of default MCP server definitions that
users can adapt in local config files or local testing setups.
"""
from __future__ import annotations

from typing import Any

COMMON_MCP_SERVERS: list[dict[str, Any]] = [
    {
        "name": "filesystem",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        "env": {},
        "enabled": True,
        "auto_start": True,
    },
    {
        "name": "github",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {},
        "enabled": False,
        "auto_start": False,
    },
    {
        "name": "sqlite",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "./data/local.db"],
        "env": {},
        "enabled": False,
        "auto_start": False,
    },
    {
        "name": "fetch",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-fetch"],
        "env": {},
        "enabled": False,
        "auto_start": False,
    },
]


def get_common_mcp_servers() -> list[dict[str, Any]]:
    """Return a curated starter set of MCP server manifests."""
    return [server.copy() for server in COMMON_MCP_SERVERS]
