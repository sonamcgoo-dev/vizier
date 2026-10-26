"""Tests for core data types."""
from __future__ import annotations

from vizier.core.types import (
    LLMResponse,
    Message,
    Role,
    ToolCall,
    ToolDefinition,
    ToolResult,
)


def test_tool_call_openai_format() -> None:
    call = ToolCall(id="1", name="read_file", arguments={"path": "x.txt"})
    assert call.to_openai_format() == {
        "id": "1",
        "type": "function",
        "function": {"name": "read_file", "arguments": {"path": "x.txt"}},
    }


def test_message_round_trip_with_tool_calls() -> None:
    original = Message(
        role=Role.ASSISTANT,
        content=None,
        tool_calls=[ToolCall(id="1", name="echo", arguments={"text": "hi"})],
    )
    restored = Message.from_dict(original.to_dict())
    assert restored.role is Role.ASSISTANT
    assert restored.tool_calls[0].name == "echo"
    assert restored.tool_calls[0].arguments == {"text": "hi"}


def test_message_from_dict_parses_json_arguments() -> None:
    msg = Message.from_dict({
        "role": "assistant",
        "tool_calls": [{
            "id": "abc",
            "function": {"name": "echo", "arguments": '{"text": "hi"}'},
        }],
    })
    assert msg.tool_calls[0].arguments == {"text": "hi"}


def test_tool_result_display() -> None:
    assert ToolResult("1", True, "ok").display_text == "ok"
    assert "boom" in ToolResult("1", False, "", error="boom").display_text


def test_llm_response_defaults() -> None:
    response = LLMResponse()
    assert response.text == ""
    assert response.tool_calls == []
    assert response.finished is True


def test_tool_definition_defaults() -> None:
    definition = ToolDefinition(name="x", description="d", parameters={})
    assert definition.dangerous is False
