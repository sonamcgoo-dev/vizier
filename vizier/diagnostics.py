"""
Self-diagnostics for Vizier.

The :func:`run_checks` helper powers ``vizier doctor`` and the GUI health
panel.  It never raises: every check degrades to a failed/skipped result so a
broken optional dependency cannot stop the report from being produced.
"""
from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

OK = "ok"
WARN = "warn"
FAIL = "fail"
SKIP = "skip"


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str = ""

    @property
    def symbol(self) -> str:
        return {OK: "OK", WARN: "!", FAIL: "X", SKIP: "-"}.get(self.status, "?")


def _module_version(module_name: str, distribution: str | None = None) -> tuple[bool, str]:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return False, str(exc)
    version = getattr(module, "__version__", "")
    if not version:
        try:
            version = importlib.metadata.version(distribution or module_name)
        except importlib.metadata.PackageNotFoundError:
            version = ""
    return True, str(version) if version else "installed"


def check_python() -> CheckResult:
    return CheckResult("Python", OK, platform.python_version())


def check_platform() -> CheckResult:
    detail = f"{platform.system()} {platform.release()} ({platform.machine()})"
    if sys.platform not in ("win32", "darwin", "linux"):
        return CheckResult("Operating system", WARN, detail)
    return CheckResult("Operating system", OK, detail)


def check_data_dir() -> CheckResult:
    from vizier.utils import get_data_dir

    try:
        data_dir = get_data_dir()
        probe = data_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return CheckResult("Data directory", OK, str(data_dir))
    except Exception as exc:
        return CheckResult("Data directory", FAIL, str(exc))


def check_config() -> CheckResult:
    from vizier.config import Config

    try:
        config = Config.load()
        return CheckResult(
            "Configuration",
            OK,
            f"model={'set' if config.model_path else 'not set'}, "
            f"yolo={'on' if config.yolo_enabled else 'off'}, "
            f"mcp_servers={len(config.mcp_servers)}",
        )
    except Exception as exc:
        return CheckResult("Configuration", FAIL, str(exc))


def check_gui() -> CheckResult:
    available, detail = _module_version("PySide6")
    return CheckResult(
        "Qt GUI (PySide6)", OK if available else FAIL, detail
    )


def check_llama() -> CheckResult:
    available, detail = _module_version("llama_cpp", "llama-cpp-python")
    return CheckResult(
        "Local inference (llama-cpp-python)",
        OK if available else FAIL,
        detail,
    )


def check_mcp() -> CheckResult:
    available, detail = _module_version("mcp")
    if not available:
        return CheckResult("MCP support", WARN, "mcp package not installed")
    return CheckResult("MCP support", OK, detail)


def check_computer_use() -> CheckResult:
    missing = [
        name
        for name in ("pyautogui", "pyscreeze", "PIL", "pygetwindow", "pyperclip")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        return CheckResult(
            "Computer-use tools", WARN, "missing: " + ", ".join(missing)
        )
    return CheckResult("Computer-use tools", OK, "screen, mouse, keyboard ready")


def check_model() -> CheckResult:
    from vizier.config import Config
    from vizier.utils import get_models_dir

    config = Config.load()
    if config.model_path:
        path = Path(config.model_path)
        if not path.exists():
            return CheckResult("Selected model", FAIL, f"missing: {path}")
        if path.suffix.lower() != ".gguf":
            return CheckResult("Selected model", WARN, f"not a .gguf file: {path}")
        size_gb = path.stat().st_size / (1024 ** 3)
        return CheckResult(
            "Selected model", OK, f"{path.name} ({size_gb:.2f} GB)"
        )
    local = sorted(get_models_dir().glob("*.gguf"))
    if local:
        return CheckResult(
            "Selected model",
            WARN,
            f"none selected; {len(local)} local model(s) available",
        )
    return CheckResult("Selected model", WARN, "none - load a GGUF model to chat")


def check_tools() -> CheckResult:
    try:
        from vizier.config import Config
        from vizier.tools import VizierServices

        services = VizierServices(Config())
        registry = services.build_tools()
        return CheckResult("Tool registry", OK, f"{len(registry.names)} tools registered")
    except Exception as exc:
        return CheckResult("Tool registry", FAIL, str(exc))


def check_logging() -> CheckResult:
    from vizier.logging_setup import get_log_dir, get_log_file

    try:
        log_dir = get_log_dir()
        probe = log_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return CheckResult("Logging", OK, str(get_log_file()))
    except Exception as exc:
        return CheckResult("Logging", FAIL, str(exc))


def check_disk_space() -> CheckResult:
    try:
        from vizier.utils import get_data_dir

        usage = os.statvfs(get_data_dir()) if hasattr(os, "statvfs") else None
        if usage is not None:
            free_gb = usage.f_bavail * usage.f_frsize / (1024 ** 3)
        else:
            import shutil

            free_gb = shutil.disk_usage(get_data_dir()).free / (1024 ** 3)
        status = OK if free_gb >= 5 else WARN
        return CheckResult("Disk space", status, f"{free_gb:.1f} GB free")
    except Exception as exc:
        return CheckResult("Disk space", WARN, str(exc))


def check_hardware() -> CheckResult:
    try:
        from vizier.utils import detect_hardware, get_hardware_tier

        hw = detect_hardware()
        gpu = hw["gpus"][0]["name"] if hw["gpus"] else "CPU only"
        return CheckResult(
            "Hardware",
            OK,
            f"{hw['cpu_model']}, {hw['ram_gb']} GB RAM, {gpu} "
            f"(tier: {get_hardware_tier()})",
        )
    except Exception as exc:
        return CheckResult("Hardware", WARN, str(exc))


def run_checks() -> list[CheckResult]:
    """Run every diagnostic check, in display order."""
    checks = [
        check_platform,
        check_python,
        check_data_dir,
        check_config,
        check_gui,
        check_llama,
        check_mcp,
        check_computer_use,
        check_tools,
        check_model,
        check_hardware,
        check_disk_space,
        check_logging,
    ]
    results: list[CheckResult] = []
    for check in checks:
        try:
            results.append(check())
        except Exception as exc:
            results.append(CheckResult(check.__name__, FAIL, str(exc)))
    return results


def as_dict(results: list[CheckResult]) -> dict[str, Any]:
    return {
        "ok": sum(r.status == OK for r in results),
        "warnings": sum(r.status == WARN for r in results),
        "failures": sum(r.status == FAIL for r in results),
        "checks": [r.__dict__ for r in results],
    }
