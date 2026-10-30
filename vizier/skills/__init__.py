"""Built-in skill catalog for Vizier.

This adds a lightweight, reusable set of project and workflow skills that ship with
Vizier and can be surfaced to the model or UI as starter capability prompts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class SkillDefinition:
    """A single reusable Vizier skill."""

    name: str
    description: str
    category: str
    tags: list[str] = field(default_factory=list)
    prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_SKILLS: list[SkillDefinition] = [
    SkillDefinition(
        name="filesystem-overview",
        description="Inspect, read, and summarize project files without changing them.",
        category="workspace",
        tags=["read", "inspect", "files"],
        prompt=(
            "Review the relevant files in the workspace, identify the main architecture, "
            "and summarize the current design before making any change."
        ),
    ),
    SkillDefinition(
        name="repo-maintenance",
        description="Keep repository state clean, consistent, and release-ready.",
        category="maintenance",
        tags=["git", "docs", "release", "quality"],
        prompt=(
            "Check repository health, remove stale clutter, verify docs, validate packaging, "
            "and prepare a release-safe summary."
        ),
    ),
    SkillDefinition(
        name="debugging",
        description="Diagnose problems in a bounded, evidence-first way.",
        category="debugging",
        tags=["triage", "logs", "root-cause"],
        prompt=(
            "Reproduce the issue, inspect the relevant code path, identify the root cause, "
            "and propose a minimal fix with verification steps."
        ),
    ),
    SkillDefinition(
        name="research-and-docs",
        description="Collect evidence from docs, config, and repo files and write concise guidance.",
        category="documentation",
        tags=["docs", "research", "summary"],
        prompt=(
            "Read the relevant docs and source files, synthesize the facts, and produce "
            "clear guidance or release notes for the user."
        ),
    ),
    SkillDefinition(
        name="mcp-integration",
        description="Connect local tools and external MCP servers to Vizier safely.",
        category="integration",
        tags=["mcp", "servers", "tools"],
        prompt=(
            "Configure the correct MCP server manifests, validate their transport settings, "
            "and document how to enable or disable each server safely."
        ),
    ),
]


class SkillCatalog:
    """Container that exposes a curated default skill set."""

    def __init__(self, skills: list[SkillDefinition] | None = None):
        self.skills = list(skills) if skills is not None else list(DEFAULT_SKILLS)

    def names(self) -> list[str]:
        return [skill.name for skill in self.skills]

    def get(self, name: str) -> SkillDefinition | None:
        for skill in self.skills:
            if skill.name == name:
                return skill
        return None

    def as_dicts(self) -> list[dict[str, Any]]:
        return [skill.to_dict() for skill in self.skills]

    def add(self, skill: SkillDefinition) -> None:
        self.skills.append(skill)


def get_default_skills() -> list[dict[str, Any]]:
    """Return a JSON-serialisable default skill catalog."""
    return SkillCatalog().as_dicts()


__all__ = ["SkillDefinition", "SkillCatalog", "DEFAULT_SKILLS", "get_default_skills"]
