#!/usr/bin/env python
"""Remove runtime files the Vizier bundle never uses.

The PySide6, Pillow, llama.cpp, and Hugging Face wheels all ship optional
components that PyInstaller collects conservatively.  This script applies a
small, explicit allowlist of removals after the bundle is built and before the
packaged smoke tests run, so the release stays lean without guesswork.

Nothing is removed unless it matches a pattern below.  The script refuses to
touch anything outside ``dist/Vizier`` and verifies that the files required to
launch the GUI, CLI, and MCP server are still present afterwards.

Usage::

    python scripts/prune_bundle.py
    python scripts/prune_bundle.py --bundle dist/Vizier --dry-run
"""
from __future__ import annotations

import argparse
import contextlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUNDLE = ROOT / "dist" / "Vizier"

# Keep this list boring and explicit: label -> paths/globs relative to the bundle.
# Every group must be safe to remove for all three executables.  Qt libraries
# that are loaded lazily (Quick, QML, PDF, network, SVG, OpenGL) are proven
# unused by ``vizier/ui``; the remaining plugins are only alternative backends.
PRUNE_GROUPS: list[tuple[str, list[str]]] = [
    (
        "llama.cpp static import libraries",
        ["_internal/llama_cpp/lib/*.lib"],
    ),
    (
        "Hugging Face xet accelerator (optional; HTTP fallback remains)",
        ["_internal/hf_xet"],
    ),
    (
        "Pillow AVIF codec (AVIF is never opened by Vizier)",
        ["_internal/PIL/_avif*.pyd"],
    ),
    (
        "Qt software OpenGL fallback (QWidget raster rendering only)",
        [
            "_internal/PySide6/opengl32sw.dll",
            "_internal/PySide6/Qt6OpenGL.dll",
        ],
    ),
    (
        "Qt Quick / QML (unused; the UI is widget-based)",
        [
            "_internal/PySide6/Qt6Quick.dll",
            "_internal/PySide6/Qt6Qml*.dll",
        ],
    ),
    (
        "Qt PDF (unused)",
        [
            "_internal/PySide6/Qt6Pdf.dll",
            "_internal/PySide6/plugins/imageformats/qpdf.dll",
        ],
    ),
    (
        "Qt Virtual Keyboard (unused)",
        [
            "_internal/PySide6/Qt6VirtualKeyboard.dll",
            "_internal/PySide6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll",
        ],
    ),
    (
        "Qt network stack (downloads use requests, not Qt)",
        [
            "_internal/PySide6/Qt6Network.dll",
            "_internal/PySide6/QtNetwork.pyd",
            "_internal/PySide6/plugins/tls",
            "_internal/PySide6/plugins/networkinformation",
        ],
    ),
    (
        "Qt translations (English source strings; no .qm catalogs needed)",
        ["_internal/PySide6/translations"],
    ),
    (
        "Qt SVG support (icons are bundled as PNG/ICO)",
        [
            "_internal/PySide6/Qt6Svg.dll",
            "_internal/PySide6/plugins/iconengines",
            "_internal/PySide6/plugins/imageformats/qsvg.dll",
        ],
    ),
    (
        "Unused Qt platform/input plugins",
        [
            "_internal/PySide6/plugins/platforms/qdirect2d.dll",
            "_internal/PySide6/plugins/platforms/qminimal.dll",
            "_internal/PySide6/plugins/generic",
        ],
    ),
    (
        "Unused Qt image-format plugins (PNG is built into QtGui)",
        [
            "_internal/PySide6/plugins/imageformats/qgif.dll",
            "_internal/PySide6/plugins/imageformats/qicns.dll",
            "_internal/PySide6/plugins/imageformats/qjpeg.dll",
            "_internal/PySide6/plugins/imageformats/qtga.dll",
            "_internal/PySide6/plugins/imageformats/qtiff.dll",
            "_internal/PySide6/plugins/imageformats/qwbmp.dll",
            "_internal/PySide6/plugins/imageformats/qwebp.dll",
        ],
    ),
]

