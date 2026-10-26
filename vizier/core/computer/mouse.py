"""
Computer-use: mouse control via pyautogui.

Provides click, double-click, right-click, drag, scroll, and movement
with safety guards.  All actions are logged.
"""
from __future__ import annotations

import logging
from functools import cache
from importlib.util import find_spec

from vizier.core.computer.screen import ScreenCapture

log = logging.getLogger("vizier.computer.mouse")

_pa_available = find_spec("pyautogui") is not None


@cache
def _pyautogui():
    import pyautogui

    return pyautogui


class MouseController:
    """Low-level mouse control."""

    def __init__(self, screen: ScreenCapture):
        self.screen = screen
        self._safe_mode = True  # double-check coordinates

    @property
    def available(self) -> bool:
        return _pa_available

    def position(self) -> tuple[int, int]:
        """Return current mouse (x, y)."""
        if not _pa_available:
            raise RuntimeError("pyautogui not installed")
        return _pyautogui().position()

    def move_to(self, x: int, y: int, duration: float = 0.2) -> None:
        """Move the mouse cursor to (x, y)."""
        if not _pa_available:
            raise RuntimeError("pyautogui not installed")
        sw, sh = self.screen.get_screen_size()
        if self._safe_mode:
            x = max(0, min(sw - 1, int(x)))
            y = max(0, min(sh - 1, int(y)))
        log.debug(f"Mouse move to ({x}, {y})")
        _pyautogui().moveTo(x, y, duration=duration)

    def click(self, x: int | None = None, y: int | None = None, button: str = "left",
              clicks: int = 1, interval: float = 0.0) -> None:
        """Click at (x, y) or at current position."""
        if not _pa_available:
            raise RuntimeError("pyautogui not installed")
        if x is not None and y is not None:
            self.move_to(x, y)
        btn = "left" if button.lower() in ("left", "l", "primary") else \
              "right" if button.lower() in ("right", "r", "secondary") else "middle"
        log.debug(f"Mouse click {btn} x{clicks}")
        _pyautogui().click(button=btn, clicks=clicks, interval=interval)

    def double_click(self, x: int | None = None, y: int | None = None, button: str = "left") -> None:
        if x is not None and y is not None:
            self.move_to(x, y)
        _pyautogui().doubleClick(button=button)

    def right_click(self, x: int | None = None, y: int | None = None) -> None:
        if x is not None and y is not None:
            self.move_to(x, y)
        _pyautogui().rightClick()

    def drag(self, x: int, y: int, duration: float = 0.5, button: str = "left") -> None:
        if not _pa_available:
            raise RuntimeError("pyautogui not installed")
        self.move_to(x, y, duration=duration)
        _pyautogui().dragTo(x, y, duration=duration, button=button)

    def scroll(self, amount: int, x: int | None = None, y: int | None = None) -> None:
        if not _pa_available:
            raise RuntimeError("pyautogui not installed")
        if x is not None and y is not None:
            self.move_to(x, y)
        # Positive = up, negative = down
        _pyautogui().scroll(amount)

    def scroll_horizontal(self, amount: int) -> None:
        if not _pa_available:
            raise RuntimeError("pyautogui not installed")
        _pyautogui().hscroll(amount)
