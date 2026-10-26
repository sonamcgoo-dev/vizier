"""
Computer-use: keyboard input via pyautogui.

Provides typing, key presses, hotkeys, and clipboard read/write.
"""
from __future__ import annotations

import logging
from functools import cache
from importlib.util import find_spec

log = logging.getLogger("vizier.computer.keyboard")

_pa_available = find_spec("pyautogui") is not None
_clipboard_available = find_spec("pyperclip") is not None


@cache
def _pyautogui():
    import pyautogui

    return pyautogui


@cache
def _pyperclip():
    import pyperclip

    return pyperclip


class KeyboardController:
    """Low-level keyboard control."""

    KEY_ALIASES = {
        "enter": "enter", "return": "enter", "tab": "tab",
        "space": "space", "backspace": "backspace", "del": "delete",
        "delete": "delete", "esc": "esc", "escape": "esc",
        "up": "up", "down": "down", "left": "left", "right": "right",
        "home": "home", "end": "end", "pgup": "pageup", "pageup": "pageup",
        "pgdn": "pagedown", "pagedown": "pagedown",
        "ctrl": "ctrl", "control": "ctrl", "shift": "shift", "alt": "alt",
        "cmd": "command", "command": "command", "win": "win",
    }

    @property
    def available(self) -> bool:
        return _pa_available

    @classmethod
    def _normalise(cls, key: str) -> str:
        if not key:
            return key
        lowered = key.lower()
        if lowered in cls.KEY_ALIASES:
            return cls.KEY_ALIASES[lowered]
        if len(lowered) >= 2 and lowered[0] == "f" and lowered[1:].isdigit():
            return lowered
        return key if len(key) == 1 else lowered

    @classmethod
    def normalise_keys(cls, keys) -> tuple[str, ...]:
        return tuple(cls._normalise(k) for k in keys)

    def type_text(self, text: str, interval: float = 0.01) -> None:
        """Type text character by character."""
        if not _pa_available:
            raise RuntimeError("pyautogui not installed")
        log.debug("Typing: %s...", text[:40])
        _pyautogui().write(text, interval=interval)

    def press(self, key: str, presses: int = 1, interval: float = 0.0) -> None:
        """Press a single key."""
        if not _pa_available:
            raise RuntimeError("pyautogui not installed")
        log.debug("Pressing key: %s", key)
        _pyautogui().press(self._normalise(key), presses=presses, interval=interval)

    def hotkey(self, *keys: str) -> None:
        """Press a combination of keys (e.g. ``hotkey('ctrl', 'c')``)."""
        if not _pa_available:
            raise RuntimeError("pyautogui not installed")
        log.debug("Hotkey: %s", keys)
        _pyautogui().hotkey(*self.normalise_keys(keys))

    def write(self, text: str) -> None:
        """Alias for type_text with no interval (fast)."""
        self.type_text(text, interval=0.0)

    def get_clipboard(self) -> str:
        """Return current clipboard text."""
        if _clipboard_available:
            return _pyperclip().paste()
        return self._windows_clipboard(get=True)

    def set_clipboard(self, text: str) -> None:
        """Set clipboard text."""
        if _clipboard_available:
            _pyperclip().copy(text)
            return
        self._windows_clipboard(set_text=text)

    @staticmethod
    def _windows_clipboard(get: bool = False, set_text: str | None = None) -> str:
        """Fallback clipboard access on Windows via ctypes."""
        if get:
            try:
                import ctypes

                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                if not user32.OpenClipboard(None):
                    return ""
                try:
                    handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
                    if not handle:
                        return ""
                    ptr = kernel32.GlobalLock(handle)
                    try:
                        return ctypes.wstring_at(ptr)
                    finally:
                        kernel32.GlobalUnlock(handle)
                finally:
                    user32.CloseClipboard()
            except Exception:
                return ""
        if set_text is not None:
            try:
                import ctypes

                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                data = ctypes.create_unicode_buffer(set_text)
                if not user32.OpenClipboard(None):
                    return ""
                try:
                    user32.EmptyClipboard()
                    size = ctypes.sizeof(data)
                    handle = kernel32.GlobalAlloc(0x0042, size)
                    ptr = kernel32.GlobalLock(handle)
                    ctypes.memmove(ptr, data, size)
                    kernel32.GlobalUnlock(handle)
                    user32.SetClipboardData(13, handle)
                finally:
                    user32.CloseClipboard()
            except Exception:
                pass
        return ""
