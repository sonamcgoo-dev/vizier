"""Tests for the tool registry and FunctionTool."""
from __future__ import annotations

import pytest

from vizier.core.tool import FunctionTool, VizierTool
from vizier.core.types import ToolCategory
from vizier.tools.registry import ToolRegistry


class EchoTool(VizierTool):
    name = "echo"
    description = "Echo text"
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    category = ToolCategory.CUSTOM.value

    def execute(self, text: str) -> str:
        return text


class DangerousTool(EchoTool):
    name = "danger"
    dangerous = True


def test_register_and_lookup() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    assert registry.has("echo")
    assert registry.get("echo") is not None
    assert registry.names == ["echo"]


def test_register_rejects_non_tools() -> None:
    registry = ToolRegistry()
    with pytest.raises(TypeError):
        registry.register(object())  # type: ignore[arg-type]


def test_definitions_and_dangerous_filter() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(DangerousTool())

    all_defs = registry.definitions()
    assert len(all_defs) == 2
    assert all_defs[0]["type"] == "function"

    safe_defs = registry.definitions(include_dangerous=False)
    assert [d["function"]["name"] for d in safe_defs] == ["echo"]
    assert registry.get_dangerous() == ["danger"]


def test_unregister_and_enable_disable() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    assert registry.disable("echo")
    assert registry.definitions() == []
    assert registry.enable("echo")
    assert len(registry.definitions()) == 1
    assert registry.unregister("echo")
    assert not registry.has("echo")


def test_by_category() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    grouped = registry.by_category()
    assert grouped["custom"][0].name == "echo"


def test_function_tool_infers_schema() -> None:
    def add(a: int, b: int = 2) -> int:
        """Add two numbers."""
        return a + b

    tool = VizierTool.from_function(add)
    assert isinstance(tool, FunctionTool)
    assert tool.name == "add"
    assert tool.description == "Add two numbers."
    assert tool.parameters["required"] == ["a"]
    assert tool.parameters["properties"]["a"]["type"] == "integer"
    assert tool.execute(a=1, b=3) == "4"
