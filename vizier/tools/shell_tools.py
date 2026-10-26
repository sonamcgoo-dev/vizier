"""
Shell tool definitions — wraps ShellManager as VizierTool instances.

Shell execution is **dangerous** and requires YOLO confirmation.
"""
from __future__ import annotations

from vizier.core.shell import ShellManager
from vizier.core.tool import VizierTool
from vizier.core.types import ToolCategory


class ShellRunTool(VizierTool):
    name = "shell"
    description = (
        "Execute a shell command on the user's computer. "
        "Captures stdout, stderr, and exit code. "
        "Use with CAUTION — this can modify/delete files."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30)", "default": 30},
            "cwd": {"type": "string", "description": "Working directory (optional)"},
        },
        "required": ["command"],
    }
    category = ToolCategory.SHELL.value
    dangerous = True

    def __init__(self, shell: ShellManager):
        super().__init__()
        self._shell = shell

    def execute(self, command: str, timeout: int = 30, cwd: str | None = None) -> str:
        result = self._shell.execute(command, timeout=timeout, cwd=cwd)
        return str(result)


class ShellListProcessesTool(VizierTool):
    name = "list_processes"
    description = "List running processes on the system."
    parameters = {"type": "object", "properties": {}}
    category = ToolCategory.SHELL.value
    dangerous = False

    def __init__(self, shell: ShellManager):
        super().__init__()
        self._shell = shell

    def execute(self) -> str:
        try:
            cmd = "tasklist /v" if __import__("os").name == "nt" else "ps aux"
            result = self._shell.execute(cmd, timeout=10)
            return result.stdout if result.success else f"[Error: {result.stderr}]"
        except Exception as e:
            return f"[Error: {e}]"


def get_shell_tools(shell: ShellManager | None = None) -> list:
    """Factory: create all shell tools."""
    shell = shell or ShellManager()
    return [ShellRunTool(shell), ShellListProcessesTool(shell)]
