"""
Persistent configuration for Vizier.

Stores user preferences, last-used model path, MCP server manifests,
YOLO state, and hardware-tier recommendations.  The config file lives
in the user data directory as ``config.json`` and is transparently
read/written by :class:`Config`.

Writes are atomic and keep a ``.bak`` copy so a crash or power loss cannot
leave the application without a usable configuration.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from vizier.utils import get_data_dir

log = logging.getLogger("vizier.config")

_DEFAULTS: dict[str, Any] = {
    "model_path": "",
    "model_n_ctx": 4096,
    "model_n_gpu_layers": 0,        # number of layers to offload to GPU
    "model_temperature": 0.7,
    "model_top_p": 0.9,
    "model_repeat_penalty": 1.1,
    "yolo_enabled": False,
    "yolo_warned": False,
    "mcp_servers": [],              # list of {name, type, command, args, url, ...}
    "mcp_auto_start": True,
    "max_tool_rounds": 10,
    "system_prompt": (
        "You are Vizier, a local AI agent and royal advisor. "
        "You operate entirely on the user's machine — no cloud, no telemetry. "
        "You have powerful computer-use, filesystem, shell, and coding tools. "
        "Think carefully, act decisively, and always keep the user informed."
    ),
    "recent_models": [],
    "last_session": "",
    "theme": "royal",               # only theme, always black/red/white
}

_INT_RANGES: dict[str, tuple[int, int]] = {
    "model_n_ctx": (256, 1_048_576),
    "model_n_gpu_layers": (-1, 1024),
    "max_tool_rounds": (1, 200),
}

_FLOAT_RANGES: dict[str, tuple[float, float]] = {
    "model_temperature": (0.0, 2.0),
    "model_top_p": (0.0, 1.0),
    "model_repeat_penalty": (0.1, 4.0),
}


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _as_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _as_float(value: Any, default: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read %s: %s", path, exc)
        return None
    return data if isinstance(data, dict) else None


@dataclass
class Config:
    """User configuration loaded from / saved to ``config.json``."""
    model_path: str = ""
    model_n_ctx: int = 4096
    model_n_gpu_layers: int = 0
    model_temperature: float = 0.7
    model_top_p: float = 0.9
    model_repeat_penalty: float = 1.1
    yolo_enabled: bool = False
    yolo_warned: bool = False
    mcp_servers: list[dict[str, Any]] = field(default_factory=list)
    mcp_auto_start: bool = True
    max_tool_rounds: int = 10
    system_prompt: str = _DEFAULTS["system_prompt"]
    recent_models: list[str] = field(default_factory=list)
    last_session: str = ""
    theme: str = "royal"

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        path = path or (get_data_dir() / "config.json")
        data: dict[str, Any] = {}
        if path.exists():
            data = _read_json(path) or {}
            if not data:
                backup = path.with_name(path.name + ".bak")
                recovered = _read_json(backup) if backup.exists() else None
                if recovered:
                    log.warning("Recovered configuration from %s", backup)
                    data = recovered
        merged = {**_DEFAULTS, **data}
        cfg = cls()
        for key in cls.__dataclass_fields__:
            if key in merged:
                setattr(cfg, key, merged[key])
        return cfg.sanitize()

    def sanitize(self) -> Config:
        """Coerce every field to a safe type and range."""
        defaults = Config()
        self.model_path = str(self.model_path or "")
        self.yolo_enabled = _as_bool(self.yolo_enabled, defaults.yolo_enabled)
        self.yolo_warned = _as_bool(self.yolo_warned, defaults.yolo_warned)
        self.mcp_auto_start = _as_bool(self.mcp_auto_start, defaults.mcp_auto_start)

        for key, (low, high) in _INT_RANGES.items():
            setattr(
                self,
                key,
                _as_int(getattr(self, key), getattr(defaults, key), low, high),
            )
        for key, (low, high) in _FLOAT_RANGES.items():
            setattr(
                self,
                key,
                round(
                    _as_float(getattr(self, key), getattr(defaults, key), low, high),
                    4,
                ),
            )

        if not isinstance(self.mcp_servers, list):
            self.mcp_servers = []
        else:
            self.mcp_servers = [
                dict(server) for server in self.mcp_servers if isinstance(server, dict)
            ]

        if not isinstance(self.recent_models, list):
            self.recent_models = []
        else:
            self.recent_models = [
                str(name) for name in self.recent_models if isinstance(name, str)
            ][:20]

        self.system_prompt = str(self.system_prompt or defaults.system_prompt)
        self.last_session = str(self.last_session or "")
        self.theme = "royal"
        return self

    def save(self, path: Path | None = None) -> None:
        path = path or (get_data_dir() / "config.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self.sanitize())
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        temp_path = path.with_name(path.name + ".tmp")
        temp_path.write_text(payload, encoding="utf-8")
        if path.exists():
            try:
                shutil.copy2(path, path.with_name(path.name + ".bak"))
            except OSError:
                log.debug("Could not create config backup", exc_info=True)
        os.replace(temp_path, path)
        log.debug("Config saved to %s", path)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def set(self, key: str, value: Any) -> None:
        if key in self.__dataclass_fields__:
            setattr(self, key, value)
            self.sanitize()
        else:
            log.warning("Unknown config key: %s", key)

    def update(self, values: dict[str, Any]) -> Config:
        """Update multiple values, ignoring unknown keys."""
        for key, value in values.items():
            if key in self.__dataclass_fields__:
                setattr(self, key, value)
            else:
                log.warning("Unknown config key: %s", key)
        return self.sanitize()

    def to_dict(self) -> dict[str, Any]:
        """Return the configuration as a JSON-serialisable dictionary."""
        return asdict(self.sanitize())

    def reset(self) -> Config:
        """Reset every field to its default value."""
        defaults = Config()
        for key in self.__dataclass_fields__:
            setattr(self, key, getattr(defaults, key))
        return self
