"""
Utility functions shared across the Vizier project.
"""
from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_base_dir() -> Path:
    """Return the base directory of the Vizier installation."""
    return Path(__file__).resolve().parent.parent


def get_resource_dir() -> Path:
    """Return the directory holding bundled resources (assets, docs).

    Inside a PyInstaller build resources are extracted to ``sys._MEIPASS``;
    in a source checkout they live next to the package.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle)
    return get_base_dir().parent


def get_asset_path(*parts: str) -> Path:
    """Resolve a bundled asset path, falling back to the source tree."""
    candidates = [
        get_resource_dir() / "assets" / Path(*parts),
        get_base_dir().parent / "assets" / Path(*parts),
        get_base_dir() / "assets" / Path(*parts),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def get_data_dir() -> Path:
    """Return the *user* data directory (for config, models, etc.)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.environ.get("APPDATA", ""))
        p = (Path(base) / "Vizier") if base else (Path.home() / ".vizier")
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "Vizier"
    else:
        p = Path.home() / ".local" / "share" / "vizier"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_models_dir() -> Path:
    """Directory where GGUF models are stored."""
    p = get_data_dir() / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_cache_dir() -> Path:
    """Directory for caches (HuggingFace hub cache, screenshots, etc.)."""
    p = get_data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------

def _run_hidden(command: list[str]) -> str:
    """Run a command without flashing a console window on Windows."""
    import subprocess

    kwargs: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "timeout": 10,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.run(command, **kwargs)
    return (proc.stdout or "").strip()


def _powershell(script: str) -> str:
    if os.name != "nt":
        return ""
    return _run_hidden([
        "powershell", "-NoProfile", "-NonInteractive", "-Command", script,
    ])


def detect_hardware() -> dict[str, Any]:
    """Detect the host hardware so we can recommend models."""
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "cpu_model": "Unknown",
        "cpu_cores": os.cpu_count() or 1,
        "ram_gb": _get_total_ram_gb(),
        "gpus": [],
    }
    try:
        if os.name == "nt":
            out = _powershell(
                "(Get-CimInstance Win32_Processor | Select-Object -First 1 "
                "-ExpandProperty Name)"
            )
            if out:
                info["cpu_model"] = out.splitlines()[0].strip()
        elif sys.platform == "darwin":
            out = _run_hidden(["sysctl", "-n", "machdep.cpu.brand_string"])
            if out:
                info["cpu_model"] = out
        else:
            out = _run_hidden(["sh", "-c", "cat /proc/cpuinfo | grep 'model name' | head -1"])
            if ":" in out:
                info["cpu_model"] = out.split(":", 1)[1].strip()
    except Exception:
        pass
    info["gpus"] = _detect_gpus()
    return info


def _get_total_ram_gb() -> float:
    try:
        import psutil  # type: ignore[import-not-found]

        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        pass
    try:
        if os.name == "nt":
            out = _powershell(
                "(Get-CimInstance Win32_ComputerSystem "
                "| Select-Object -ExpandProperty TotalPhysicalMemory)"
            )
            if out.isdigit():
                return round(int(out) / (1024 ** 3), 1)
        elif sys.platform == "darwin":
            out = _run_hidden(["sysctl", "-n", "hw.memsize"])
            if out.isdigit():
                return round(int(out) / (1024 ** 3), 1)
        else:
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return round(kb / (1024 ** 2), 1)
    except Exception:
        pass
    return 0.0


def _detect_gpus() -> list[dict[str, Any]]:
    """Detect GPUs, returning a list of dicts with vendor/model/VRAM."""
    gpus: list[dict[str, Any]] = []
    if os.name != "nt":
        return gpus
    try:
        out = _powershell(
            "Get-CimInstance Win32_VideoController | "
            "ForEach-Object { \"$($_.Name)|$($_.AdapterRAM)\" }"
        )
        for line in out.splitlines():
            line = line.strip()
            if not line or "|" not in line:
                continue
            name, _, ram_text = line.partition("|")
            name = name.strip()
            entry: dict[str, Any] = {
                "vendor": _gpu_vendor(name),
                "name": name or "Unknown",
                "vram_gb": 0,
            }
            try:
                ram = int((ram_text or "0").strip())
                # AdapterRAM is a signed 32-bit value and wraps for >4 GB
                # cards; treat suspicious values as unknown rather than lie.
                if 0 < ram < 2 ** 31:
                    entry["vram_gb"] = round(ram / (1024 ** 3), 1)
            except (TypeError, ValueError):
                pass
            if entry["vram_gb"] > 0 or entry["name"] != "Unknown":
                gpus.append(entry)
    except Exception:
        pass
    return gpus


def _gpu_vendor(name: str) -> str:
    n = name.lower()
    if "nvidia" in n or "geforce" in n or "quadro" in n or "rtx" in n or "gtx" in n:
        return "NVIDIA"
    if "amd" in n or "radeon" in n or "rx " in n:
        return "AMD"
    if "intel" in n or "uhd" in n or "hd graphics" in n:
        return "Intel"
    if "apple" in n or "m1" in n or "m2" in n or "m3" in n or "m4" in n:
        return "Apple"
    return "Unknown"


def get_hardware_tier() -> str:
    """Classify the machine into an LLM-runnable tier."""
    gpus = detect_hardware()["gpus"]
    best_vram = max((g["vram_gb"] for g in gpus), default=0)
    if best_vram == 0:
        return "cpu"
    if best_vram < 12:
        return "gpu_8"
    if best_vram < 20:
        return "gpu_16"
    if best_vram < 40:
        return "gpu_24"
    if best_vram < 64:
        return "gpu_48"
    return "gpu_64+"


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def load_json(path: str | Path, default: Any = None) -> Any:
    """Load a JSON file, returning *default* on error."""
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: str | Path, data: Any) -> None:
    """Save *data* as pretty-printed JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# ANSI / Console colour helpers (CLI mode)
# ---------------------------------------------------------------------------

class Colors:
    """ANSI escape codes — blood-red on black theme."""
    RED = "\033[38;2;139;0;0m"
    RED_BOLD = "\033[1;38;2;160;0;0m"
    WHITE = "\033[97m"
    BLACK_BG = "\033[48;2;0;0;0m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREY = "\033[38;2;128;128;128m"
    GREEN = "\033[38;2;0;180;0m"
    ORANGE = "\033[38;2;230;120;0m"


def cprint(text: str, color: str = "", end: str = "\n") -> None:
    """Print with optional ANSI colour."""
    if color:
        print(f"{color}{text}{Colors.RESET}", end=end)
    else:
        print(text, end=end)