REQUIRED = [
    "Vizier.exe",
    "VizierCLI.exe",
    "VizierMCP.exe",
    "_internal/python313.dll",
    "_internal/PySide6/Qt6Core.dll",
    "_internal/PySide6/Qt6Gui.dll",
    "_internal/PySide6/Qt6Widgets.dll",
    "_internal/PySide6/plugins/platforms/qwindows.dll",
    "_internal/PySide6/plugins/platforms/qoffscreen.dll",
    "_internal/PySide6/plugins/imageformats/qico.dll",
    "_internal/PySide6/plugins/styles/qmodernwindowsstyle.dll",
    "_internal/assets/vizier.ico",
    "_internal/assets/fonts/Rakkas-Regular.ttf",
]


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            with contextlib.suppress(OSError):
                total += child.stat().st_size
    return total


def _resolve(bundle: Path, pattern: str) -> list[Path]:
    """Expand one manifest entry, keeping only paths inside ``bundle``."""
    matches = sorted(bundle.glob(pattern))
    safe: list[Path] = []
    root = bundle.resolve()
    for match in matches:
        try:
            resolved = match.resolve()
        except OSError:
            continue
        if resolved == root or root not in resolved.parents:
            continue
        safe.append(match)
    return safe


def _remove_empty_dirs(bundle: Path) -> None:
    """Tidy empty plugin folders left behind by file-level removals."""
    for directory in sorted(bundle.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not directory.is_dir():
            continue
        try:
            next(directory.iterdir())
        except StopIteration:
            with contextlib.suppress(OSError):
                directory.rmdir()
        except OSError:
            pass


def prune(bundle: Path, *, dry_run: bool) -> int:
    if not bundle.is_dir():
        print(f"error: bundle not found: {bundle}", file=sys.stderr)
        return 2
    if not (bundle / "Vizier.exe").is_file():
        print(f"error: {bundle} does not look like a Vizier bundle", file=sys.stderr)
        return 2

    before = _size(bundle)
    print(f"Bundle: {bundle}")
    print(f"Before: {before / (1024 * 1024):.1f} MB")

    removed: set[Path] = set()
    saved = 0
    for label, patterns in PRUNE_GROUPS:
        group_size = 0
        group_paths: list[Path] = []
        for pattern in patterns:
            for path in _resolve(bundle, pattern):
                if path in removed:
                    continue
                # A parent directory may already cover a nested match.
                if any(parent in removed for parent in path.parents):
                    continue
                group_paths.append(path)
                group_size += _size(path)
        if not group_paths:
            continue
        print(f"  - {label}: {group_size / (1024 * 1024):.2f} MB ({len(group_paths)} paths)")
        saved += group_size
        if dry_run:
            for path in group_paths:
                print(f"      {path.relative_to(bundle)}")
            continue
        for path in group_paths:
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                removed.add(path)
            except OSError as exc:
                print(f"error: could not remove {path}: {exc}", file=sys.stderr)
                return 1

    if not dry_run:
        _remove_empty_dirs(bundle)

    after = _size(bundle)
    print(f"After:  {after / (1024 * 1024):.1f} MB")
    print(f"Saved:  {saved / (1024 * 1024):.1f} MB")

    if dry_run:
        return 0

    missing = [name for name in REQUIRED if not (bundle / name).exists()]
    if missing:
        print("error: prune removed required files:", file=sys.stderr)
        for name in missing:
            print(f"  {name}", file=sys.stderr)
        return 1
    print("Required runtime files: OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--bundle",
        type=Path,
        default=DEFAULT_BUNDLE,
        help="Path to the onedir bundle (default: dist/Vizier)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be removed without deleting anything",
    )
    args = parser.parse_args()
    return prune(args.bundle.resolve(), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
