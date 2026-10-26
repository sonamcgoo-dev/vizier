# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Vizier Windows release.

Builds a single onedir bundle containing:

    Vizier.exe       — desktop GUI (no console)
    VizierCLI.exe    — command-line interface (console)
    VizierMCP.exe    — MCP server for stdio / HTTP clients (console)

Run via ``scripts/build_windows.ps1`` or::

    pyinstaller --noconfirm --clean packaging/windows/Vizier.spec
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent.parent
ASSETS = ROOT / "assets"
VERSION_INFO = ROOT / "build" / "vizier_version_info.txt"

# ---------------------------------------------------------------------------
# Shared collection
# ---------------------------------------------------------------------------

datas = [
    (str(ASSETS), "assets"),
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "RELEASE_NOTES.md"), "."),
    (str(ROOT / "LICENSE"), "."),
]
binaries = []
hiddenimports = []

# Packages that rely on data files, native libraries, or dynamic imports.
for package in (
    "llama_cpp",
    "pyautogui",
    "pyscreeze",
    "pygetwindow",
    "pyperclip",
    "pytesseract",
    "PIL",
    "requests",
    "certifi",
    "psutil",
    "pydantic",
    "anyio",
    "httpx",
    "uvicorn",
    "starlette",
    "sse_starlette",
):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    except Exception:  # optional dependency not installed
        continue
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# Collect the MCP server/client tree without importing the optional ``mcp.cli``
# module, which requires typer and is not part of Vizier.
for package in ("mcp.client", "mcp.server", "mcp.shared", "mcp.os", "mcp.types"):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass
hiddenimports += ["mcp", "mcp.types"]

# Metadata is needed by importlib.metadata-based version checks.
for distribution in ("mcp", "pydantic", "llama-cpp-python", "certifi"):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass

# Keep the GUI modules out of the MCP server's archive.  PyInstaller scans
# imports inside functions, so the three entry points still pull in exactly
# the packages they need; this list only guarantees lazily referenced modules
# are present.  Qt is the single largest dependency, so the MCP executable
# should not carry it.
vizier_modules = collect_submodules("vizier")
ui_modules = [
    module
    for module in vizier_modules
    if module == "vizier.theme" or module.startswith("vizier.ui")
]
core_vizier_modules = [module for module in vizier_modules if module not in ui_modules]
hiddenimports += core_vizier_modules
hiddenimports += [
    "vizier.__main__",
    "vizier.logging_setup",
    "vizier.diagnostics",
    "mcp.server",
    "mcp.client",
    "mcp.server.stdio",
    "mcp.server.sse",
    "mcp.server.streamable_http",
    "sqlite3",
    "ssl",
    "ctypes",
]

excludes = [
    "tkinter",
    "matplotlib",
    "pandas",
    "scipy",
    "torch",
    "tensorflow",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "mcp.cli",
    # Optional accelerators / codecs that Vizier never loads.
    "hf_xet",
    "PIL.AvifImagePlugin",
    # Qt modules for Quick/QML, PDF, SVG, networking, and OpenGL are unused;
    # excluding the Python modules also stops their plugin dependencies from
    # being collected.  The post-build prune removes any remaining DLLs.
    "PySide6.QtNetwork",
    "PySide6.QtOpenGL",
    "PySide6.QtPdf",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtSvg",
    "PySide6.QtVirtualKeyboard",
]

common = dict(
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)


def build_exe(entry: str, name: str, console: bool, extra_hiddenimports=()):
    options = dict(common)
    options["hiddenimports"] = common["hiddenimports"] + list(extra_hiddenimports)
    analysis = Analysis([str(SPEC_DIR / entry)], **options)
    pyz = PYZ(analysis.pure)
    exe = EXE(
        pyz,
        analysis.scripts,
        [],
        exclude_binaries=True,
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=console,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(ASSETS / "vizier.ico") if ASSETS.joinpath("vizier.ico").exists() else None,
        version=str(VERSION_INFO) if VERSION_INFO.exists() else None,
    )
    return analysis, pyz, exe


a_gui, pyz_gui, exe_gui = build_exe(
    "vizier_gui.py",
    "Vizier",
    console=False,
    extra_hiddenimports=ui_modules + ["vizier.servers.mcp_server"],
)
a_cli, pyz_cli, exe_cli = build_exe(
    "vizier_cli.py",
    "VizierCLI",
    console=True,
    extra_hiddenimports=ui_modules + ["vizier.servers.mcp_server"],
)
a_mcp, pyz_mcp, exe_mcp = build_exe(
    "vizier_mcp.py",
    "VizierMCP",
    console=True,
    extra_hiddenimports=["vizier.servers.mcp_server"],
)

coll = COLLECT(
    exe_gui,
    a_gui.binaries,
    a_gui.datas,
    exe_cli,
    a_cli.binaries,
    a_cli.datas,
    exe_mcp,
    a_mcp.binaries,
    a_mcp.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Vizier",
)
