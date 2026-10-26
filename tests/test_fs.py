"""Tests for safe filesystem operations."""
from __future__ import annotations

import json

import pytest

from vizier.core.fs.file_ops import FilesystemManager, _human_readable_size


@pytest.fixture()
def fs(tmp_path):
    return FilesystemManager(allowed_roots=[str(tmp_path)])


def test_write_and_read(fs, tmp_path) -> None:
    target = tmp_path / "sub" / "hello.txt"
    written = fs.write_file(str(target), "hello")
    assert written == str(target)
    assert fs.read_file(str(target)) == "hello"


def test_append(fs, tmp_path) -> None:
    target = tmp_path / "a.txt"
    fs.write_file(str(target), "one")
    fs.write_file(str(target), "two", append=True)
    assert fs.read_file(str(target)) == "onetwo"


def test_read_truncates(fs, tmp_path) -> None:
    target = tmp_path / "a.txt"
    fs.write_file(str(target), "abcdef")
    assert fs.read_file(str(target), max_chars=3).startswith("abc")
    assert "truncated" in fs.read_file(str(target), max_chars=3)


def test_list_dir_and_info(fs, tmp_path) -> None:
    (tmp_path / "dir").mkdir()
    fs.write_file(str(tmp_path / "dir" / "x.txt"), "x")
    entries = fs.list_dir(str(tmp_path))
    names = {e["name"] for e in entries}
    assert names == {"dir"}

    nested = {e["name"] for e in fs.list_dir(str(tmp_path / "dir"))}
    assert nested == {"x.txt"}

    info = fs.file_info(str(tmp_path / "dir" / "x.txt"))
    assert info["is_file"] is True
    assert info["size"] == 1
    assert "mime_type" in info


def test_list_dir_recursive_and_hidden(fs, tmp_path) -> None:
    fs.write_file(str(tmp_path / ".hidden"), "h")
    fs.write_file(str(tmp_path / "sub" / "deep.txt"), "d")
    assert all(not e["name"].startswith(".") for e in fs.list_dir(str(tmp_path)))
    recursive = fs.list_dir(str(tmp_path), include_hidden=True, recursive=True)
    assert any(e["name"] == "deep.txt" for e in recursive)


def test_move_copy_delete(fs, tmp_path) -> None:
    src = tmp_path / "src.txt"
    fs.write_file(str(src), "data")
    moved = fs.move(str(src), str(tmp_path / "moved.txt"))
    assert fs.exists(moved)
    assert not src.exists()

    copied = fs.copy(moved, str(tmp_path / "copy.txt"))
    assert fs.read_file(copied) == "data"

    fs.delete(copied)
    assert not fs.exists(copied)


def test_delete_non_empty_requires_recursive(fs, tmp_path) -> None:
    folder = tmp_path / "folder"
    fs.write_file(str(folder / "file.txt"), "x")
    with pytest.raises(ValueError):
        fs.delete(str(folder))
    fs.delete(str(folder), recursive=True)
    assert not folder.exists()


def test_search(fs, tmp_path) -> None:
    fs.write_file(str(tmp_path / "report_final.md"), "x")
    fs.write_file(str(tmp_path / "notes.txt"), "x")
    results = fs.search("report", path=str(tmp_path))
    assert [r["name"] for r in results] == ["report_final.md"]

    results = fs.search("*", path=str(tmp_path), file_types=[".txt"])
    assert [r["name"] for r in results] == ["notes.txt"]


def test_json_helpers(fs, tmp_path) -> None:
    target = tmp_path / "data.json"
    fs.write_json(str(target), {"a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    assert fs.read_json(str(target)) == {"a": 1}


def test_outside_root_is_blocked(fs, tmp_path) -> None:
    outside = tmp_path.parent / "outside.txt"
    with pytest.raises(PermissionError):
        fs.write_file(str(outside), "nope")


def test_non_strict_allows_outside(tmp_path) -> None:
    outside = tmp_path.parent / "outside-nonstrict.txt"
    manager = FilesystemManager(allowed_roots=[str(tmp_path)], strict=False)
    manager.write_file(str(outside), "ok")
    assert outside.read_text(encoding="utf-8") == "ok"
    outside.unlink()


def test_missing_file_raises(fs, tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        fs.read_file(str(tmp_path / "missing.txt"))


def test_human_readable_size() -> None:
    assert _human_readable_size(512) == "512.0 B"
    assert _human_readable_size(2048) == "2.0 KB"
