"""Unit tests for command_queue — written but not run."""
from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sop_automation.models.runtime import (
    CommandAcknowledgement,
    RuntimeCommand,
    RuntimeCommandType,
)
from sop_automation.runtime.command_queue import (
    consume_command,
    poll_commands,
    read_acknowledgement,
    submit_command,
    write_acknowledgement,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_command(
    command_id: str = "cmd-001",
    command_type: RuntimeCommandType = RuntimeCommandType.START_RUN,
    payload: dict | None = None,
) -> RuntimeCommand:
    return RuntimeCommand(
        command_id=command_id,
        command_type=command_type,
        payload=payload or {},
        created_at=datetime.now(UTC),
    )


def _make_ack(
    command_id: str = "cmd-001",
    status: str = "ACCEPTED",
    run_id: str | None = None,
    message: str | None = None,
) -> CommandAcknowledgement:
    return CommandAcknowledgement(
        command_id=command_id,
        run_id=run_id,
        status=status,
        message=message,
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# TestSubmitCommand
# ---------------------------------------------------------------------------

class TestSubmitCommand:
    def test_submit_creates_file(self, tmp_path: Path) -> None:
        commands_dir = tmp_path / "commands"
        cmd = _make_command("abc123")
        returned_path = submit_command(commands_dir, cmd)
        assert returned_path.exists()

    def test_file_named_by_command_id(self, tmp_path: Path) -> None:
        commands_dir = tmp_path / "commands"
        cmd = _make_command("my-unique-id")
        returned_path = submit_command(commands_dir, cmd)
        assert returned_path.name == "my-unique-id.json"

    def test_submit_creates_parent_dirs(self, tmp_path: Path) -> None:
        commands_dir = tmp_path / "deep" / "nested" / "commands"
        cmd = _make_command("cmd-nested")
        submit_command(commands_dir, cmd)
        assert commands_dir.is_dir()

    def test_submitted_file_is_valid_json(self, tmp_path: Path) -> None:
        import json

        commands_dir = tmp_path / "commands"
        cmd = _make_command("cmd-json-check")
        path = submit_command(commands_dir, cmd)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["command_id"] == "cmd-json-check"
        assert data["command_type"] == RuntimeCommandType.START_RUN.value


# ---------------------------------------------------------------------------
# TestPollCommands
# ---------------------------------------------------------------------------

class TestPollCommands:
    def test_empty_dir_returns_empty_list(self, tmp_path: Path) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        result = poll_commands(commands_dir)
        assert result == []

    def test_nonexistent_dir_returns_empty_list(self, tmp_path: Path) -> None:
        commands_dir = tmp_path / "does_not_exist"
        result = poll_commands(commands_dir)
        assert result == []

    def test_multiple_files_sorted_oldest_first(self, tmp_path: Path) -> None:
        commands_dir = tmp_path / "commands"
        cmd_a = _make_command("cmd-a")
        cmd_b = _make_command("cmd-b")
        cmd_c = _make_command("cmd-c")

        path_a = submit_command(commands_dir, cmd_a)
        # Ensure distinct mtime by touching with explicit times
        time.sleep(0.02)
        path_b = submit_command(commands_dir, cmd_b)
        time.sleep(0.02)
        path_c = submit_command(commands_dir, cmd_c)

        polled = poll_commands(commands_dir)
        assert len(polled) == 3
        # Sorted oldest → newest
        assert polled[0].name == path_a.name
        assert polled[2].name == path_c.name

    def test_non_json_files_excluded(self, tmp_path: Path) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "noise.txt").write_text("ignored", encoding="utf-8")
        result = poll_commands(commands_dir)
        assert result == []

    def test_returns_path_objects(self, tmp_path: Path) -> None:
        commands_dir = tmp_path / "commands"
        submit_command(commands_dir, _make_command("cmd-type-check"))
        result = poll_commands(commands_dir)
        assert all(isinstance(p, Path) for p in result)


# ---------------------------------------------------------------------------
# TestConsumeCommand
# ---------------------------------------------------------------------------

class TestConsumeCommand:
    def test_consume_returns_runtime_command(self, tmp_path: Path) -> None:
        commands_dir = tmp_path / "commands"
        cmd = _make_command("cmd-to-consume", RuntimeCommandType.CANCEL_RUN)
        path = submit_command(commands_dir, cmd)
        result = consume_command(path)
        assert isinstance(result, RuntimeCommand)
        assert result.command_id == "cmd-to-consume"
        assert result.command_type == RuntimeCommandType.CANCEL_RUN

    def test_consume_deletes_file(self, tmp_path: Path) -> None:
        commands_dir = tmp_path / "commands"
        path = submit_command(commands_dir, _make_command("cmd-del"))
        assert path.exists()
        consume_command(path)
        assert not path.exists()

    def test_consume_preserves_payload(self, tmp_path: Path) -> None:
        commands_dir = tmp_path / "commands"
        payload = {"run_id": "run-xyz", "sop_id": "my-sop"}
        cmd = _make_command("cmd-payload", payload=payload)
        path = submit_command(commands_dir, cmd)
        result = consume_command(path)
        assert result.payload == payload


# ---------------------------------------------------------------------------
# TestAcknowledgement
# ---------------------------------------------------------------------------

class TestAcknowledgement:
    def test_write_and_read_back(self, tmp_path: Path) -> None:
        acks_dir = tmp_path / "acks"
        ack = _make_ack("cmd-ack-01", status="ACCEPTED", run_id="run-abc")
        write_acknowledgement(acks_dir, ack)
        result = read_acknowledgement(acks_dir, "cmd-ack-01")
        assert result is not None
        assert result.command_id == "cmd-ack-01"
        assert result.status == "ACCEPTED"
        assert result.run_id == "run-abc"

    def test_missing_returns_none(self, tmp_path: Path) -> None:
        acks_dir = tmp_path / "acks"
        acks_dir.mkdir()
        result = read_acknowledgement(acks_dir, "nonexistent-id")
        assert result is None

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        acks_dir = tmp_path / "deep" / "acks"
        ack = _make_ack("cmd-dir-test")
        write_acknowledgement(acks_dir, ack)
        assert acks_dir.is_dir()

    def test_ack_file_named_by_command_id(self, tmp_path: Path) -> None:
        acks_dir = tmp_path / "acks"
        ack = _make_ack("cmd-file-name")
        write_acknowledgement(acks_dir, ack)
        assert (acks_dir / "cmd-file-name.json").exists()

    def test_message_field_preserved(self, tmp_path: Path) -> None:
        acks_dir = tmp_path / "acks"
        ack = _make_ack("cmd-msg", message="Run started successfully.")
        write_acknowledgement(acks_dir, ack)
        result = read_acknowledgement(acks_dir, "cmd-msg")
        assert result is not None
        assert result.message == "Run started successfully."
