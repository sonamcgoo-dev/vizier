"""
The Skill system — generic, composable skill packages that the agent
discovers and loads at runtime.

A *skill* is a self-contained bundle of tools, prompts, and configuration
that adds a capability to Vizier.  Skills live in the ``skills/`` directory
and are discovered via a ``skill.json`` manifest, mirroring the MCP server
``.json`` standard.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import logging
from pathlib import Path
from typing import Any

from vizier.core.tool import VizierTool
from vizier.utils import get_base_dir

log = logging.getLogger("vizier.skill")


class SkillDescriptor:
    """Metadata for a skill loaded from its ``skill.json`` manifest."""

    def __init__(self, manifest: dict[str, Any], path: Path):
        self.name: str = manifest.get("name", "unnamed")
        self.description: str = manifest.get("description", "")
        self.version: str = manifest.get("version", "0.0.0")
        self.author: str = manifest.get("author", "unknown")
        self.entry_point: str = manifest.get("entry_point", "")
        self.tools: list[str] = manifest.get("tools", [])
        self.prompts: list[str] = manifest.get("prompts", [])
        self.path: Path = path
        self.enabled: bool = manifest.get("enabled", True)
        self.requires: list[str] = manifest.get("requires", [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "entry_point": self.entry_point,
            "tools": self.tools,
            "prompts": self.prompts,
            "path": str(self.path),
            "enabled": self.enabled,
            "requires": self.requires,
        }


class Skill:
    """Base class for skills.  Subclass and override :meth:`get_tools`."""

    name: str = "base"
    description: str = ""

    def __init__(self, context: Any | None = None):
        self._ctx = context

    def get_tools(self) -> list[VizierTool]:
        """Return the list of tools this skill provides."""
        return []

    def get_prompts(self) -> dict[str, str]:
        """Return named prompt templates this skill provides."""
        return {}

    def on_load(self) -> None:
        """Hook called after the skill is loaded."""

    def on_unload(self) -> None:
        """Hook called before the skill is unloaded."""


class SkillRegistry:
    """Discovers, loads, and manages skills."""

    def __init__(self):
        self.skills_dir = get_base_dir() / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._loaded: dict[str, Skill] = {}
        self._descriptors: dict[str, SkillDescriptor] = {}

    def discover(self) -> list[SkillDescriptor]:
        """Scan the skills directory and return descriptors for all found skills."""
        self._descriptors.clear()
        for entry in self.skills_dir.iterdir():
            manifest_path = entry / "skill.json"
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    desc = SkillDescriptor(manifest, entry)
                    self._descriptors[desc.name] = desc
                except Exception as e:
                    log.warning(f"Failed to load skill manifest at {manifest_path}: {e}")
        return list(self._descriptors.values())

    def load(self, name: str) -> Skill | None:
        """Load a skill by name."""
        if name in self._loaded:
            return self._loaded[name]
        if name not in self._descriptors:
            return None
        desc = self._descriptors[name]
        if not desc.enabled:
            return None
        entry_path = desc.path / f"{desc.entry_point}.py"
        if not entry_path.exists():
            log.error(f"Skill entry point not found: {entry_path}")
            return None
        spec = importlib.util.spec_from_file_location(
            f"vizier.skill.{name}", entry_path
        )
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Find the Skill subclass
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if inspect.isclass(attr) and issubclass(attr, Skill) and attr is not Skill:
                instance = attr(context=self._ctx)
                instance.on_load()
                self._loaded[name] = instance
                log.info(f"Loaded skill: {name}")
                return instance
        log.warning(f"Skill '{name}' did not define a Skill subclass")
        return None

    def load_all(self) -> list[Skill]:
        """Load all discovered, enabled skills."""
        self.discover()
        skills: list[Skill] = []
        for name in list(self._descriptors.keys()):
            skill = self.load(name)
            if skill:
                skills.append(skill)
        return skills

    def all_tools(self) -> list[VizierTool]:
        """Convenience: gather all tools from all loaded skills."""
        tools: list[VizierTool] = []
        for skill in self._loaded.values():
            tools.extend(skill.get_tools())
        return tools

    def get(self, name: str) -> Skill | None:
        return self._loaded.get(name)
