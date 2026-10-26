"""
Computer-use tool definitions — wraps ScreenCapture, MouseController,
and KeyboardController as VizierTool instances.
"""
from __future__ import annotations

import json

from vizier.core.computer.keyboard import KeyboardController
from vizier.core.computer.mouse import MouseController
from vizier.core.computer.screen import ScreenCapture
from vizier.core.tool import VizierTool
from vizier.core.types import ToolCategory


class ScreenshotTool(VizierTool):
    """Take a screenshot of the screen or a region."""
    name = "screenshot"
    description = "Capture a screenshot of the screen or a specific region (x,y,w,h). Returns the path to the saved PNG file."
    parameters = {
        "type": "object",
        "properties": {
            "region": {"type": "string", "description": "Region as 'x,y,width,height'. Omit for full screen."},
            "scale": {"type": "number", "description": "Downscale factor (0.5 = half size). Default: 0.5.", "default": 0.5},
        },
    }
    category = ToolCategory.COMPUTER.value
    dangerous = False

    def __init__(self, screen: ScreenCapture):
        super().__init__()
        self._screen = screen

    def execute(self, region: str | None = None, scale: float = 0.5) -> str:
        if not self._screen.available:
            return "[Error: pyscreeze not installed]"
        reg = None
        if region:
            parts = [int(x) for x in region.split(",")]
            if len(parts) == 4:
                reg = tuple(parts)
        path = self._screen.screenshot(region=reg, scale=scale)
        return f"Screenshot saved to: {path}"


class ScreenSizeTool(VizierTool):
    name = "screen_size"
    description = "Get the dimensions of the primary screen."
    parameters = {"type": "object", "properties": {}}
    category = ToolCategory.COMPUTER.value

    def __init__(self, screen: ScreenCapture):
        super().__init__()
        self._screen = screen

    def execute(self) -> str:
        w, h = self._screen.get_screen_size()
        return json.dumps({"width": w, "height": h})


class MouseClickTool(VizierTool):
    name = "mouse_click"
    description = "Click the mouse at the given coordinates. Button: left, right, or middle."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X coordinate (optional)"},
            "y": {"type": "integer", "description": "Y coordinate (optional)"},
            "button": {"type": "string", "description": "left/right/middle. Default: left", "default": "left"},
            "clicks": {"type": "integer", "description": "Number of clicks. Default: 1", "default": 1},
        },
    }
    category = ToolCategory.COMPUTER.value
    dangerous = False

    def __init__(self, mouse: MouseController):
        super().__init__()
        self._mouse = mouse

    def execute(self, x: int | None = None, y: int | None = None,
                button: str = "left", clicks: int = 1) -> str:
        if not self._mouse.available:
            return "[Error: pyautogui not installed]"
        self._mouse.click(x=x, y=y, button=button, clicks=clicks)
        if x is not None and y is not None:
            return f"Clicked {button} at ({x}, {y}) x{clicks}"
        return f"Clicked {button} x{clicks}"


class MouseMoveTool(VizierTool):
    name = "mouse_move"
    description = "Move the mouse cursor to the given (x, y) coordinates."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X coordinate", "minimum": 0},
            "y": {"type": "integer", "description": "Y coordinate", "minimum": 0},
        },
        "required": ["x", "y"],
    }
    category = ToolCategory.COMPUTER.value

    def __init__(self, mouse: MouseController):
        super().__init__()
        self._mouse = mouse

    def execute(self, x: int, y: int) -> str:
        if not self._mouse.available:
            return "[Error: pyautogui not installed]"
        self._mouse.move_to(x, y)
        return f"Moved to ({x}, {y})"


class MouseScrollTool(VizierTool):
    name = "mouse_scroll"
    description = "Scroll the mouse wheel. Positive=up, negative=down."
    parameters = {
        "type": "object",
        "properties": {
            "amount": {"type": "integer", "description": "Scroll amount"},
            "x": {"type": "integer", "description": "X coordinate (optional)"},
            "y": {"type": "integer", "description": "Y coordinate (optional)"},
        },
        "required": ["amount"],
    }
    category = ToolCategory.COMPUTER.value

    def __init__(self, mouse: MouseController):
        super().__init__()
        self._mouse = mouse

    def execute(self, amount: int, x: int | None = None, y: int | None = None) -> str:
        if not self._mouse.available:
            return "[Error: pyautogui not installed]"
        self._mouse.scroll(amount, x, y)
        return f"Scrolled by {amount}"


class KeyboardTypeTool(VizierTool):
    name = "keyboard_type"
    description = "Type text on the keyboard (sends keystrokes to the active window)."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "The text to type"}},
        "required": ["text"],
    }
    category = ToolCategory.COMPUTER.value

    def __init__(self, keyboard: KeyboardController):
        super().__init__()
        self._keyboard = keyboard

    def execute(self, text: str) -> str:
        if not self._keyboard.available:
            return "[Error: pyautogui not installed]"
        self._keyboard.type_text(text)
        return f"Typed: {text[:30]}..."


class KeyboardHotkeyTool(VizierTool):
    name = "keyboard_hotkey"
    description = "Press a keyboard hotkey combination. Keys comma-separated (e.g. 'ctrl,c')."
    parameters = {
        "type": "object",
        "properties": {"keys": {"type": "string", "description": "Comma-separated key names"}},
        "required": ["keys"],
    }
    category = ToolCategory.COMPUTER.value

    def __init__(self, keyboard: KeyboardController):
        super().__init__()
        self._keyboard = keyboard

    def execute(self, keys: str) -> str:
        if not self._keyboard.available:
            return "[Error: pyautogui not installed]"
        key_list = [k.strip() for k in keys.split(",")]
        self._keyboard.hotkey(*key_list)
        return f"Pressed: {keys}"


class OCRScreenTool(VizierTool):
    name = "ocr_screen"
    description = "Extract text from a region of the screen using OCR. Region: 'x,y,width,height'."
    parameters = {
        "type": "object",
        "properties": {"region": {"type": "string", "description": "Region as 'x,y,width,height'. Omit for full screen."}},
    }
    category = ToolCategory.COMPUTER.value

    def __init__(self, screen: ScreenCapture):
        super().__init__()
        self._screen = screen

    def execute(self, region: str | None = None) -> str:
        reg = None
        if region:
            parts = [int(x) for x in region.split(",")]
            if len(parts) == 4:
                reg = tuple(parts)
        try:
            return self._screen.ocr_region(region=reg)
        except Exception as e:
            return f"[OCR failed: {e}]"


class ListWindowsTool(VizierTool):
    name = "list_windows"
    description = "List all currently open windows with titles and positions."
    parameters = {"type": "object", "properties": {}}
    category = ToolCategory.COMPUTER.value

    def __init__(self, screen: ScreenCapture):
        super().__init__()
        self._screen = screen

    def execute(self) -> str:
        windows = self._screen.list_windows()
        return json.dumps(windows, indent=2)


def get_computer_tools(
    screen: ScreenCapture | None = None,
    mouse: MouseController | None = None,
    keyboard: KeyboardController | None = None,
) -> list[VizierTool]:
    """Factory: create all computer-use tools with shared service instances."""
    screen = screen or ScreenCapture()
    mouse = mouse or MouseController(screen)
    keyboard = keyboard or KeyboardController()
    return [
        ScreenshotTool(screen),
        ScreenSizeTool(screen),
        MouseClickTool(mouse),
        MouseMoveTool(mouse),
        MouseScrollTool(mouse),
        KeyboardTypeTool(keyboard),
        KeyboardHotkeyTool(keyboard),
        OCRScreenTool(screen),
        ListWindowsTool(screen),
    ]
