"""Tests for the agent reasoning loop using a scripted LLM."""
from __future__ import annotations

import asyncio
import time

from vizier.core.agent import AgentConfig, VizierAgent
from vizier.core.llm.provider import LLMConfig, LLMProvider
from vizier.core.tool import VizierTool
from vizier.core.types import LLMResponse, Role, ToolCall
from vizier.tools.registry import ToolRegistry


def run(coro):
    """Run a coroutine without depending on pytest-asyncio."""
    return asyncio.run(coro)


class ScriptedProvider(LLMProvider):
    """A provider that replays pre-scripted streamed responses."""

    display_name = "Scripted"
    provider_id = "scripted"

    def __init__(self, responses):
        super().__init__(LLMConfig(model_path="fake.gguf"))
        self.responses = responses
        self.calls = 0

    async def load(self) -> None:
        self._loaded = True

    async def unload(self) -> None:
        self._loaded = False

    def _next(self):
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[index]

    async def generate(self, messages, tools=None, system_prompt=None):
        chunks = self._next()
        result = LLMResponse()
        for chunk in chunks:
            result.text += chunk.text
            result.tool_calls.extend(chunk.tool_calls)
            result.finished = chunk.finished
            result.finish_reason = chunk.finish_reason
        return result

    async def generate_stream(self, messages, tools=None, system_prompt=None):
        for chunk in self._next():
            yield chunk


class EchoTool(VizierTool):
    name = "echo"
    description = "Echo text"
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    category = "custom"

    def execute(self, text: str) -> str:
        return text


class DangerousEcho(EchoTool):
    name = "danger"
    dangerous = True


class SlowTool(EchoTool):
    name = "slow"

    def execute(self, text: str = "") -> str:
        time.sleep(0.5)
        return "slow"


class FailingTool(EchoTool):
    name = "fail"

    def execute(self, text: str = "") -> str:
        raise ValueError("boom")


def make_agent(responses, tools=None, **config_kwargs):
    provider = ScriptedProvider(responses)
    registry = ToolRegistry()
    for tool in tools or []:
        registry.register(tool)
    config = AgentConfig(
        system_prompt="test",
        streaming=True,
        max_tool_rounds=config_kwargs.pop("max_tool_rounds", 5),
        **config_kwargs,
    )
    return VizierAgent(provider, registry, config)


def test_text_only_turn() -> None:
    agent = make_agent([[
        LLMResponse(text="Hel", finished=False),
        LLMResponse(text="lo", finished=True),
    ]])
    chunks: list[str] = []
    agent.config.on_llm_chunk = chunks.append

    result = run(agent.run("hi"))
    assert result == "Hello"
    assert chunks == ["Hel", "lo"]
    assert agent.history[0].role is Role.USER
    assert agent.history[1].role is Role.ASSISTANT
    assert agent.state.value == "idle"


def test_tool_call_then_answer_ordering() -> None:
    responses = [
        [LLMResponse(
            text="",
            tool_calls=[ToolCall(id="1", name="echo", arguments={"text": "hi"})],
            finished=False,
        )],
        [LLMResponse(text="done", finished=True)],
    ]
    agent = make_agent(responses, tools=[EchoTool()])

    result = run(agent.run("go"))
    assert result == "done"
    assert [m.role for m in agent.history] == [
        Role.USER, Role.ASSISTANT, Role.TOOL, Role.ASSISTANT,
    ]
    assert agent.history[2].content == "hi"
    assert agent.history[2].tool_call_id == "1"


def test_dangerous_tool_blocked_without_yolo() -> None:
    responses = [
        [LLMResponse(
            text="",
            tool_calls=[ToolCall(id="1", name="danger", arguments={"text": "x"})],
            finished=False,
        )],
        [LLMResponse(text="ok", finished=True)],
    ]
    agent = make_agent(responses, tools=[DangerousEcho()], yolo_enabled=False)
    run(agent.run("go"))
    assert "BLOCKED" in agent.history[2].content


def test_dangerous_tool_allowed_with_yolo() -> None:
    responses = [
        [LLMResponse(
            text="",
            tool_calls=[ToolCall(id="1", name="danger", arguments={"text": "x"})],
            finished=False,
        )],
        [LLMResponse(text="ok", finished=True)],
    ]
    agent = make_agent(responses, tools=[DangerousEcho()], yolo_enabled=True)
    run(agent.run("go"))
    assert agent.history[2].content == "x"


def test_unknown_tool_reports_error() -> None:
    responses = [
        [LLMResponse(
            text="",
            tool_calls=[ToolCall(id="1", name="missing", arguments={})],
            finished=False,
        )],
        [LLMResponse(text="ok", finished=True)],
    ]
    agent = make_agent(responses)
    run(agent.run("go"))
    assert "unknown tool" in agent.history[2].content


def test_tool_failure_is_reported() -> None:
    responses = [
        [LLMResponse(
            text="",
            tool_calls=[ToolCall(id="1", name="fail", arguments={})],
            finished=False,
        )],
        [LLMResponse(text="ok", finished=True)],
    ]
    agent = make_agent(responses, tools=[FailingTool()])
    run(agent.run("go"))
    assert "boom" in agent.history[2].content


def test_tool_timeout() -> None:
    responses = [
        [LLMResponse(
            text="",
            tool_calls=[ToolCall(id="1", name="slow", arguments={})],
            finished=False,
        )],
        [LLMResponse(text="ok", finished=True)],
    ]
    agent = make_agent(responses, tools=[SlowTool()], tool_timeout=0.1)
    run(agent.run("go"))
    assert "timed out" in agent.history[2].content


def test_tool_callbacks() -> None:
    responses = [
        [LLMResponse(
            text="",
            tool_calls=[ToolCall(id="1", name="echo", arguments={"text": "hi"})],
            finished=False,
        )],
        [LLMResponse(text="ok", finished=True)],
    ]
    started = []
    finished = []
    agent = make_agent(responses, tools=[EchoTool()])
    agent.config.on_tool_start = lambda tc: started.append(tc.name)
    agent.config.on_tool_result = lambda tc, text, ok: finished.append((tc.name, text, ok))

    run(agent.run("go"))
    assert started == ["echo"]
    assert finished == [("echo", "hi", True)]


def test_max_tool_rounds() -> None:
    def tool_call_response():
        return [LLMResponse(
            text="",
            tool_calls=[ToolCall(id="1", name="echo", arguments={"text": "x"})],
            finished=False,
        )]

    agent = make_agent(
        [tool_call_response()],
        tools=[EchoTool()],
        max_tool_rounds=2,
    )
    result = run(agent.run("go"))
    assert "Maximum tool rounds" in result


def test_non_streaming_mode() -> None:
    agent = make_agent(
        [[LLMResponse(text="direct", finished=True)]],
    )
    agent.config.streaming = False
    assert run(agent.run("hi")) == "direct"


def test_clear_and_set_helpers() -> None:
    agent = make_agent([[LLMResponse(text="ok", finished=True)]])
    run(agent.run("hi"))
    assert agent.history
    agent.add_system_message("note")
    agent.set_system_prompt("new prompt")
    agent.set_yolo(True)
    assert agent.config.system_prompt == "new prompt"
    assert agent.config.yolo_enabled is True
    agent.clear_history()
    assert agent.history == []
