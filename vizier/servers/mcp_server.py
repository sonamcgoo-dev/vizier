"""
Vizier as an MCP (Model Context Protocol) **server**.

When launched with ``vizier mcp-server --stdio`` (or ``--sse`` /
``--streamable-http``), Vizier exposes its built-in tools — filesystem,
computer use, shell, and more — to any MCP client (Claude Desktop,
Cursor, VS Code, Android Studio, etc.).

This makes Vizier a **headless CLI plugin**: other apps connect to
Vizier's MCP server and get access to its full toolkit.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from vizier.__version__ import __version__
from vizier.config import Config
from vizier.core.computer.keyboard import KeyboardController
from vizier.core.computer.mouse import MouseController
from vizier.core.computer.screen import ScreenCapture
from vizier.core.fs.file_ops import FilesystemManager
from vizier.core.shell import ShellManager

log = logging.getLogger("vizier.mcp_server")

try:  # pragma: no cover - optional dependency
    from mcp.server import MCPServer

    _MCP_AVAILABLE = True
except ImportError:  # pragma: no cover
    MCPServer = None  # type: ignore[assignment]
    _MCP_AVAILABLE = False


_mcp: MCPServer | None = None
_fs: FilesystemManager | None = None
_shell: ShellManager | None = None
_screen: ScreenCapture | None = None
_mouse: MouseController | None = None
_keyboard: KeyboardController | None = None


def _require_services() -> None:
    if _fs is None or _shell is None or _screen is None:
        raise RuntimeError("MCP server services are not initialised")


def init_services(config: Config | None = None) -> None:
    """Initialise shared service objects (idempotent)."""
    global _fs, _shell, _screen, _mouse, _keyboard, _mcp
    if not _MCP_AVAILABLE:
        raise RuntimeError(
            "The 'mcp' package is not installed. Install it with: pip install mcp"
        )
    if _fs is not None:
        return
    config = config or Config.load()
    _fs = FilesystemManager()
    _shell = ShellManager(default_timeout=60)
    _screen = ScreenCapture()
    _mouse = MouseController(_screen)
    _keyboard = KeyboardController()
    _mcp = MCPServer("vizier", version=__version__)
    _register_tools(config)


def _register_tools(config: Config) -> None:
    """Register all Vizier tools on the MCP server."""
    assert _mcp is not None

    @_mcp.tool()
    def file_read(path: str, max_chars: int = 100000) -> str:
        """Read a text file from the filesystem."""
        _require_services()
        return _fs.read_file(path, max_chars)  # type: ignore[union-attr]

    @_mcp.tool()
    def file_write(path: str, content: str, append: bool = False) -> str:
        """Write content to a file. Append if append=True."""
        _require_services()
        return _fs.write_file(path, content, append)  # type: ignore[union-attr]

    @_mcp.tool()
    def file_list(
        path: str, include_hidden: bool = False, recursive: bool = False
    ) -> str:
        """List directory contents as JSON."""
        _require_services()
        entries = _fs.list_dir(  # type: ignore[union-attr]
            path, include_hidden=include_hidden, recursive=recursive
        )
        return json.dumps(entries, indent=2)

    @_mcp.tool()
    def file_info(path: str) -> str:
        """Get detailed metadata for a file or directory."""
        _require_services()
        return json.dumps(_fs.file_info(path), indent=2)  # type: ignore[union-attr]

    @_mcp.tool()
    def file_move(src: str, dst: str) -> str:
        """Move or rename a file."""
        _require_services()
        return _fs.move(src, dst)  # type: ignore[union-attr]

    @_mcp.tool()
    def file_delete(path: str, recursive: bool = False) -> str:
        """Delete a file or directory."""
        _require_services()
        return _fs.delete(path, recursive=recursive)  # type: ignore[union-attr]

    @_mcp.tool()
    def file_search(
        query: str, path: str | None = None, max_results: int = 50
    ) -> str:
        """Search for files by name pattern."""
        _require_services()
        results = _fs.search(  # type: ignore[union-attr]
            query, path=path, max_results=max_results
        )
        return json.dumps(results, indent=2)

    @_mcp.tool()
    def shell_run(command: str, timeout: int = 30) -> str:
        """Execute a shell command. DANGEROUS: arbitrary code execution."""
        _require_services()
        return str(_shell.execute(  # type: ignore[union-attr]
            command, timeout=timeout
        ))

    @_mcp.tool()
    def screenshot(region: str | None = None, scale: float = 0.5) -> str:
        """Take a screenshot of the screen (or region 'x,y,w,h')."""
        _require_services()
        reg = None
        if region:
            parts = [int(x) for x in region.split(",")]
            if len(parts) == 4:
                reg = tuple(parts)
        return _screen.screenshot(region=reg, scale=scale)  # type: ignore[union-attr]

    @_mcp.tool()
    def mouse_click(
        x: int | None = None,
        y: int | None = None,
        button: str = "left",
    ) -> str:
        """Click the mouse at given coordinates."""
        _require_services()
        if x is not None and y is not None:
            _mouse.click(x=x, y=y, button=button)  # type: ignore[union-attr]
            return f"Clicked {button} at ({x}, {y})"
        _mouse.click(button=button)  # type: ignore[union-attr]
        return f"Clicked {button}"

    @_mcp.tool()
    def mouse_move(x: int, y: int) -> str:
        """Move the mouse cursor to (x, y)."""
        _require_services()
        _mouse.move_to(x, y)  # type: ignore[union-attr]
        return f"Moved to ({x}, {y})"

    @_mcp.tool()
    def keyboard_type(text: str) -> str:
        """Type text on the keyboard."""
        _require_services()
        _keyboard.type_text(text)  # type: ignore[union-attr]
        return f"Typed {len(text)} characters"

    @_mcp.tool()
    def keyboard_hotkey(keys: str) -> str:
        """Press a hotkey combination (e.g. 'ctrl,c')."""
        _require_services()
        key_list = [k.strip() for k in keys.split(",")]
        _keyboard.hotkey(*key_list)  # type: ignore[union-attr]
        return f"Pressed hotkey: {keys}"

    @_mcp.tool()
    def screen_size() -> str:
        """Get the screen dimensions."""
        _require_services()
        w, h = _screen.get_screen_size()  # type: ignore[union-attr]
        return json.dumps({"width": w, "height": h})

    @_mcp.tool()
    def list_windows() -> str:
        """List open windows."""
        _require_services()
        return json.dumps(_screen.list_windows(), indent=2)  # type: ignore[union-attr]

    # -- resources --------------------------------------------------------

    @_mcp.resource("config://models-directory")
    def models_dir_resource() -> str:
        from vizier.utils import get_models_dir

        return str(get_models_dir())

    @_mcp.resource("config://user-home")
    def user_home_resource() -> str:
        return str(Path.home())

    @_mcp.resource("config://platform-info")
    def platform_info_resource() -> str:
        from vizier.utils import detect_hardware

        return json.dumps(detect_hardware(), indent=2, default=str)


def get_mcp_server() -> MCPServer:
    if _mcp is None:
        init_services(Config.load())
    assert _mcp is not None
    return _mcp


def run_stdio() -> None:
    """Run Vizier as an MCP server over stdio."""
    get_mcp_server().run(transport="stdio")


def run_sse(host: str = "127.0.0.1", port: int = 9000) -> None:
    """Run Vizier as an MCP server over SSE."""
    get_mcp_server().run(transport="sse", host=host, port=port)


def run_streamable_http(host: str = "127.0.0.1", port: int = 9000) -> None:
    """Run Vizier as an MCP server over streamable HTTP."""
    get_mcp_server().run(transport="streamable-http", host=host, port=port)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vizier-mcp-server",
        description="Expose Vizier's tools over the Model Context Protocol.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--stdio", action="store_true", help="Use stdio (default)")
    group.add_argument("--sse", action="store_true", help="Use Server-Sent Events")
    group.add_argument(
        "--streamable-http",
        action="store_true",
        help="Use streamable HTTP",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    if args.sse:
        run_sse(args.host, args.port)
    elif args.streamable_http:
        run_streamable_http(args.host, args.port)
    else:
        run_stdio()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
