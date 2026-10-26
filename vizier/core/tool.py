"""
Base tool class and tool registry for Vizier.

Every capability that the agent can invoke — computer control, filesystem
operations, shell commands, MCP server tools, coding helpers — is expressed
as a subclass of :class:`VizierTool` and registered with the
:class:`ToolRegistry`.
"""
from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from typing import Any

from vizier.core.types import ToolCategory, ToolDefinition


class VizierTool:
    """Base class for all Vizier tools.

    Subclasses override :meth:`execute` and set the class attributes
    ``name``, ``description``, ``parameters`` (JSON Schema), ``category``,
    and ``dangerous`` (whether the tool can harm the system and thus
    requires a YOLO confirmation dialog when YOLO mode is off).
    """

    name: str = "unnamed"
    description: str = ""
    parameters: dict[str, Any] = {}
    category: str = ToolCategory.CUSTOM.value
    dangerous: bool = False
    enabled: bool = True

    # The optional async flag — most tools are synchronous for simplicity.
    is_async: bool = False

    def __init__(self, context: ToolExecutionContext | None = None):
        self._ctx = context

    # -- core API ---------------------------------------------------------

    def execute(self, **kwargs: Any) -> str:
        """Execute the tool and return a string result.

        Override in subclasses.  For async tools set ``is_async = True``
        and override :meth:`execute_async` instead.
        """
        raise NotImplementedError

    async def execute_async(self, **kwargs: Any) -> str:
        """Async variant — override when ``is_async`` is True."""
        # Default bridge: call sync version (subclass should override both
        # or just the sync version).
        return self.execute(**kwargs)  # type: ignore[return-value]

    # -- introspection ----------------------------------------------------

    @property
    def definition(self) -> ToolDefinition:
        """Return the OpenAI-compatible tool definition for this tool."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            category=self.category,
            dangerous=self.dangerous,
        )

    @classmethod
    def from_function(
        cls,
        func: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
        category: str = ToolCategory.CUSTOM.value,
        dangerous: bool = False,
    ) -> FunctionTool:
        """Create a :class:`FunctionTool` wrapper around a plain function."""
        return FunctionTool(
            func=func,
            name=name or func.__name__,
            description=description or (func.__doc__ or "").strip(),
            category=category,
            dangerous=dangerous,
        )


class FunctionTool(VizierTool):
    """Wrap a plain Python function as a VizierTool."""

    def __init__(
        self,
        func: Callable[..., Any],
        name: str,
        description: str,
        category: str,
        dangerous: bool,
    ):
        super().__init__()
        self._func = func
        self.name = name
        self.description = description
        self.category = category
        self.dangerous = dangerous
        self.parameters = _infer_schema(func)

    def execute(self, **kwargs: Any) -> str:
        result = self._func(**kwargs)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, indent=2)


def _infer_schema(func: Callable[..., Any]) -> dict[str, Any]:
    """Infer a JSON-Schema parameter object from a Python function signature."""
    import typing

    try:
        hints = typing.get_type_hints(func)
    except Exception:
        hints = {}

    sig = inspect.signature(func)
    props: dict[str, Any] = {}
    required: list[str] = []
    type_map = {
        str: "string", int: "integer", float: "number",
        bool: "boolean", list: "array", dict: "object",
    }

    def _json_type(annotation: Any) -> str:
        if annotation is inspect.Parameter.empty:
            return "string"
        origin = typing.get_origin(annotation)
        if origin is typing.Union or str(origin) == "types.UnionType":
            args = [a for a in typing.get_args(annotation) if a is not type(None)]
            if len(args) == 1:
                return _json_type(args[0])
            return "string"
        if origin in (list, tuple, set):
            return "array"
        if origin is dict:
            return "object"
        return type_map.get(annotation, "string")

    for pname, param in sig.parameters.items():
        if param.default is inspect.Parameter.empty:
            required.append(pname)
        ann = hints.get(pname, param.annotation)
        props[pname] = {
            "type": _json_type(ann),
            "description": "",
        }
    schema: dict[str, Any] = {
        "type": "object",
        "properties": props,
    }
    if required:
        schema["required"] = required
    return schema


class ToolExecutionContext:
    """Passed to tools so they can access agent-level services."""

    def __init__(self, **services: Any):
        self._services = services

    def get(self, name: str, default: Any = None) -> Any:
        return self._services.get(name, default)

    @property
    def llm_provider(self):
        return self._services.get("llm_provider")

    @property
    def mcp_client(self):
        return self._services.get("mcp_client")

    @property
    def computer(self):
        return self._services.get("computer")

    @property
    def filesystem(self):
        return self._services.get("filesystem")
