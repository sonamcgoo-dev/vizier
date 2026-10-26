"""Tests for configuration persistence."""
from __future__ import annotations

import json

from vizier.config import Config


def test_defaults() -> None:
    config = Config()
    assert config.max_tool_rounds == 10
    assert config.yolo_enabled is False
    assert config.theme == "royal"
    assert isinstance(config.system_prompt, str)


def test_save_and_load(tmp_path) -> None:
    path = tmp_path / "config.json"
    config = Config()
    config.model_path = "model.gguf"
    config.model_temperature = 0.25
    config.yolo_enabled = True
    config.save(path)

    loaded = Config.load(path)
    assert loaded.model_path == "model.gguf"
    assert loaded.model_temperature == 0.25
    assert loaded.yolo_enabled is True


def test_load_invalid_json_falls_back_to_defaults(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    loaded = Config.load(path)
    assert loaded.max_tool_rounds == 10


def test_load_ignores_unknown_keys(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"unknown": 1, "max_tool_rounds": 3}), encoding="utf-8")
    loaded = Config.load(path)
    assert loaded.max_tool_rounds == 3
    assert not hasattr(loaded, "unknown")


def test_update_and_to_dict() -> None:
    config = Config()
    config.update({"max_tool_rounds": 4, "nope": 1})
    data = config.to_dict()
    assert data["max_tool_rounds"] == 4
    assert "nope" not in data


def test_reset() -> None:
    config = Config()
    config.yolo_enabled = True
    config.model_path = "x"
    config.reset()
    assert config.yolo_enabled is False
    assert config.model_path == ""


def test_sanitizes_out_of_range_and_wrong_types() -> None:
    config = Config()
    config.model_n_ctx = "not-a-number"  # type: ignore[assignment]
    config.model_n_gpu_layers = 99_999  # type: ignore[assignment]
    config.model_temperature = 9.5  # type: ignore[assignment]
    config.model_top_p = "0.5"  # type: ignore[assignment]
    config.max_tool_rounds = 0  # type: ignore[assignment]
    config.yolo_enabled = "yes"  # type: ignore[assignment]
    config.mcp_servers = "nope"  # type: ignore[assignment]
    config.recent_models = ["a", 5, "b"]  # type: ignore[list-item]
    config.theme = "light"

    config.sanitize()

    assert config.model_n_ctx == 4096
    assert config.model_n_gpu_layers == 1024
    assert config.model_temperature == 2.0
    assert config.model_top_p == 0.5
    assert config.max_tool_rounds == 1
    assert config.yolo_enabled is True
    assert config.mcp_servers == []
    assert config.recent_models == ["a", "b"]
    assert config.theme == "royal"


def test_atomic_save_creates_backup(tmp_path) -> None:
    path = tmp_path / "config.json"
    config = Config()
    config.max_tool_rounds = 3
    config.save(path)
    config.max_tool_rounds = 7
    config.save(path)

    assert json.loads(path.read_text(encoding="utf-8"))["max_tool_rounds"] == 7
    backup = tmp_path / "config.json.bak"
    assert backup.exists()
    assert json.loads(backup.read_text(encoding="utf-8"))["max_tool_rounds"] == 3
    assert not (tmp_path / "config.json.tmp").exists()


def test_recovers_from_corrupt_config_using_backup(tmp_path) -> None:
    path = tmp_path / "config.json"
    backup = tmp_path / "config.json.bak"
    path.write_text("{broken", encoding="utf-8")
    backup.write_text(json.dumps({"max_tool_rounds": 5}), encoding="utf-8")

    loaded = Config.load(path)

    assert loaded.max_tool_rounds == 5


def test_set_ignores_unknown_keys() -> None:
    config = Config()
    config.set("max_tool_rounds", 3)
    config.set("does_not_exist", 1)
    assert config.max_tool_rounds == 3
    assert not hasattr(config, "does_not_exist")
