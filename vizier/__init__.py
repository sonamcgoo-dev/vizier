"""Public package exports for Vizier."""
from __future__ import annotations

from vizier.__version__ import __codename__ as __codename__
from vizier.__version__ import __version__ as __version__
from vizier.core.tool import VizierTool
from vizier.mcp_catalog import get_common_mcp_servers
from vizier.skills import SkillCatalog, get_default_skills

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
    "SkillCatalog",
    "get_common_mcp_servers",
    "get_default_skills",
    "__codename__",
    "__version__",
]
