"""
Filesystem tool definitions — wraps FilesystemManager as VizierTool instances.

Read, write, list, move, delete, search, and inspect files.
Destructive operations are flagged as ``dangerous`` for YOLO confirmation.
"""
from __future__ import annotations

import json

from vizier.core.fs.file_ops import FilesystemManager
from vizier.core.tool import VizierTool
from vizier.core.types import ToolCategory


class ReadFileTool(VizierTool):
    name = "read_file"
    description = "Read a text file from the filesystem."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file"},
            "max_chars": {"type": "integer", "description": "Maximum characters to read", "default": 100000},
        },
        "required": ["path"],
    }
    category = ToolCategory.FILESYSTEM.value
    dangerous = False

    def __init__(self, fs: FilesystemManager):
        super().__init__()
        self._fs = fs

    def execute(self, path: str, max_chars: int = 100000) -> str:
        try:
            content = self._fs.read_file(path, max_chars)
            return f"File: {path}\n\n{content}"
        except Exception as e:
            return f"[Error reading file: {e}]"


class WriteFileTool(VizierTool):
    name = "write_file"
    description = "Write (or overwrite) a text file. Set append=True to append."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file"},
            "content": {"type": "string", "description": "Content to write"},
            "append": {"type": "boolean", "description": "Append instead of overwrite", "default": False},
        },
        "required": ["path", "content"],
    }
    category = ToolCategory.FILESYSTEM.value
    dangerous = True

    def __init__(self, fs: FilesystemManager):
        super().__init__()
        self._fs = fs

    def execute(self, path: str, content: str, append: bool = False) -> str:
        try:
            result = self._fs.write_file(path, content, append)
            return f"Written to {result} ({len(content)} chars, append={append})"
        except Exception as e:
            return f"[Error writing file: {e}]"


class ListDirTool(VizierTool):
    name = "list_dir"
    description = "List directory contents with metadata."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path"},
            "include_hidden": {"type": "boolean", "default": False},
            "recursive": {"type": "boolean", "default": False},
        },
        "required": ["path"],
    }
    category = ToolCategory.FILESYSTEM.value
    dangerous = False

    def __init__(self, fs: FilesystemManager):
        super().__init__()
        self._fs = fs

    def execute(self, path: str, include_hidden: bool = False, recursive: bool = False) -> str:
        try:
            entries = self._fs.list_dir(path, include_hidden, recursive)
            return json.dumps(entries, indent=2)
        except Exception as e:
            return f"[Error listing directory: {e}]"


class FileInfoTool(VizierTool):
    name = "file_info"
    description = "Get detailed metadata for a file or directory."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File or directory path"},
        },
        "required": ["path"],
    }
    category = ToolCategory.FILESYSTEM.value
    dangerous = False

    def __init__(self, fs: FilesystemManager):
        super().__init__()
        self._fs = fs

    def execute(self, path: str) -> str:
        try:
            info = self._fs.file_info(path)
            return json.dumps(info, indent=2, default=str)
        except Exception as e:
            return f"[Error getting file info: {e}]"


class FileMoveTool(VizierTool):
    name = "move_file"
    description = "Move or rename a file or directory."
    parameters = {
        "type": "object",
        "properties": {
            "src": {"type": "string", "description": "Source path"},
            "dst": {"type": "string", "description": "Destination path"},
        },
        "required": ["src", "dst"],
    }
    category = ToolCategory.FILESYSTEM.value
    dangerous = True

    def __init__(self, fs: FilesystemManager):
        super().__init__()
        self._fs = fs

    def execute(self, src: str, dst: str) -> str:
        try:
            return f"Moved: {self._fs.move(src, dst)}"
        except Exception as e:
            return f"[Error moving file: {e}]"


class FileDeleteTool(VizierTool):
    name = "delete_file"
    description = "Delete a file or directory (recursive=True for non-empty dirs)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to delete"},
            "recursive": {"type": "boolean", "default": False},
        },
        "required": ["path"],
    }
    category = ToolCategory.FILESYSTEM.value
    dangerous = True

    def __init__(self, fs: FilesystemManager):
        super().__init__()
        self._fs = fs

    def execute(self, path: str, recursive: bool = False) -> str:
        try:
            return f"Deleted: {self._fs.delete(path, recursive)}"
        except Exception as e:
            return f"[Error deleting: {e}]"


class FileSearchTool(VizierTool):
    name = "search_files"
    description = "Search for files by name pattern."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "File name pattern"},
            "path": {"type": "string", "description": "Search root path"},
            "max_results": {"type": "integer", "default": 50},
            "file_types": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["query"],
    }
    category = ToolCategory.FILESYSTEM.value
    dangerous = False

    def __init__(self, fs: FilesystemManager):
        super().__init__()
        self._fs = fs

    def execute(self, query: str, path: str | None = None,
                max_results: int = 50, file_types: list | None = None) -> str:
        try:
            results = self._fs.search(query, path, max_results, file_types)
            return json.dumps(results, indent=2)
        except Exception as e:
            return f"[Error searching: {e}]"


class MakeDirTool(VizierTool):
    name = "make_dir"
    description = "Create a directory (with parents if needed)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path to create"},
        },
        "required": ["path"],
    }
    category = ToolCategory.FILESYSTEM.value
    dangerous = False

    def __init__(self, fs: FilesystemManager):
        super().__init__()
        self._fs = fs

    def execute(self, path: str) -> str:
        try:
            return f"Created: {self._fs.mkdir(path)}"
        except Exception as e:
            return f"[Error creating directory: {e}]"


def get_filesystem_tools(fs: FilesystemManager | None = None) -> list:
    """Factory: create all filesystem tools."""
    fs = fs or FilesystemManager()
    return [
        ReadFileTool(fs), WriteFileTool(fs), ListDirTool(fs),
        FileInfoTool(fs), FileMoveTool(fs), FileDeleteTool(fs),
        FileSearchTool(fs), MakeDirTool(fs),
    ]