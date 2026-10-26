"""
Abstract LLM provider interface.

Vizier supports pluggable LLM backends.  Each provider implements
:class:`LLMProvider` and returns streaming :class:`LLMResponse` objects
that may contain text and / or tool calls.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from vizier.core.types import LLMResponse, Message, ToolDefinition

log = logging.getLogger("vizier.llm")


@dataclass
class LLMConfig:
    """Configuration shared across all LLM providers."""
    model_path: str
    n_ctx: int = 4096
    n_gpu_layers: int = 0
    temperature: float = 0.7
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    max_tokens: int = -1  # -1 = unlimited (use n_ctx)
    stop_words: list[str] | None = None
    model_alias: str = ""

    def to_dict(self) -> dict:
        return {
            "model_path": self.model_path,
            "n_ctx": self.n_ctx,
            "n_gpu_layers": self.n_gpu_layers,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "repeat_penalty": self.repeat_penalty,
            "max_tokens": self.max_tokens,
            "stop_words": self.stop_words,
            "model_alias": self.model_alias,
        }


class LLMProvider(ABC):
    """Abstract base class for all LLM backends."""

    #: Human-readable name shown in the UI
    display_name: str = "AbstractLLM"

    #: Short identifier (e.g. "llamacpp")
    provider_id: str = "abstract"

    def __init__(self, config: LLMConfig):
        self.config = config
        self._model = None
        self._info: dict = {}
        self._loaded = False

    # -- lifecycle --------------------------------------------------------

    @abstractmethod
    async def load(self) -> None:
        """Load the model into memory (may be slow)."""

    @abstractmethod
    async def unload(self) -> None:
        """Release model memory."""

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_info(self) -> dict:
        return self._info

    # -- inference --------------------------------------------------------

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Single-turn generation — returns a parsed LLMResponse."""

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
    ) -> AsyncIterator[LLMResponse]:
        """Streaming generation — yields partial LLMResponse chunks."""

    # -- convenience ------------------------------------------------------

    def supports_tools(self) -> bool:
        """Whether this provider supports structured tool calling."""
        return True

    def supports_vision(self) -> bool:
        """Whether this provider can process image inputs."""
        return False

    def token_count(self, text: str) -> int:
        """Rough token estimate (override with real tokenizer when possible)."""
        return max(1, len(text) // 4)
