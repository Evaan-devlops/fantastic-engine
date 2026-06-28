"""Unit tests for atomic JSON/JSONL storage helpers, SHA-256 utils, and workspace service."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sop_automation.errors import WorkspaceError
from sop_automation.services.workspace import WorkspaceService
from sop_automation.storage.json_store import (
    append_jsonl,
    read_json,
    sha256_of_file,
    sha256_of_str,
    write_json_atomic,
)
from sop_automation.storage.paths import resolve_path


# ---------------------------------------------------------------------------
# 1. write_json_atomic + read_json round-trip
# ---------------------------------------------------------------------------

class TestAtomicJsonRoundTrip:
    def test_write_and_read_back(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        data = {"key": "value", "number": 42}
        write_json_atomic(path, data)
        result = read_json(path)
        assert result == data

    def test_no_tmp_file_remains_after_write(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        write_json_atomic(path, {"x": 1})
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Unexpected .tmp files: {tmp_files}"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        write_json_atomic(path, {"v": 1})
        write_json_atomic(path, {"v": 2})
        assert read_json(path) == {"v": 2}

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "deep" / "data.json"
        write_json_atomic(path, {"ok": True})
        assert read_json(path) == {"ok": True}

    def test_read_json_missing_file_raises_storage_error(self, tmp_path: Path) -> None:
        from sop_automation.errors import StorageError

        path = tmp_path / "missing.json"
        with pytest.raises(StorageError):
            read_json(path)

    def test_read_json_invalid_json_raises_storage_error(self, tmp_path: Path) -> None:
        from sop_automation.errors import StorageError

        path = tmp_path / "bad.json"
        path.write_text("NOT JSON {{{", encoding="utf-8")
        with pytest.raises(StorageError):
            read_json(path)


# ---------------------------------------------------------------------------
# 2. append_jsonl accumulates lines
# ---------------------------------------------------------------------------

class TestAppendJsonl:
    def test_three_records_produce_three_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "events.jsonl"
        records = [{"id": 1}, {"id": 2}, {"id": 3}]
        for record in records:
            append_jsonl(path, record)

        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3

    def test_each_line_is_valid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "events.jsonl"
        for i in range(3):
            append_jsonl(path, {"seq": i, "msg": f"event-{i}"})

        for line in path.read_text(encoding="utf-8").strip().splitlines():
            parsed = json.loads(line)
            assert "seq" in parsed

    def test_accumulates_across_calls(self, tmp_path: Path) -> None:
        path = tmp_path / "log.jsonl"
        append_jsonl(path, {"a": 1})
        append_jsonl(path, {"b": 2})
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert json.loads(lines[0]) == {"a": 1}
        assert json.loads(lines[1]) == {"b": 2}

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "sub" / "log.jsonl"
        append_jsonl(path, {"ok": True})
        assert path.exists()


# ---------------------------------------------------------------------------
# 3. SHA256 helpers
# ---------------------------------------------------------------------------

class TestSha256Helpers:
    def test_sha256_of_str_is_deterministic(self) -> None:
        result1 = sha256_of_str("hello")
        result2 = sha256_of_str("hello")
        assert result1 == result2

    def test_sha256_of_str_differs_for_different_inputs(self) -> None:
        assert sha256_of_str("hello") != sha256_of_str("world")

    def test_sha256_of_str_returns_64_hex_chars(self) -> None:
        result = sha256_of_str("test")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_sha256_of_file_matches_str_hash(self, tmp_path: Path) -> None:
        text = "known content for hashing"
        path = tmp_path / "content.txt"
        path.write_text(text, encoding="utf-8")
        assert sha256_of_file(path) == sha256_of_str(text)

    def test_sha256_of_file_missing_raises_storage_error(self, tmp_path: Path) -> None:
        from sop_automation.errors import StorageError

        path = tmp_path / "missing.txt"
        with pytest.raises(StorageError):
            sha256_of_file(path)


# ---------------------------------------------------------------------------
# 4. resolve_path traversal guard
# ---------------------------------------------------------------------------

class TestResolvePathTraversalGuard:
    def test_traversal_attempt_raises_workspace_error(self, tmp_path: Path) -> None:
        with pytest.raises(WorkspaceError):
            resolve_path(tmp_path, "../../etc/passwd")

    def test_valid_relative_path_succeeds(self, tmp_path: Path) -> None:
        result = resolve_path(tmp_path, "sub/file.json")
        assert str(result).startswith(str(tmp_path.resolve()))

    def test_nested_valid_path_succeeds(self, tmp_path: Path) -> None:
        result = resolve_path(tmp_path, "a/b/c/data.json")
        assert result == (tmp_path / "a" / "b" / "c" / "data.json").resolve()

    def test_same_dir_dot_path_succeeds(self, tmp_path: Path) -> None:
        result = resolve_path(tmp_path, "file.json")
        assert result.parent.resolve() == tmp_path.resolve()

    def test_double_dot_in_middle_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(WorkspaceError):
            resolve_path(tmp_path, "sub/../../outside/file.json")


# ---------------------------------------------------------------------------
# 5. WorkspaceService.init
# ---------------------------------------------------------------------------

class TestWorkspaceServiceInit:
    EXPECTED_SUBDIRS = [
        "inbox",
        "sources",
        "compiled",
        "manifests",
        "runs",
        "resolutions",
        "routes",
        "tool_build_requests",
        "tools",
        "generated",
        "runtime",
        str(Path("runtime") / "commands"),
        str(Path("runtime") / "acknowledgements"),
        str(Path("runtime") / "processed"),
        str(Path("runtime") / "failed"),
    ]

    def test_init_creates_all_fifteen_directories(self, tmp_path: Path) -> None:
        service = WorkspaceService()
        results = service.init(tmp_path)

        created_names = [rel for rel, _ in results]
        statuses = [status for _, status in results]

        assert len(results) == 15
        assert all(status == "CREATED" for status in statuses)

        for subdir in self.EXPECTED_SUBDIRS:
            assert (tmp_path / subdir).is_dir(), f"Missing directory: {subdir}"

    def test_init_returns_correct_relative_paths(self, tmp_path: Path) -> None:
        service = WorkspaceService()
        results = service.init(tmp_path)
        rel_names = [rel for rel, _ in results]
        for expected in self.EXPECTED_SUBDIRS:
            assert any(expected in rel for rel in rel_names), f"'{expected}' not in results"

    def test_init_is_idempotent(self, tmp_path: Path) -> None:
        service = WorkspaceService()
        service.init(tmp_path)
        results2 = service.init(tmp_path)

        statuses = [status for _, status in results2]
        assert all(status == "EXISTS" for status in statuses)

    def test_init_second_run_returns_exists_for_all(self, tmp_path: Path) -> None:
        service = WorkspaceService()
        service.init(tmp_path)
        results = service.init(tmp_path)
        for rel, status in results:
            assert status == "EXISTS", f"Expected EXISTS for '{rel}', got '{status}'"

    def test_init_with_nested_root_creates_parents(self, tmp_path: Path) -> None:
        nested_root = tmp_path / "deep" / "nested" / "workspace"
        service = WorkspaceService()
        results = service.init(nested_root)
        assert all(status == "CREATED" for _, status in results)
        assert (nested_root / "inbox").is_dir()
