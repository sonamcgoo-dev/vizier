"""
Tool initialization — assembles all built-in tools into a ToolRegistry.
"""
from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

from vizier.config import Config
from vizier.core.computer.keyboard import KeyboardController
from vizier.core.computer.mouse import MouseController
from vizier.core.computer.screen import ScreenCapture
from vizier.core.fs.file_ops import FilesystemManager
from vizier.core.llm.llama_cpp import LlamaCppProvider
from vizier.core.llm.model_manager import ModelManager
from vizier.core.llm.provider import LLMConfig
from vizier.core.session import SessionManager
from vizier.core.shell import ShellManager
from vizier.tools.computer_tools import get_computer_tools
from vizier.tools.fs_tools import get_filesystem_tools
from vizier.tools.registry import ToolRegistry
from vizier.tools.shell_tools import get_shell_tools

if TYPE_CHECKING:
    from vizier.core.agent import VizierAgent
    from vizier.core.mcp_client import MCPServerManager

log = logging.getLogger("vizier.tools")


class VizierServices:
    """Container for all shared service instances."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config.load()
        self.fs = FilesystemManager()
        self.shell = ShellManager(default_timeout=60)
        self.screen = ScreenCapture()
        self.mouse = MouseController(self.screen)
        self.keyboard = KeyboardController()
        self.model_manager = ModelManager()
        self._mcp_manager: MCPServerManager | None = None
        self.session_manager = SessionManager()
        self.registry = ToolRegistry()
        self.llm_provider: LlamaCppProvider | None = None
        self._built = False
        self._mcp_connected = False

    @property
    def mcp_manager(self) -> MCPServerManager:
        """Create the MCP manager on demand.

        Importing ``mcp`` costs well over a second and is pointless when no
        servers are configured, so the whole client stack stays lazy.
        """
        if self._mcp_manager is None:
            from vizier.core.mcp_client import MCPServerManager

            self._mcp_manager = MCPServerManager()
        return self._mcp_manager

    def build_tools(self) -> ToolRegistry:
        """Assemble all built-in tools into the registry."""
        if self._built:
            return self.registry
        self.registry.register_many(
            get_computer_tools(self.screen, self.mouse, self.keyboard)
        )
        self.registry.register_many(get_filesystem_tools(self.fs))
        self.registry.register_many(get_shell_tools(self.shell))
        if self.config.mcp_servers:
            from vizier.core.mcp_client import MCPServerConfig

            for server in self.config.mcp_servers:
                try:
                    self.mcp_manager.add_server(MCPServerConfig.from_dict(server))
                except Exception as exc:
                    log.warning("Invalid MCP server config %r: %s", server, exc)
            self.mcp_manager.set_registry(self.registry)
        self._built = True
        return self.registry

    def load_llm(self, model_path: str | None = None) -> LlamaCppProvider:
        """Create the llama.cpp provider from the current configuration."""
        path = model_path or self.config.model_path
        cfg = LLMConfig(
            model_path=path,
            n_ctx=self.config.model_n_ctx,
            n_gpu_layers=self.config.model_n_gpu_layers,
            temperature=self.config.model_temperature,
            top_p=self.config.model_top_p,
            repeat_penalty=self.config.model_repeat_penalty,
            model_alias=path.replace("\\", "/").split("/")[-1] if path else "",
        )
        self.llm_provider = LlamaCppProvider(cfg)
        self.config.model_path = path
        return self.llm_provider

    def connect_mcp_servers(self) -> None:
        """Auto-connect to configured MCP servers if enabled."""
        if self._mcp_connected or not self.config.mcp_auto_start:
            return
        self.build_tools()
        self.mcp_manager.connect_all()
        self._mcp_connected = True

    def create_agent(
        self,
        yolo: bool | None = None,
        *,
        on_llm_chunk=None,
        on_tool_start=None,
        on_tool_result=None,
        on_state_change=None,
    ) -> VizierAgent:
        """Create an agent wired to the configured tools and LLM."""
        # Imported lazily to avoid a circular import: vizier.core.agent imports
        # vizier.tools.registry, which triggers this package's __init__.
        from vizier.core.agent import AgentConfig, VizierAgent

        if self.llm_provider is None:
            self.load_llm()
        if not self._built:
            self.build_tools()
        if self.config.mcp_auto_start:
            self.connect_mcp_servers()

        yolo_enabled = (
            yolo if yolo is not None else self.config.yolo_enabled
        )
        agent_config = AgentConfig(
            system_prompt=self.config.system_prompt,
            max_tool_rounds=self.config.max_tool_rounds,
            yolo_enabled=yolo_enabled,
            streaming=True,
            on_llm_chunk=on_llm_chunk,
            on_tool_start=on_tool_start,
            on_tool_result=on_tool_result,
            on_state_change=on_state_change,
        )
        return VizierAgent(self.llm_provider, self.registry, agent_config)

    def shutdown(self) -> None:
        """Disconnect MCP servers and unload the model."""
        if self._mcp_manager is not None:
            with contextlib.suppress(Exception):
                self._mcp_manager.disconnect_all()
        self._mcp_connected = False
