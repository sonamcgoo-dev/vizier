"""Tests for the command-line interface."""
from __future__ import annotations

import argparse

from vizier import cli
from vizier.core.tool import VizierTool
from vizier.core.types import Message, Role
from vizier.tools.registry import ToolRegistry


def test_fmt_bytes() -> None:
    assert cli._fmt_bytes(512) == "512.0 B"
    assert cli._fmt_bytes(2048) == "2.0 KB"
    assert cli._fmt_bytes(5 * 1024 ** 3) == "5.0 GB"


def test_parser_subcommands() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["chat", "--model", "m.gguf", "--yolo"])
    assert args.command == "chat"
    assert args.model == "m.gguf"
    assert args.yolo is True

    args = parser.parse_args(["models", "--search", "qwen", "--limit", "5"])
    assert args.command == "models"
    assert args.search == "qwen"
    assert args.limit == 5

    args = parser.parse_args(["mcp-server", "--streamable-http", "--port", "9100"])
    assert args.streamable_http is True
    assert args.port == 9100


def test_version_command(capsys) -> None:
    from vizier.__version__ import __version__

    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_global_model_is_kept_separate() -> None:
    args = cli.build_parser().parse_args(["--model", "global.gguf", "chat"])
    assert args.global_model == "global.gguf"
    assert getattr(args, "model", None) is None


class FakeAgent:
    def __init__(self) -> None:
        self.history = [Message(role=Role.USER, content="hi")]
        self.cleared = False
        self.yolo = False

        class Config:
            yolo_enabled = False

        self.config = Config()

    def clear_history(self) -> None:
        self.cleared = True
        self.history = []

    def set_yolo(self, enabled: bool) -> None:
        self.yolo = enabled
        self.config.yolo_enabled = enabled


class EchoTool(VizierTool):
    name = "echo"
    description = "Echo"

    def execute(self, text: str = "") -> str:
        return text


class FakeServices:
    def __init__(self) -> None:
        self.registry = ToolRegistry()
        self.registry.register(EchoTool())


class FakeConfig:
    yolo_enabled = False

    def save(self) -> None:
        pass


def test_slash_help_and_exit(capsys) -> None:
    agent = FakeAgent()
    services = FakeServices()
    config = FakeConfig()

    assert cli._handle_slash("/help", agent, services, config) is False
    assert "show this help" in capsys.readouterr().out

    assert cli._handle_slash("/exit", agent, services, config) is True


def test_slash_clear_and_yolo() -> None:
    agent = FakeAgent()
    services = FakeServices()
    config = FakeConfig()

    cli._handle_slash("/clear", agent, services, config)
    assert agent.cleared is True

    cli._handle_slash("/yolo", agent, services, config)
    assert agent.yolo is True
    assert config.yolo_enabled is True


def test_slash_tools_and_unknown(capsys) -> None:
    agent = FakeAgent()
    services = FakeServices()
    config = FakeConfig()

    cli._handle_slash("/tools", agent, services, config)
    output = capsys.readouterr().out
    assert "echo" in output

    cli._handle_slash("/nope", agent, services, config)
    assert "Unknown command" in capsys.readouterr().out


def test_mcp_server_command_forwards_arguments(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr("vizier.servers.mcp_server.main", fake_main)
    args = argparse.Namespace(
        stdio=False, sse=True, streamable_http=False, host="127.0.0.1", port=9100
    )
    assert cli.cmd_mcp_server(args) == 0
    assert captured["argv"] == ["--sse", "--host", "127.0.0.1", "--port", "9100"]
