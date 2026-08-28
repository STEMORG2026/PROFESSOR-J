"""Tests for WorkspaceManager — bounded, safety-gated file operations."""

from __future__ import annotations

from pathlib import Path

from app.workspace import WorkspaceManager, WorkspaceSecurityError


def test_read_write_round_trip(tmp_path: Path) -> None:
    wm = WorkspaceManager(tmp_path)
    assert wm.write("notes.md", "hello world")["success"] is True
    got = wm.read("notes.md")
    assert got["success"] is True
    assert got["content"] == "hello world"


def test_list_entries(tmp_path: Path) -> None:
    wm = WorkspaceManager(tmp_path)
    wm.write("a.txt", "a")
    wm.write("sub/b.txt", "b")
    listing = wm.list(".")
    assert listing["success"] is True
    names = {e["name"] for e in listing["entries"]}
    assert "a.txt" in names
    assert "sub" in names


def test_exists(tmp_path: Path) -> None:
    wm = WorkspaceManager(tmp_path)
    wm.write("x.txt", "x")
    assert wm.exists("x.txt") is True
    assert wm.exists("missing.txt") is False


def test_delete_removes_file(tmp_path: Path) -> None:
    wm = WorkspaceManager(tmp_path)
    wm.write("garbage.txt", "data")
    assert wm.exists("garbage.txt")
    assert wm.delete("garbage.txt")["success"] is True
    assert wm.exists("garbage.txt") is False


def test_path_escape_blocked(tmp_path: Path) -> None:
    wm = WorkspaceManager(tmp_path)
    try:
        wm.read("../../etc/passwd")
        raise AssertionError("expected WorkspaceSecurityError")
    except WorkspaceSecurityError:
        pass


def test_max_bytes_enforced(tmp_path: Path) -> None:
    wm = WorkspaceManager(tmp_path, max_bytes=10)
    wm.write("small.txt", "hi")
    too_big = wm.write("big.txt", "x" * 100)
    assert too_big["success"] is False
