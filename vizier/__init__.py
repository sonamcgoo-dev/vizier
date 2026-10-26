"""
Vizier - A local AI agent framework for computer use, filesystem management, 
and general assistance. Named after the royal advisor — Vizier knows all, 
sees all, and acts on your behalf while keeping every computation on your machine.

No cloud. No BYOK. No telemetry. 100 % local.
"""
from vizier.__version__ import __codename__ as __codename__
from vizier.__version__ import __version__ as __version__
from vizier.core.tool import VizierTool

# Core imports exposed at package level for convenience
from vizier.core.types import Message, Role, ToolCall, ToolCategory, ToolDefinition, ToolResult

__all__ = [
    "Message",
    "Role",
    "ToolCall",
    "ToolCategory",
    "ToolDefinition",
    "ToolResult",
    "VizierTool",
    "__codename__",
    "__version__",
]
