"""Tests for the self-diagnostics used by ``vizier doctor`` and the About box."""
from __future__ import annotations

from pathlib import Path

import vizier.config
import vizier.diagnostics as diagnostics
import vizier.utils
from vizier.config import Config


def test_as_dict_counts_statuses() -> None:
    results = [
        diagnostics.CheckResult("a", diagnostics.OK),
        diagnostics.CheckResult("b", diagnostics.WARN, "detail"),
        diagnostics.CheckResult("c", diagnostics.FAIL),
        diagnostics.CheckResult("d", diagnostics.OK),
    ]

    data = diagnostics.as_dict(results)

    assert data["ok"] == 2
    assert data["warnings"] == 1
    assert data["failures"] == 1
    assert data["checks"][1]["name"] == "b"


def test_symbols() -> None:
    assert diagnostics.CheckResult("x", diagnostics.OK).symbol == "OK"
    assert diagnostics.CheckResult("x", diagnostics.WARN).symbol == "!"
    assert diagnostics.CheckResult("x", diagnostics.FAIL).symbol == "X"
    assert diagnostics.CheckResult("x", diagnostics.SKIP).symbol == "-"


def test_run_checks_never_raises(monkeypatch) -> None:
    def explode() -> diagnostics.CheckResult:
        raise RuntimeError("boom")

    monkeypatch.setattr(diagnostics, "check_python", explode)
    results = diagnostics.run_checks()

    failed = next(r for r in results if r.name == "explode")
    assert failed.status == diagnostics.FAIL
    assert "boom" in failed.detail


def test_data_dir_check_reports_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vizier.utils, "get_data_dir", lambda: tmp_path)

    result = diagnostics.check_data_dir()

    assert result.status == diagnostics.OK
    assert str(tmp_path) in result.detail
    assert not (tmp_path / ".write-test").exists()


def test_config_check_missing_model(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vizier.config, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(vizier.utils, "get_data_dir", lambda: tmp_path)
    config = Config()
    config.model_path = str(tmp_path / "missing.gguf")
    config.save(tmp_path / "config.json")

    model_result = diagnostics.check_model()
    config_result = diagnostics.check_config()

    assert model_result.status == diagnostics.FAIL
    assert "missing.gguf" in model_result.detail
    assert config_result.status == diagnostics.OK


def test_model_check_prefers_selected_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vizier.config, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(vizier.utils, "get_data_dir", lambda: tmp_path)
    model = tmp_path / "tiny.gguf"
    model.write_bytes(b"GGUF")
    config = Config()
    config.model_path = str(model)
    config.save(tmp_path / "config.json")

    result = diagnostics.check_model()

    assert result.status == diagnostics.OK
    assert "tiny.gguf" in result.detail


def test_hardware_check_is_tolerant(monkeypatch) -> None:
    def broken() -> dict:
        raise OSError("no hardware")

    monkeypatch.setattr(vizier.utils, "detect_hardware", broken)

    result = diagnostics.check_hardware()

    assert result.status == diagnostics.WARN
    assert "no hardware" in result.detail


def test_tool_registry_check() -> None:
    result = diagnostics.check_tools()
    assert result.status == diagnostics.OK
    assert "tools registered" in result.detail


def test_logging_check_creates_log_dir(tmp_path, monkeypatch) -> None:
    import vizier.logging_setup

    monkeypatch.setattr(vizier.logging_setup, "get_data_dir", lambda: tmp_path)

    result = diagnostics.check_logging()

    assert result.status == diagnostics.OK
    assert Path(result.detail).parent.name == "logs"
