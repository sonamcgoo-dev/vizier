"""
The Vizier Agent — the core reasoning loop.

Receives user input, sends it to the LLM with available tools, executes
tool calls (with YOLO confirmation for dangerous tools), and feeds results
back to the LLM until a final response is produced.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from vizier.core.llm.provider import LLMProvider
from vizier.core.tool import VizierTool
from vizier.core.types import LLMResponse, Message, Role, ToolCall
from vizier.tools.registry import ToolRegistry

log = logging.getLogger("vizier.agent")


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    CALLING_TOOLS = "calling_tools"
    EXECUTING_TOOLS = "executing_tools"
    ERROR = "error"


@dataclass
class AgentConfig:
    """Runtime configuration for the agent."""
    system_prompt: str = ""
    max_tool_rounds: int = 10
    yolo_enabled: bool = False
    streaming: bool = True
    tool_timeout: int = 60
    on_tool_start: Callable[[ToolCall], Any] | None = None
    on_tool_result: Callable[[ToolCall, str, bool], Any] | None = None
    on_llm_chunk: Callable[[str], Any] | None = None
    on_state_change: Callable[[AgentState], Any] | None = None
    on_message: Callable[[Message], Any] | None = None
    history: list[Message] = field(default_factory=list)


class VizierAgent:
    """The main agent orchestrator."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        registry: ToolRegistry,
        config: AgentConfig | None = None,
    ):
        self.llm = llm_provider
        self.registry = registry
        self.config = config or AgentConfig()
        self.state = AgentState.IDLE
        self.history: list[Message] = self.config.history or []

    # -- callback helpers -------------------------------------------------

    def _set_state(self, state: AgentState) -> None:
        self.state = state
        cb = self.config.on_state_change
        if cb:
            try:
                cb(state)
            except Exception:
                log.debug("on_state_change callback failed", exc_info=True)

    @staticmethod
    async def _maybe_call(cb, *args) -> None:
        if cb is None:
            return
        try:
            result = cb(*args)
            if inspect.isawaitable(result):
                await result
        except Exception:
            log.debug("agent callback failed", exc_info=True)

    # -- public API -------------------------------------------------------

    async def run(
        self,
        user_input: str,
        images: list[str] | None = None,
    ) -> str:
        """Process a user message and return the final text response."""
        user_message = Message(
            role=Role.USER,
            content=user_input,
            metadata={"images": images or []},
        )
        self.history.append(user_message)
        await self._maybe_call(self.config.on_message, user_message)

        final_text = ""
        try:
            async for response in self._agent_loop():
                if response.text:
                    final_text += response.text
        except Exception as exc:
            self._set_state(AgentState.ERROR)
            log.exception("Agent run failed")
            final_text += f"\n\n[Agent error: {exc}]"
        finally:
            if self.state is not AgentState.ERROR:
                self._set_state(AgentState.IDLE)
        return final_text

    # -- core loop --------------------------------------------------------

    async def _agent_loop(self) -> AsyncIterator[LLMResponse]:
        """The full agent loop with tool calling."""
        for round_index in range(self.config.max_tool_rounds):
            response = await self._single_turn()

            if response.text or response.tool_calls:
                assistant_message = Message(
                    role=Role.ASSISTANT,
                    content=response.text or None,
                    tool_calls=list(response.tool_calls),
                )
                self.history.append(assistant_message)
                await self._maybe_call(self.config.on_message, assistant_message)
            if response.text:
                yield LLMResponse(text=response.text, finished=False)

            if not response.tool_calls:
                yield LLMResponse(text="", finished=True)
                return

            self._set_state(AgentState.EXECUTING_TOOLS)
            tool_results = await self._execute_tools(response.tool_calls)
            self.history.extend(tool_results)
            for message in tool_results:
                await self._maybe_call(self.config.on_message, message)

            if round_index == self.config.max_tool_rounds - 1:
                break

        yield LLMResponse(
            text="\n⚠️ Maximum tool rounds reached; stopping.",
            finished=True,
        )

    async def _single_turn(
        self,
        messages: list[Message] | None = None,
    ) -> LLMResponse:
        """Get an LLM response for the current history."""
        msgs = messages if messages is not None else self.history
        tools = self._get_tool_definitions()
        self._set_state(AgentState.THINKING)
        system = self.config.system_prompt or ""

        if not self.config.streaming:
            response = await self.llm.generate(msgs, tools, system)
            if response.text:
                await self._maybe_call(self.config.on_llm_chunk, response.text)
            return response

        result = LLMResponse()
        async for chunk in self.llm.generate_stream(msgs, tools, system):
            if chunk.text:
                result.text += chunk.text
                await self._maybe_call(self.config.on_llm_chunk, chunk.text)
            result.tool_calls.extend(chunk.tool_calls or [])
            result.finish_reason = chunk.finish_reason
            result.finished = chunk.finished
        return result

    def _get_tool_definitions(self) -> list:
        return self.registry.definitions(include_dangerous=True)

    async def _execute_tools(
        self, tool_calls: list[ToolCall]
    ) -> list[Message]:
        """Execute tool calls (respecting YOLO mode) and return result messages."""
        results: list[Message] = []
        for tc in tool_calls:
            self._set_state(AgentState.CALLING_TOOLS)
            await self._maybe_call(self.config.on_tool_start, tc)

            tool = self.registry.get(tc.name)
            if tool is None:
                content = f"[Error: unknown tool '{tc.name}']"
                success = False
            elif tool.dangerous and not self.config.yolo_enabled:
                log.warning(
                    "Dangerous tool '%s' blocked (YOLO disabled)", tc.name
                )
                content = (
                    f"[BLOCKED: Tool '{tc.name}' is dangerous and YOLO mode "
                    f"is disabled. Enable YOLO mode to allow it.]"
                )
                success = False
            else:
                content, success = await self._execute_one(tool, tc)

            results.append(Message(
                role=Role.TOOL,
                content=content,
                tool_call_id=tc.id,
                name=tc.name,
            ))
            await self._maybe_call(
                self.config.on_tool_result, tc, content, success
            )
        return results

    async def _execute_one(
        self, tool: VizierTool, tc: ToolCall
    ) -> tuple[str, bool]:
        """Execute a single tool with a timeout, returning (text, success)."""
        timeout = self.config.tool_timeout
        try:
            if tool.is_async:
                result = await asyncio.wait_for(
                    tool.execute_async(**tc.arguments), timeout=timeout
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(lambda: tool.execute(**tc.arguments)),
                    timeout=timeout,
                )
            return (str(result) if result is not None else ""), True
        except asyncio.TimeoutError:
            log.error("Tool '%s' timed out after %ss", tc.name, timeout)
            return f"[Tool error: '{tc.name}' timed out after {timeout}s]", False
        except Exception as exc:
            log.error("Tool '%s' failed: %s", tc.name, exc)
            return f"[Tool error: {exc}]", False

    # -- conversation management ------------------------------------------

    def clear_history(self) -> None:
        self.history.clear()

    def get_history(self) -> list[dict]:
        return [m.to_dict() for m in self.history]

    def add_system_message(self, text: str) -> None:
        self.history.append(Message(role=Role.SYSTEM, content=text))

    def set_system_prompt(self, text: str) -> None:
        self.config.system_prompt = text

    def set_yolo(self, enabled: bool) -> None:
        self.config.yolo_enabled = enabled
