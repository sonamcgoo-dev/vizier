"""
Vizier command-line interface.

Usage::

    vizier                      # launch the desktop GUI
    vizier chat --model x.gguf  # interactive terminal chat
    vizier mcp-server --stdio   # expose tools over MCP
    vizier models --recommend   # hardware-aware model suggestions
    vizier info                 # hardware / configuration report
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import sys
from pathlib import Path

from vizier.__version__ import __codename__, __version__
from vizier.config import Config
from vizier.logging_setup import (
    get_log_file,
    install_exception_hook,
    log_startup_banner,
    setup_logging,
)
from vizier.utils import Colors, cprint, detect_hardware, get_hardware_tier

log = logging.getLogger("vizier.cli")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_bytes(num: float) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def _banner() -> None:
    cprint("  VIZIER  ", Colors.RED_BOLD, end="")
    cprint("- Royal Advisor", Colors.WHITE)
    cprint(f"  v{__version__} · 100% local", Colors.DIM)


def _load_config(args) -> Config:
    config = Config.load()
    model = getattr(args, "model", None) or getattr(args, "global_model", None)
    if model:
        config.model_path = str(Path(model).expanduser())
    return config


def _resolve_model(config: Config, args) -> str | None:
    if config.model_path and Path(config.model_path).exists():
        return config.model_path
    from vizier.core.llm.model_manager import ModelManager

    local = ModelManager().get_local_models()
    if len(local) == 1:
        cprint(f"Using the only local model: {local[0].local_path}", Colors.DIM)
        config.model_path = local[0].local_path or ""
        return config.model_path
    return None


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def cmd_gui(args) -> int:
    try:
        from vizier.ui.main_window import main as gui_main
    except ImportError as exc:  # pragma: no cover
        cprint(f"Could not start the GUI: {exc}", Colors.RED)
        cprint("Install PySide6 with: pip install PySide6", Colors.DIM)
        return 1

    model = None
    selected = getattr(args, "model", None) or getattr(args, "global_model", None)
    if selected:
        model = str(Path(selected).expanduser())
    return gui_main(model)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

def cmd_chat(args) -> int:
    config = _load_config(args)
    model = _resolve_model(config, args)
    if not model:
        cprint("No model selected.", Colors.RED)
        cprint(
            "Pass --model path/to/model.gguf, or download one with:\n"
            "  vizier models --recommend",
            Colors.DIM,
        )
        return 1

    from vizier.tools import VizierServices

    services = VizierServices(config)
    provider = services.load_llm(model)

    _banner()
    cprint(f"Model: {model}", Colors.WHITE)
    cprint("Loading model into memory...", Colors.DIM)
    try:
        asyncio.run(provider.load())
    except Exception as exc:
        cprint(f"Failed to load model: {exc}", Colors.RED)
        return 1

    state = {"streaming": False}

    def on_chunk(text: str) -> None:
        if not state["streaming"]:
            print()
            cprint("Vizier: ", Colors.RED_BOLD, end="")
            state["streaming"] = True
        print(text, end="", flush=True)

    def on_tool_start(tool_call) -> None:
        if state["streaming"]:
            print()
            state["streaming"] = False
        args_text = json.dumps(tool_call.arguments, ensure_ascii=False)
        if len(args_text) > 200:
            args_text = args_text[:200] + "..."
        cprint(f"  > {tool_call.name}({args_text})", Colors.DIM)

    def on_tool_result(tool_call, result: str, success: bool) -> None:
        text = result.replace("\n", " ")
        if len(text) > 200:
            text = text[:200] + "..."
        colour = Colors.GREEN if success else Colors.RED
        cprint(f"  {'OK' if success else 'X'} {text}", colour)

    def on_state(new_state) -> None:
        value = getattr(new_state, "value", str(new_state))
        if value in ("error", "idle"):
            cprint(f"  [{value}]", Colors.DIM)

    agent = services.create_agent(
        yolo=args.yolo,
        on_llm_chunk=on_chunk,
        on_tool_start=on_tool_start,
        on_tool_result=on_tool_result,
        on_state_change=on_state,
    )

    cprint("Type /help for commands. Ctrl+C or /exit to quit.", Colors.DIM)
    try:
        while True:
            try:
                user = input("\nYou: ").strip()
            except EOFError:
                break
            if not user:
                continue
            if user.startswith("/"):
                if _handle_slash(user, agent, services, config):
                    break
                continue

            state["streaming"] = False
            try:
                asyncio.run(agent.run(user))
            except KeyboardInterrupt:
                cprint("\n[interrupted]", Colors.DIM)
                continue
            except Exception as exc:
                cprint(f"\n[error: {exc}]", Colors.RED)
            if state["streaming"]:
                print()
    except KeyboardInterrupt:
        pass

    cprint("\nGoodbye.", Colors.DIM)
    services.shutdown()
    return 0


def _handle_slash(
    command: str,
    agent,
    services,
    config: Config,
) -> bool:
    """Handle a /command. Returns True when the REPL should exit."""
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/exit", "/quit", "/q"):
        return True
    if cmd in ("/help", "/?"):
        cprint(
            "/help            show this help\n"
            "/exit            quit\n"
            "/clear           clear conversation history\n"
            "/yolo            toggle YOLO mode (dangerous tools)\n"
            "/tools           list registered tools\n"
            "/history         show conversation length\n"
            "/model PATH      switch GGUF model (reloads)\n"
            "/config          show current configuration",
            Colors.WHITE,
        )
        return False
    if cmd == "/clear":
        agent.clear_history()
        cprint("History cleared.", Colors.DIM)
        return False
    if cmd == "/yolo":
        enabled = not agent.config.yolo_enabled
        agent.set_yolo(enabled)
        config.yolo_enabled = enabled
        with contextlib.suppress(Exception):
            config.save()
        cprint(f"YOLO mode {'ON' if enabled else 'OFF'}", Colors.RED if enabled else Colors.DIM)
        return False
    if cmd == "/tools":
        for category, tools in sorted(services.registry.by_category().items()):
            cprint(f"{category}:", Colors.RED_BOLD)
            for tool in tools:
                flag = " (dangerous)" if tool.dangerous else ""
                cprint(f"  - {tool.name}{flag}", Colors.WHITE)
        return False
    if cmd == "/history":
        cprint(f"{len(agent.history)} messages in history.", Colors.DIM)
        return False
    if cmd == "/config":
        cprint(json.dumps(config.to_dict(), indent=2), Colors.WHITE)
        return False
    if cmd == "/model":
        if not arg:
            cprint("Usage: /model path/to/model.gguf", Colors.RED)
            return False
        path = str(Path(arg).expanduser())
        if not Path(path).exists():
            cprint(f"File not found: {path}", Colors.RED)
            return False
        cprint("Loading model...", Colors.DIM)
        try:
            provider = services.load_llm(path)
            asyncio.run(provider.load())
            agent.llm = provider
            config.model_path = path
            config.save()
            cprint("Model switched.", Colors.GREEN)
        except Exception as exc:
            cprint(f"Failed to load model: {exc}", Colors.RED)
        return False
    cprint(f"Unknown command: {cmd} (try /help)", Colors.RED)
    return False


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

def cmd_mcp_server(args) -> int:
    try:
        from vizier.servers.mcp_server import (
            main as server_main,
        )
    except ImportError as exc:  # pragma: no cover
        cprint(f"Could not start the MCP server: {exc}", Colors.RED)
        cprint("Install the MCP package with: pip install mcp", Colors.DIM)
        return 1

    argv: list[str] = []
    if args.stdio:
        argv.append("--stdio")
    elif args.sse:
        argv.append("--sse")
    elif args.streamable_http:
        argv.append("--streamable-http")
    if args.host:
        argv.extend(["--host", args.host])
    if args.port:
        argv.extend(["--port", str(args.port)])
    return server_main(argv)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def cmd_models(args) -> int:
    from vizier.core.llm.model_manager import ModelManager

    manager = ModelManager()
    tier = get_hardware_tier()

    if args.search:
        cprint(f"Searching Hugging Face for \"{args.search}\"...", Colors.DIM)
        results = manager.search_hf(args.search, limit=args.limit)
        if not results:
            cprint("No GGUF repositories found.", Colors.DIM)
            return 1
        for model in results:
            cprint(f"{model.name}", Colors.RED_BOLD)
            cprint(f"  file: {model.filename}", Colors.WHITE)
            cprint(f"  url:  {model.download_url}", Colors.DIM)
        return 0

    if args.download:
        repo, _, filename = args.download.partition(" ")
        if not filename:
            cprint("Usage: vizier models --download REPO_ID FILENAME", Colors.RED)
            return 1
        cprint(f"Downloading {filename} from {repo}...", Colors.WHITE)
        try:
            path = manager.download_model(
                repo,
                filename,
                on_progress=lambda done, total, name: _progress(done, total),
            )
            cprint(f"\nSaved to {path}", Colors.GREEN)
        except Exception as exc:
            cprint(f"\nDownload failed: {exc}", Colors.RED)
            return 1
        return 0

    if args.local:
        models = manager.refresh_local()
        if not models:
            cprint("No local .gguf models found.", Colors.DIM)
        for model in models:
            cprint(
                f"{model.display_name}  ({_fmt_bytes(model.vram_gb * 1024 ** 3)})",
                Colors.WHITE,
            )
            cprint(f"  {model.local_path}", Colors.DIM)
        return 0

    # default: recommendations
    cprint(f"Detected hardware tier: {tier}", Colors.RED_BOLD)
    hw = detect_hardware()
    gpu = ", ".join(g["name"] for g in hw["gpus"]) or "CPU only"
    cprint(f"CPU: {hw['cpu_model']}  |  RAM: {hw['ram_gb']} GB  |  GPU: {gpu}", Colors.DIM)
    for model in manager.recommend_models(tier):
        cprint(f"\n{model.display_name}", Colors.RED_BOLD)
        cprint(
            f"  {model.quant} · ~{model.vram_gb} GB VRAM · "
            f"{model.ram_minimum_gb} GB RAM minimum", Colors.WHITE,
        )
        cprint(f"  {model.description}", Colors.DIM)
        cprint(f"  download: vizier models --download \"{model.name} {model.filename}\"", Colors.DIM)
    return 0


def _progress(done: int, total: int) -> None:
    if total <= 0:
        print(f"\r  {_fmt_bytes(done)}", end="", flush=True)
        return
    pct = done / total * 100
    print(
        f"\r  {pct:5.1f}%  {_fmt_bytes(done)} / {_fmt_bytes(total)}",
        end="",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Info / version
# ---------------------------------------------------------------------------

def cmd_info(args) -> int:
    hw = detect_hardware()
    cprint(f"Vizier {__version__} - {__codename__}", Colors.RED_BOLD)
    cprint("Vizier system report", Colors.WHITE)
    cprint(json.dumps(hw, indent=2), Colors.WHITE)
    cprint(f"Hardware tier: {get_hardware_tier()}", Colors.RED_BOLD)
    config = Config.load()
    cprint(f"Model path: {config.model_path or '(not set)'}", Colors.WHITE)
    from vizier.utils import get_data_dir

    cprint(f"Data directory: {get_data_dir()}", Colors.DIM)
    cprint(f"Log file: {get_log_file()}", Colors.DIM)
    return 0


def cmd_doctor(args) -> int:
    from vizier.diagnostics import FAIL, OK, WARN, run_checks

    results = run_checks()
    cprint(f"Vizier {__version__} self-check", Colors.RED_BOLD)
    for result in results:
        if result.status == OK:
            colour = Colors.GREEN
        elif result.status == WARN:
            colour = Colors.ORANGE
        elif result.status == FAIL:
            colour = Colors.RED_BOLD
        else:
            colour = Colors.GREY
        cprint(f"  [{result.symbol:>2}] {result.name}", colour, end="")
        if result.detail:
            cprint(f" - {result.detail}", Colors.DIM)
        else:
            print()

    failures = sum(r.status == FAIL for r in results)
    warnings = sum(r.status == WARN for r in results)
    print()
    if failures:
        cprint(
            f"{failures} problem(s) found, {warnings} warning(s). "
            f"See {get_log_file()} for details.",
            Colors.RED,
        )
        return 1
    if warnings:
        cprint(f"No blocking problems. {warnings} warning(s).", Colors.ORANGE)
    else:
        cprint("Everything looks good.", Colors.GREEN)
    return 0


def cmd_version(args) -> int:
    print(__version__)
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vizier",
        description="Vizier - a 100% local AI agent and royal advisor.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Vizier {__version__} ({__codename__})",
    )
    parser.add_argument(
        "--model",
        dest="global_model",
        help="Path to a .gguf model (shorthand for the GUI).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging."
    )
    sub = parser.add_subparsers(dest="command")

    gui = sub.add_parser("gui", help="Launch the desktop GUI (default).")
    gui.add_argument("--model", help="Path to a .gguf model.")
    gui.set_defaults(func=cmd_gui)

    chat = sub.add_parser("chat", help="Interactive terminal chat.")
    chat.add_argument("--model", help="Path to a .gguf model.")
    chat.add_argument("--yolo", action="store_true", help="Allow dangerous tools.")
    chat.set_defaults(func=cmd_chat)

    server = sub.add_parser("mcp-server", help="Run Vizier as an MCP server.")
    transport = server.add_mutually_exclusive_group()
    transport.add_argument("--stdio", action="store_true", help="stdio transport (default)")
    transport.add_argument("--sse", action="store_true", help="SSE transport")
    transport.add_argument(
        "--streamable-http", action="store_true", help="Streamable HTTP transport"
    )
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=9000)
    server.set_defaults(func=cmd_mcp_server)

    models = sub.add_parser("models", help="Browse, search, and download models.")
    models.add_argument("--recommend", action="store_true", help="Show recommendations (default)")
    models.add_argument("--local", action="store_true", help="List local models")
    models.add_argument("--search", metavar="QUERY", help="Search Hugging Face")
    models.add_argument("--limit", type=int, default=10)
    models.add_argument(
        "--download",
        metavar="REPO_ID FILENAME",
        help="Download a model, e.g. --download \"Qwen/Qwen3-8B-GGUF file.gguf\"",
    )
    models.set_defaults(func=cmd_models)

    info = sub.add_parser("info", help="Show hardware and configuration.")
    info.set_defaults(func=cmd_info)

    doctor = sub.add_parser(
        "doctor", help="Run a self-check of the installation and dependencies."
    )
    doctor.set_defaults(func=cmd_doctor)

    version = sub.add_parser("version", help="Print the version.")
    version.set_defaults(func=cmd_version)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(verbose=getattr(args, "verbose", False), log_name="vizier.cli")
    install_exception_hook()
    log_startup_banner("CLI")

    func = getattr(args, "func", None)
    if func is None:
        # No sub-command: launch the GUI, honouring a global --model.
        args.model = getattr(args, "global_model", None)
        return cmd_gui(args)
    return int(func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
