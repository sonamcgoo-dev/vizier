"""
MCP (Model Context Protocol) client integration for Vizier.

Connects to MCP servers (stdio or HTTP), discovers their tools, and
exposes them as Vizier tools via :class:`MCPToolAdapter`.

The ``mcp`` package is an optional dependency: importing Vizier works
without it, but connecting to MCP servers requires it.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from vizier.core.tool import VizierTool
from vizier.core.types import ToolCategory
from vizier.tools.registry import ToolRegistry

log = logging.getLogger("vizier.mcp_client")

try:  # pragma: no cover - optional dependency
    from mcp import Client, StdioServerParameters

    _MCP_AVAILABLE = True
except ImportError:  # pragma: no cover
    Client = None  # type: ignore[assignment]
    StdioServerParameters = None  # type: ignore[assignment]
    _MCP_AVAILABLE = False


def _require_mcp() -> None:
    if not _MCP_AVAILABLE:
        raise RuntimeError(
            "The 'mcp' package is not installed. Install it with: pip install mcp"
        )


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""

    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    transport: str = "stdio"
    enabled: bool = True
    auto_start: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> MCPServerConfig:
        return cls(
            name=d.get("name", "unknown"),
            command=d.get("command"),
            args=list(d.get("args", []) or []),
            url=d.get("url"),
            env=dict(d.get("env", {}) or {}),
            transport=d.get("transport", "stdio"),
            enabled=bool(d.get("enabled", True)),
            auto_start=bool(d.get("auto_start", True)),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "command": self.command,
            "args": self.args,
            "url": self.url,
            "env": self.env,
            "transport": self.transport,
            "enabled": self.enabled,
            "auto_start": self.auto_start,
        }

    def to_mcp_params(self):
        _require_mcp()
        return StdioServerParameters(
            command=self.command or "",
            args=self.args,
            env=self.env or None,
        )


class MCPServerManager:
    """Manages connections to multiple MCP servers."""

    def __init__(self):
        self._servers: dict[str, MCPServerConfig] = {}
        self._clients: dict[str, Any] = {}
        self._stacks: dict[str, AsyncExitStack] = {}
        self._tool_adapters: dict[str, MCPToolAdapter] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._registry: ToolRegistry | None = None

    # -- configuration ----------------------------------------------------

    def set_registry(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def add_server(self, config: MCPServerConfig) -> None:
        self._servers[config.name] = config

    def remove_server(self, name: str) -> None:
        self.disconnect_server(name)
        self._servers.pop(name, None)

    @property
    def servers(self) -> dict[str, MCPServerConfig]:
        return dict(self._servers)

    @property
    def connected_servers(self) -> list[str]:
        return list(self._clients.keys())

    # -- background event loop -------------------------------------------

    def _ensure_loop(self) -> None:
        if (
            self._loop is not None
            and not self._loop.is_closed()
            and self._thread is not None
            and self._thread.is_alive()
        ):
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="vizier-mcp-loop",
        )
        self._thread.start()

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_coro(self, coro):
        self._ensure_loop()
        assert self._loop is not None
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    # -- connections ------------------------------------------------------

    async def connect_server(self, name: str):
        """Connect to an MCP server and register its tools."""
        if name in self._clients:
            return self._clients[name]
        config = self._servers.get(name)
        if not config or not config.enabled:
            return None
        _require_mcp()

        stack = AsyncExitStack()
        try:
            if config.transport == "stdio":
                client_cm = Client(
                    config.to_mcp_params(), raise_exceptions=False
                )
            else:
                if not config.url:
                    raise ValueError(
                        f"MCP server '{name}' has transport={config.transport} "
                        "but no url configured"
                    )
                client_cm = Client(config.url, raise_exceptions=False)
            client = await stack.enter_async_context(client_cm)
        except Exception as exc:
            await stack.aclose()
            log.error("Failed to connect to MCP server '%s': %s", name, exc)
            return None

        self._clients[name] = client
        self._stacks[name] = stack
        log.info("Connected to MCP server: %s", name)
        await self._register_tools(name, client)
        return client

    def connect_server_sync(self, name: str, timeout: float = 20.0):
        """Blocking helper used by the GUI/CLI."""
        return self._run_coro(self.connect_server(name)).result(timeout=timeout)

    async def _register_tools(self, server_name: str, client) -> None:
        """Discover tools from an MCP server and register them."""
        try:
            tools_result = await client.list_tools()
            tools = tools_result.tools if tools_result else []
        except Exception as exc:
            log.warning(
                "Could not list tools from '%s': %s", server_name, exc
            )
            return
        for tool in tools:
            td = self._extract_tool_def(tool)
            adapter = MCPToolAdapter(
                server_name=server_name,
                tool_name=tool.name,
                description=td.get("description", ""),
                parameters=td.get(
                    "parameters", {"type": "object", "properties": {}}
                ),
                client=client,
                loop_ref=self._loop,
            )
            self._tool_adapters[adapter.name] = adapter
            if self._registry:
                self._registry.register(adapter)

    @staticmethod
    def _extract_tool_def(tool) -> dict:
        desc = getattr(tool, "description", "") or ""
        params = getattr(tool, "inputSchema", None)
        if params is None:
            params = getattr(tool, "parameters", None)
        if params is None:
            params = {"type": "object", "properties": {}}
        elif hasattr(params, "model_dump"):
            params = params.model_dump()
        return {
            "name": getattr(tool, "name", ""),
            "description": desc,
            "parameters": params,
        }

    def connect_all(self) -> None:
        """Connect to all enabled servers with auto_start=True."""
        for name, config in list(self._servers.items()):
            if config.enabled and config.auto_start:
                try:
                    self.connect_server_sync(name)
                except Exception as exc:
                    log.error(
                        "Failed to auto-start MCP server '%s': %s", name, exc
                    )

    def disconnect_server(self, name: str) -> None:
        """Close one MCP server connection."""
        stack = self._stacks.pop(name, None)
        self._clients.pop(name, None)
        if stack is not None:
            with contextlib.suppress(Exception):
                self._run_coro(stack.aclose()).result(timeout=10)
        for tool_name in [
            n for n, a in self._tool_adapters.items()
            if a.server_name == name
        ]:
            self._tool_adapters.pop(tool_name, None)
            if self._registry:
                self._registry.unregister(tool_name)

    def disconnect_all(self) -> None:
        """Close all MCP server connections."""
        for name in list(self._clients.keys()):
            self.disconnect_server(name)

    # -- tool access ------------------------------------------------------

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        adapter = self._tool_adapters.get(tool_name)
        if adapter:
            return adapter.execute(**arguments)
        raise KeyError(f"Unknown MCP tool: {tool_name}")

    def list_tools(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for adapter in self._tool_adapters.values():
            td = adapter.definition
            result.append({
                "name": td.name,
                "description": td.description,
                "parameters": td.parameters,
                "category": td.category,
                "server": adapter.server_name,
            })
        return result


class MCPToolAdapter(VizierTool):
    """Wraps an MCP server's tool as a VizierTool."""

    def __init__(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        parameters: dict,
        client,
        loop_ref: asyncio.AbstractEventLoop | None = None,
    ):
        super().__init__()
        self.server_name = server_name
        self._tool_name = tool_name
        self._name_override: str | None = None
        self.description = description
        self.parameters = parameters
        self.category = ToolCategory.MCP.value
        self.dangerous = False
        self._client = client
        self._loop_ref = loop_ref

    @property
    def name(self) -> str:
        return self._name_override or f"mcp_{self.server_name}_{self._tool_name}"

    @name.setter
    def name(self, value: str) -> None:
        self._name_override = value

    def execute(self, **kwargs: Any) -> str:
        """Call the MCP tool synchronously."""
        if self._loop_ref is None or self._loop_ref.is_closed():
            return "[MCP tool error: no active event loop]"

        async def _call() -> str:
            result = await self._client.call_tool(
                self._tool_name, kwargs
            )
            content = (
                getattr(result, "content", None)
                or getattr(result, "structured_content", None)
                or str(result)
            )
            if isinstance(content, list):
                texts = [
                    c.text if hasattr(c, "text") else str(c) for c in content
                ]
                return "\n".join(t for t in texts if t)
            return str(content)

        future = asyncio.run_coroutine_threadsafe(_call(), self._loop_ref)
        try:
            return future.result(timeout=60)
        except Exception as exc:
            return f"[MCP tool error: {exc}]"
