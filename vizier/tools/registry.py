"""
Tool registry — central catalogue of all available tools.

Tools are registered by category, can be looked up by name, and can be
listed with full OpenAI-compatible definitions for LLM consumption.
"""
from __future__ import annotations

import logging
from typing import Any

from vizier.core.tool import VizierTool
from vizier.core.types import ToolDefinition

log = logging.getLogger("vizier.tools.registry")


class ToolRegistry:
    """In-memory registry of VizierTool instances, grouped by category."""

    def __init__(self):
        self._tools: dict[str, VizierTool] = {}
        self._by_category: dict[str, list[str]] = {}

    # -- registration -----------------------------------------------------

    def register(self, tool: VizierTool) -> None:
        """Register a tool instance."""
        if not isinstance(tool, VizierTool):
            raise TypeError(f"Expected VizierTool, got {type(tool)}")
        if tool.name in self._tools:
            log.debug(f"Re-registering tool: {tool.name}")
        self._tools[tool.name] = tool
        cat = tool.category
        if cat not in self._by_category:
            self._by_category[cat] = []
        if tool.name not in self._by_category[cat]:
            self._by_category[cat].append(tool.name)
        log.debug(f"Registered tool '{tool.name}' in category '{cat}'")

    def register_many(self, tools: list[VizierTool]) -> None:
        for t in tools:
            self.register(t)

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            tool = self._tools.pop(name)
            category = self._by_category.get(tool.category)
            if category is not None and name in category:
                category.remove(name)
            return True
        return False

    # -- lookup -----------------------------------------------------------

    def get(self, name: str) -> VizierTool | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    # -- listing ----------------------------------------------------------

    @property
    def names(self) -> list[str]:
        return list(self._tools.keys())

    def all_tools(self) -> list[VizierTool]:
        return list(self._tools.values())

    def by_category(self) -> dict[str, list[VizierTool]]:
        result: dict[str, list[VizierTool]] = {}
        for category, names in self._by_category.items():
            result[category] = [self._tools[n] for n in names if n in self._tools]
        return result

    def definitions(self, include_dangerous: bool = True) -> list[dict[str, Any]]:
        """Return OpenAI-format tool definitions for the LLM.

        Args:
            include_dangerous: If False, omit tools flagged as dangerous.
        """
        defs: list[dict[str, Any]] = []
        for tool in self.all_tools():
            if not tool.enabled:
                continue
            if not include_dangerous and tool.dangerous:
                continue
            td: ToolDefinition = tool.definition
            defs.append({
                "type": "function",
                "function": {
                    "name": td.name,
                    "description": td.description,
                    "parameters": td.parameters,
                    "strict": td.strict,
                },
            })
        return defs

    def get_dangerous(self) -> list[str]:
        """Names of all dangerous tools."""
        return [t.name for t in self.all_tools() if t.dangerous]

    def enable(self, name: str) -> bool:
        tool = self._tools.get(name)
        if tool:
            tool.enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        tool = self._tools.get(name)
        if tool:
            tool.enabled = False
            return True
        return False
