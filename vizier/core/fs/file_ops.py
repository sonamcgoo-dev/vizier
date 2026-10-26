"""
Filesystem management — the agent's file-system hands.

Provides read, write, list, move, delete, search, and metadata tools.
All operations are logged.  Destructive operations are flagged as
``dangerous`` so they trigger a YOLO confirmation dialog.
"""
from __future__ import annotations

import contextlib
import fnmatch
import json
import logging
import mimetypes
import shutil
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("vizier.fs")


def _human_readable_size(size: int) -> str:
    """Convert bytes to a human-readable string."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def _default_roots() -> list[Path]:
    """Roots the filesystem manager is allowed to touch by default."""
    roots = [Path.home()]
    # Allow the current working directory even when it lives outside $HOME
    # (common on Windows where projects can live on another drive).
    with contextlib.suppress(OSError):
        roots.append(Path.cwd())
    return roots


class FilesystemManager:
    """Safe, logged filesystem operations.

    Args:
        allowed_roots: Directories the manager may access.  Defaults to the
            user's home directory plus the current working directory.
        strict: When true (default), paths outside ``allowed_roots`` raise
            :class:`PermissionError` instead of being allowed through.
    """

    def __init__(
        self,
        allowed_roots: Iterable[str] | None = None,
        strict: bool = True,
    ):
        self.strict = strict
        if allowed_roots is None:
            self.allowed_roots = _default_roots()
        else:
            self.allowed_roots = [
                Path(r).expanduser().resolve() for r in allowed_roots
            ]

    # -- path handling ----------------------------------------------------

    def _resolve(self, path: str | Path) -> Path:
        """Resolve *path* and ensure it is within an allowed root."""
        raw = Path(path).expanduser()
        p = raw.resolve()
        if not self.strict or not self.allowed_roots:
            return p
        for root in self.allowed_roots:
            try:
                p.relative_to(root)
                return p
            except ValueError:
                continue
        roots = ", ".join(str(r) for r in self.allowed_roots)
        raise PermissionError(
            f"Path is outside the allowed roots ({roots}): {p}"
        )

    # -- read / write -----------------------------------------------------

    def read_file(self, path: str, max_chars: int = 100_000) -> str:
        """Read a text file (truncated to *max_chars*)."""
        p = self._resolve(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        if not p.is_file():
            raise ValueError(f"Not a file: {p}")
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n...[truncated]"
        return content

    def write_file(self, path: str, content: str, append: bool = False) -> str:
        """Write (or append to) a text file."""
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(p, mode, encoding="utf-8") as f:
            f.write(content)
        log.info(f"Wrote {len(content)} chars to {p}")
        return str(p)

    def read_binary(self, path: str, max_bytes: int = 5_000_000) -> str:
        """Read a binary file and return a base64-encoded string."""
        import base64

        p = self._resolve(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        data = p.read_bytes()[:max_bytes]
        return base64.b64encode(data).decode("ascii")

    # -- listing & metadata ----------------------------------------------

    def _entry_info(self, p: Path) -> dict[str, Any]:
        """Return a serialisable metadata dictionary for *p*."""
        try:
            st = p.stat()
        except OSError as e:  # broken symlink, permission error, ...
            return {
                "name": p.name,
                "path": str(p),
                "type": "unknown",
                "error": str(e),
                "is_dir": p.is_dir(),
                "is_file": p.is_file(),
            }
        return {
            "name": p.name,
            "path": str(p),
            "type": "dir" if p.is_dir() else "file",
            "size": st.st_size,
            "size_human": _human_readable_size(st.st_size),
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
            "is_dir": p.is_dir(),
            "is_file": p.is_file(),
        }

    def list_dir(
        self,
        path: str,
        include_hidden: bool = False,
        recursive: bool = False,
    ) -> list[dict[str, Any]]:
        """List directory contents with metadata."""
        p = self._resolve(path)
        if not p.exists():
            raise FileNotFoundError(f"Path not found: {p}")
        if p.is_file():
            return [self._entry_info(p)]
        entries: list[dict[str, Any]] = []
        try:
            items = sorted(p.rglob("*")) if recursive else sorted(p.iterdir())
        except OSError as e:
            raise PermissionError(f"Cannot list {p}: {e}") from e
        for item in items:
            if not include_hidden and item.name.startswith("."):
                continue
            entries.append(self._entry_info(item))
        return entries

    def file_info(self, path: str) -> dict[str, Any]:
        """Get detailed metadata for a single file."""
        p = self._resolve(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        info = self._entry_info(p)
        st = p.stat()
        info["mode"] = oct(st.st_mode)
        info["owner"] = getattr(st, "st_uid", None)
        info["mime_type"] = (
            mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        )
        if p.is_symlink():
            info["symlink_target"] = str(p.resolve())
        return info

    # -- mutations --------------------------------------------------------

    def move(self, src: str, dst: str) -> str:
        """Move or rename *src* to *dst*."""
        src_p = self._resolve(src)
        dst_p = self._resolve(dst)
        if not src_p.exists():
            raise FileNotFoundError(f"Source not found: {src_p}")
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_p), str(dst_p))
        log.info(f"Moved {src_p} -> {dst_p}")
        return str(dst_p)

    def copy(self, src: str, dst: str) -> str:
        """Copy a file or directory tree."""
        src_p = self._resolve(src)
        dst_p = self._resolve(dst)
        if not src_p.exists():
            raise FileNotFoundError(f"Source not found: {src_p}")
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        if src_p.is_dir():
            shutil.copytree(src_p, dst_p, dirs_exist_ok=True)
        else:
            shutil.copy2(src_p, dst_p)
        log.info(f"Copied {src_p} -> {dst_p}")
        return str(dst_p)

    def delete(self, path: str, recursive: bool = False) -> str:
        """Delete a file or directory."""
        p = self._resolve(path)
        if not p.exists():
            raise FileNotFoundError(f"Path not found: {p}")
        if p.is_dir():
            if not recursive:
                try:
                    p.rmdir()
                except OSError as e:
                    raise ValueError(
                        f"Directory not empty, use recursive=True: {p}"
                    ) from e
            else:
                shutil.rmtree(p)
        else:
            p.unlink()
        log.info(f"Deleted: {p}")
        return str(p)

    def mkdir(self, path: str, parents: bool = True) -> str:
        """Create a directory (and parents)."""
        p = self._resolve(path)
        p.mkdir(parents=parents, exist_ok=True)
        return str(p)

    # -- search -----------------------------------------------------------

    def search(
        self,
        query: str,
        path: str | None = None,
        max_results: int = 50,
        file_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for files whose name matches *query* (glob-style)."""
        root = self._resolve(path or str(Path.home()))
        if not root.exists():
            raise FileNotFoundError(f"Search root not found: {root}")
        if root.is_file():
            root = root.parent

        pattern = query if any(ch in query for ch in "*?[") else f"*{query}*"
        suffix_filter = None
        if file_types:
            suffix_filter = {
                t.lower() if t.startswith(".") else f".{t.lower()}"
                for t in file_types
            }

        results: list[dict[str, Any]] = []
        for item in sorted(root.rglob("*")):
            try:
                if not fnmatch.fnmatch(item.name.lower(), pattern.lower()):
                    continue
                if suffix_filter and item.suffix.lower() not in suffix_filter:
                    continue
            except OSError:
                continue
            results.append(self._entry_info(item))
            if len(results) >= max_results:
                break
        return results

    # -- helpers ----------------------------------------------------------

    def exists(self, path: str) -> bool:
        try:
            return self._resolve(path).exists()
        except Exception:
            return False

    def read_json(self, path: str) -> Any:
        p = self._resolve(path)
        return json.loads(p.read_text(encoding="utf-8"))

    def write_json(self, path: str, data: Any, pretty: bool = True) -> str:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        kwargs = {"indent": 2} if pretty else {}
        p.write_text(
            json.dumps(data, ensure_ascii=False, **kwargs), encoding="utf-8"
        )
        return str(p)
