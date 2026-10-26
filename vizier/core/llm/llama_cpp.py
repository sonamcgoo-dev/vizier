"""
LlamaCpp LLM provider — uses ``llama-cpp-python`` for GGUF inference.

Supports CPU inference and GPU offloading via:
  - ``nvidia``  (CUDA)
  - ``amd``     (Vulkan / ROCm)
  - ``intel``   (Vulkan)
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from vizier.core.llm.provider import LLMConfig, LLMProvider
from vizier.core.types import LLMResponse, Message, ToolCall

log = logging.getLogger("vizier.llm.llamacpp")


class LlamaCppProvider(LLMProvider):
    """GGUF inference through llama-cpp-python."""

    display_name = "Llama.cpp (GGUF)"
    provider_id = "llamacpp"

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._llm = None
        self._model_params: dict[str, Any] = {}

    # -- lifecycle --------------------------------------------------------

    async def load(self) -> None:
        """Load the GGUF model asynchronously."""
        if self._loaded:
            return
        if not self.config.model_path:
            raise RuntimeError(
                "No model path configured. Select a .gguf model first."
            )
        try:
            from llama_cpp import Llama
        except ImportError as e:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "llama-cpp-python is not installed. Run the install wizard "
                "or: pip install llama-cpp-python"
            ) from e

        log.info("Loading model: %s", self.config.model_path)

        def _do_load():
            params: dict[str, Any] = {
                "model_path": self.config.model_path,
                "n_ctx": self.config.n_ctx,
                "n_gpu_layers": self.config.n_gpu_layers,
                "verbose": False,
            }
            self._model_params = params.copy()
            return Llama(**params)

        loop = asyncio.get_running_loop()
        self._llm = await loop.run_in_executor(None, _do_load)
        self._info = {
            "name": self.config.model_alias or self.config.model_path,
            "path": self.config.model_path,
            "n_ctx": self.config.n_ctx,
            "n_gpu_layers": self.config.n_gpu_layers,
        }
        self._loaded = True
        log.info("Model loaded successfully")

    async def unload(self) -> None:
        """Release the model from memory."""
        llm, self._llm = self._llm, None
        if llm is not None:
            try:
                close = getattr(llm, "close", None)
                if callable(close):
                    close()
                del llm
            except Exception:
                pass
        self._loaded = False
        self._info = {}

    # -- message building -------------------------------------------------

    def _build_chat_messages(
        self,
        messages: list[Message],
        system_prompt: str | None,
    ) -> list[dict[str, Any]]:
        """Convert Vizier Message objects to llama-cpp chat format."""
        chat: list[dict[str, Any]] = []
        if system_prompt:
            chat.append({"role": "system", "content": system_prompt})
        for msg in messages:
            role = msg.role.value
            if role == "system":
                chat.append({"role": "system", "content": msg.content or ""})
            elif role == "user":
                chat.append({"role": "user", "content": msg.content or ""})
            elif role == "assistant":
                entry: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content or "",
                }
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        tc.to_openai_format() for tc in msg.tool_calls
                    ]
                chat.append(entry)
            elif role == "tool":
                entry = {
                    "role": "tool",
                    "content": msg.content or "",
                }
                if msg.tool_call_id:
                    entry["tool_call_id"] = msg.tool_call_id
                chat.append(entry)
        return chat

    def _convert_tools(
        self, tools: list | None
    ) -> list[dict[str, Any]] | None:
        """Convert tool definitions to llama-cpp's expected format."""
        if not tools:
            return None
        result: list[dict[str, Any]] = []
        for t in tools:
            if isinstance(t, dict):
                if "type" in t and "function" in t:
                    result.append(t)
                elif "name" in t:
                    result.append({"type": "function", "function": t})
                continue
            definition = getattr(t, "definition", None)
            if definition is not None:
                result.append({
                    "type": "function",
                    "function": {
                        "name": definition.name,
                        "description": definition.description,
                        "parameters": definition.parameters,
                    },
                })
        return result or None

    @staticmethod
    def _base_kwargs(
        chat: list[dict[str, Any]],
        llama_tools: list[dict[str, Any]] | None,
        config: LLMConfig,
        stream: bool,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "messages": chat,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "repeat_penalty": config.repeat_penalty,
            "stream": stream,
        }
        if llama_tools:
            kwargs["tools"] = llama_tools
        if config.max_tokens and config.max_tokens > 0:
            kwargs["max_tokens"] = config.max_tokens
        if config.stop_words:
            kwargs["stop"] = config.stop_words
        return kwargs

    # -- inference --------------------------------------------------------

    async def generate(
        self,
        messages: list[Message],
        tools: list | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Single-turn generation."""
        if not self._loaded:
            await self.load()
        assert self._llm is not None

        chat = self._build_chat_messages(messages, system_prompt)
        llama_tools = self._convert_tools(tools)
        kwargs = self._base_kwargs(chat, llama_tools, self.config, stream=False)

        def _do_generate():
            try:
                return self._llm.create_chat_completion(**kwargs)
            except TypeError:
                # Older llama-cpp-python builds do not accept ``tools``.
                kwargs.pop("tools", None)
                return self._llm.create_chat_completion(**kwargs)

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _do_generate)
        return self._parse_response(result)

    async def generate_stream(
        self,
        messages: list[Message],
        tools: list | None = None,
        system_prompt: str | None = None,
    ):
        """Streaming generation — yields partial LLMResponse chunks."""
        if not self._loaded:
            await self.load()
        assert self._llm is not None

        chat = self._build_chat_messages(messages, system_prompt)
        llama_tools = self._convert_tools(tools)
        kwargs = self._base_kwargs(chat, llama_tools, self.config, stream=True)

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _worker():
            try:
                try:
                    stream = self._llm.create_chat_completion(**kwargs)
                except TypeError:
                    kwargs.pop("tools", None)
                    stream = self._llm.create_chat_completion(**kwargs)
                for chunk in stream:
                    loop.call_soon_threadsafe(queue.put_nowait, ("chunk", chunk))
            except Exception as exc:  # pragma: no cover - runtime failure
                loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

        threading.Thread(
            target=_worker, daemon=True, name="vizier-llm-stream"
        ).start()

        tool_fragments: dict[int, dict[str, Any]] = {}
        finish_reason = "stop"

        while True:
            kind, payload = await queue.get()
            if kind == "error":
                raise payload
            if kind == "done":
                break
            chunk = payload
            try:
                choice = chunk["choices"][0]
            except (KeyError, IndexError, TypeError):
                continue
            delta = choice.get("delta") or {}
            finish_reason = choice.get("finish_reason") or finish_reason
            text = delta.get("content") or ""
            if text:
                yield LLMResponse(text=text, finished=False)
            for raw_tc in delta.get("tool_calls") or []:
                self._accumulate_tool_fragment(tool_fragments, raw_tc)

        tool_calls = self._finalise_tool_fragments(tool_fragments)
        yield LLMResponse(
            text="",
            tool_calls=tool_calls,
            finished=not tool_calls and finish_reason != "tool_calls",
            finish_reason="tool_calls" if tool_calls else finish_reason,
        )

    # -- parsing ----------------------------------------------------------

    @staticmethod
    def _accumulate_tool_fragment(
        fragments: dict[int, dict[str, Any]], raw_tc: Any
    ) -> None:
        if not isinstance(raw_tc, dict):
            try:
                raw_tc = dict(raw_tc)
            except Exception:
                return
        index = int(raw_tc.get("index", 0) or 0)
        slot = fragments.setdefault(
            index, {"id": "", "name": "", "arguments": ""}
        )
        if raw_tc.get("id"):
            slot["id"] = raw_tc["id"]
        func = raw_tc.get("function") or {}
        if isinstance(func, dict):
            if func.get("name"):
                slot["name"] = func["name"]
            if func.get("arguments"):
                slot["arguments"] += func["arguments"]

    @staticmethod
    def _finalise_tool_fragments(
        fragments: dict[int, dict[str, Any]]
    ) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for index in sorted(fragments):
            frag = fragments[index]
            if not frag.get("name"):
                continue
            args = frag.get("arguments") or "{}"
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    args = {}
            calls.append(ToolCall(
                id=frag.get("id") or f"call_{index}",
                name=frag.get("name", ""),
                arguments=args if isinstance(args, dict) else {},
            ))
        return calls

    def _parse_response(self, result) -> LLMResponse:
        """Parse a llama-cpp chat completion result into LLMResponse."""
        if isinstance(result, dict) and "choices" in result:
            choice = result["choices"][0]
            msg = choice.get("message", {})
            finish_reason = choice.get("finish_reason", "stop")
        elif hasattr(result, "choices"):
            choice = result.choices[0]
            msg = choice.message
            finish_reason = choice.finish_reason or "stop"
        else:
            msg = {}
            finish_reason = "stop"

        if isinstance(msg, dict):
            text = msg.get("content", "") or ""
            tool_calls_raw = msg.get("tool_calls", []) or []
        else:
            text = getattr(msg, "content", "") or ""
            tool_calls_raw = getattr(msg, "tool_calls", []) or []

        tool_calls: list[ToolCall] = []
        for tc in tool_calls_raw:
            if isinstance(tc, dict):
                func = tc.get("function", {})
                tid = tc.get("id", f"call_{len(tool_calls)}")
            else:
                func = getattr(tc, "function", {}) or {}
                tid = getattr(tc, "id", f"call_{len(tool_calls)}")
            if isinstance(func, dict):
                name = func.get("name", "")
                args = func.get("arguments", {})
            else:
                name = getattr(func, "name", "")
                args = getattr(func, "arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    args = {}
            tool_calls.append(ToolCall(
                id=tid,
                name=name,
                arguments=args if isinstance(args, dict) else {},
            ))

        return LLMResponse(
            text=text or "",
            tool_calls=tool_calls,
            finished=finish_reason != "tool_calls",
            finish_reason=finish_reason or "stop",
        )
