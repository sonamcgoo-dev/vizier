"""Tests for MCP configuration, tool discovery, and tool adapters."""
from __future__ import annotations

import asyncio
import threading

import pytest

from vizier.core.mcp_client import (
    MCPServerConfig,
    MCPServerManager,
    MCPToolAdapter,
)
from vizier.tools.registry import ToolRegistry


def test_config_round_trip() -> None:
    config = MCPServerConfig.from_dict({
        "name": "demo",
        "command": "python",
        "args": ["-m", "demo"],
        "env": {"A": "1"},
        "transport": "stdio",
    })
    assert config.name == "demo"
    assert config.args == ["-m", "demo"]
    assert config.env == {"A": "1"}
    assert MCPServerConfig.from_dict(config.to_dict()) == config


def test_to_mcp_params() -> None:
    pytest.importorskip("mcp")
    config = MCPServerConfig(
        name="demo", command="python", args=["-m", "demo"], env={"A": "1"}
    )
    params = config.to_mcp_params()
    assert params.command == "python"
    assert params.args == ["-m", "demo"]


class FakeTool:
    name = "greet"
    description = "Say hello"
    inputSchema = {
        "type": "object",
        "properties": {"who": {"type": "string"}},
        "required": ["who"],
    }


class FakeText:
    def __init__(self, text: str):
        self.text = text


class FakeResult:
    def __init__(self, text: str):
        self.content = [FakeText(text)]


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def list_tools(self):
        class Result:
            tools = [FakeTool()]
        return Result()

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return FakeResult(f"hello {arguments.get('who', '?')}")


@pytest.fixture()
def loop():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        yield loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        loop.close()


def test_manager_registers_discovered_tools(monkeypatch) -> None:
    monkeypatch.setattr("vizier.core.mcp_client.Client", FakeClient)
    registry = ToolRegistry()
    manager = MCPServerManager()
    manager.set_registry(registry)
    manager.add_server(MCPServerConfig(name="demo", command="python"))

    asyncio.run(manager.connect_server("demo"))

    assert manager.connected_servers == ["demo"]
    assert registry.has("mcp_demo_greet")
    tool = registry.get("mcp_demo_greet")
    assert tool is not None
    assert tool.description == "Say hello"

    listed = manager.list_tools()
    assert listed[0]["name"] == "mcp_demo_greet"
    assert listed[0]["server"] == "demo"


def test_adapter_executes_on_background_loop(loop) -> None:
    client = FakeClient()
    adapter = MCPToolAdapter(
        server_name="demo",
        tool_name="greet",
        description="Say hello",
        parameters={"type": "object", "properties": {}},
        client=client,
        loop_ref=loop,
    )
    assert adapter.name == "mcp_demo_greet"
    assert adapter.execute(who="Vizier") == "hello Vizier"
    assert client.calls == [("greet", {"who": "Vizier"})]


def test_extract_tool_definition() -> None:
    definition = MCPServerManager._extract_tool_def(FakeTool())
    assert definition["name"] == "greet"
    assert definition["description"] == "Say hello"
    assert definition["parameters"]["required"] == ["who"]


def test_manager_add_and_remove_server() -> None:
    manager = MCPServerManager()
    manager.add_server(MCPServerConfig(name="one"))
    assert "one" in manager.servers
    manager.remove_server("one")
    assert "one" not in manager.servers
    assert manager.connected_servers == []
