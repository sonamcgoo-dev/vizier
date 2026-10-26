"""
Computer-use: screen capture and OCR.

Provides screenshots (optionally scaled or region-cropped) and basic OCR
via pytesseract.  The screenshot is returned as a PNG file path so it can
be fed to a vision-capable LLM or attached to tool results.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import time
from functools import cache
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from vizier.utils import get_cache_dir

log = logging.getLogger("vizier.computer.screen")

# Optional heavy dependencies are discovered without importing them: pyautogui
# alone costs ~300 ms, and pytesseract drags in numpy/pandas.  They are only
# imported when a computer-use tool is actually invoked.
_pyscreeze_available = find_spec("pyscreeze") is not None
_pil_available = find_spec("PIL") is not None
_tesseract_available = find_spec("pytesseract") is not None


@cache
def _pyscreeze():
    import pyscreeze

    return pyscreeze


@cache
def _pil_image():
    from PIL import Image

    return Image


@cache
def _pytesseract():
    import pytesseract

    return pytesseract


def _resample_filter():
    if not _pil_available:
        return None
    image = _pil_image()
    resampling = getattr(image, "Resampling", None)
    if resampling is not None:
        return resampling.LANCZOS
    return image.LANCZOS  # type: ignore[attr-defined]


class ScreenCapture:
    """Screen capture and image utilities."""

    def __init__(self):
        self.tmp_dir = get_cache_dir() / "screenshots"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    @property
    def available(self) -> bool:
        return _pyscreeze_available and _pil_available

    @property
    def ocr_available(self) -> bool:
        return _tesseract_available

    def screenshot(
        self,
        region: tuple[int, int, int, int] | None = None,
        scale: float = 1.0,
        save_as: str | None = None,
    ) -> str:
        """Take a screenshot and return the path to the saved PNG file.

        Args:
            region: ``(x, y, width, height)`` or ``None`` for the full screen.
            scale: Downscale factor (e.g. ``0.5`` = half size) to save tokens.
            save_as: Override filename; otherwise auto-generated.
        """
        if not _pyscreeze_available:
            raise RuntimeError("pyscreeze is not installed")

        img = _pyscreeze().screenshot(region=region)

        if scale != 1.0 and _pil_available:
            width, height = img.size
            img = img.resize(
                (max(1, int(width * scale)), max(1, int(height * scale))),
                _resample_filter(),
            )

        path = Path(save_as) if save_as else (
            self.tmp_dir / f"shot_{int(time.time() * 1000)}.png"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(path), "PNG")
        log.debug("Screenshot saved: %s", path)
        return str(path)

    def screenshot_base64(
        self,
        region: tuple[int, int, int, int] | None = None,
        scale: float = 1.0,
    ) -> str:
        """Take a screenshot and return it as a base64-encoded PNG string."""
        if not _pyscreeze_available:
            raise RuntimeError("pyscreeze is not installed")

        img = _pyscreeze().screenshot(region=region)
        if scale != 1.0 and _pil_available:
            width, height = img.size
            img = img.resize(
                (max(1, int(width * scale)), max(1, int(height * scale))),
                _resample_filter(),
            )

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def get_screen_size(self) -> tuple[int, int]:
        """Return ``(width, height)`` of the primary screen."""
        try:
            import pyautogui

            size = pyautogui.size()
            return int(size.width), int(size.height)
        except Exception:
            pass
        # Fallback via ctypes on Windows
        try:
            import ctypes

            user32 = ctypes.windll.user32
            return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
        except Exception:
            return (1920, 1080)

    def ocr_region(
        self,
        region: tuple[int, int, int, int] | None = None,
        image_path: str | None = None,
    ) -> str:
        """Run OCR on a region of the screen or on an image file."""
        if not _tesseract_available:
            raise RuntimeError(
                "pytesseract is not installed (also needs tesseract-ocr)"
            )

        if image_path:
            if not _pil_available:
                raise RuntimeError("Pillow is required to open image files")
            img = _pil_image().open(image_path)
        elif region and _pyscreeze_available:
            img = _pyscreeze().screenshot(region=region)
        else:
            raise ValueError("Must provide either region or image_path")

        return _pytesseract().image_to_string(img).strip()

    def list_windows(self) -> list[dict[str, Any]]:
        """List currently open windows (best effort, Windows only)."""
        windows: list[dict[str, Any]] = []
        try:
            if os.name == "nt":
                import pygetwindow as gw  # type: ignore[import-not-found]

                for win in gw.getAllWindows():
                    if not win.title:
                        continue
                    windows.append({
                        "title": win.title,
                        "left": win.left,
                        "top": win.top,
                        "width": win.width,
                        "height": win.height,
                    })
        except ImportError:  # pragma: no cover
            pass
        except Exception as exc:  # pragma: no cover
            log.debug("Could not enumerate windows: %s", exc)
        return windows
