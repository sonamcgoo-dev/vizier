"""
Core type definitions for Vizier's agent architecture.

These types are deliberately simple and serialisable so they can be used
both in the Qt GUI thread and in the headless CLI / MCP server.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Chat-message roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    DEVELOPER = "developer"


class ToolCategory(str, Enum):
    """Categories used for UI grouping and filtering."""
    COMPUTER = "computer"
    FILESYSTEM = "filesystem"
    SHELL = "shell"
    MCP = "mcp"
    CODE = "code"
    REASONING = "reasoning"
    SEARCH = "search"
    CUSTOM = "custom"


@dataclass
class ToolCall:
    """A request from the LLM to call a tool."""
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_openai_format(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            },
        }


@dataclass
class ToolResult:
    """The result of executing a tool call."""
    call_id: str
    success: bool
    content: str
    error: str | None = None

    @property
    def display_text(self) -> str:
        if self.success:
            return self.content
        return f"[ERROR] {self.error or self.content}"


@dataclass
class ToolDefinition:
    """OpenAI-style function definition for a tool."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    category: str = ToolCategory.CUSTOM.value
    dangerous: bool = False  # Triggers YOLO confirmation
    strict: bool = False


@dataclass
class Message:
    """A chat message that can include text, tool calls, and tool results."""
    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # for tool result messages
    name: str | None = None  # for named tool results
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role.value}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [tc.to_openai_format() for tc in self.tool_calls]
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Message:
        role = Role(d.get("role", Role.ASSISTANT.value))
        msg = cls(role=role, content=d.get("content"))
        for tc in d.get("tool_calls", []):
            if isinstance(tc, dict):
                func = tc.get("function", tc)
                msg.tool_calls.append(ToolCall(
                    id=tc.get("id", f"call_{len(msg.tool_calls)}"),
                    name=func.get("name", ""),
                    arguments=func.get("arguments", {}) if isinstance(func.get("arguments"), dict)
                    else _safe_json_parse(func.get("arguments", {})),
                ))
        if "tool_call_id" in d:
            msg.tool_call_id = d["tool_call_id"]
        return msg


def _safe_json_parse(val: Any) -> dict[str, Any]:
    if isinstance(val, str):
        import json
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    return val if isinstance(val, dict) else {}


@dataclass
class LLMResponse:
    """Parsed response from the LLM: text + optional tool calls."""
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finished: bool = True
    finish_reason: str = "stop"
