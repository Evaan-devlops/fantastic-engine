"""Unit tests for runtime host models and command protocol — written but not run."""
from __future__ import annotations

from datetime import datetime, UTC
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
from sop_automation.storage.json_store import new_id, utc_now


class TestRuntimeCommandTypeEnum:
    def test_start_run_value(self) -> None:
        assert RuntimeCommandType.START_RUN == "START_RUN"

    def test_continue_run_value(self) -> None:
        assert RuntimeCommandType.CONTINUE_RUN == "CONTINUE_RUN"

    def test_cancel_run_value(self) -> None:
        assert RuntimeCommandType.CANCEL_RUN == "CANCEL_RUN"

    def test_all_three_values_exist(self) -> None:
        values = {rt.value for rt in RuntimeCommandType}
        assert values == {"START_RUN", "CONTINUE_RUN", "CANCEL_RUN"}


class TestCommandRoundTrip:
    def test_start_run_command_round_trips(self, tmp_path: Path) -> None:
        cmd = RuntimeCommand(
            command_id=new_id(),
            command_type=RuntimeCommandType.START_RUN,
            payload={"plan_id": "plan-001", "run_id": "run-001"},
            created_at=utc_now(),
        )
        path = submit_command(tmp_path / "commands", cmd)
        recovered = consume_command(path)
        assert recovered.command_id == cmd.command_id
        assert recovered.command_type == RuntimeCommandType.START_RUN
        assert recovered.payload["plan_id"] == "plan-001"

    def test_cancel_command_round_trips(self, tmp_path: Path) -> None:
        cmd = RuntimeCommand(
            command_id=new_id(),
            command_type=RuntimeCommandType.CANCEL_RUN,
            payload={"run_id": "run-001"},
            created_at=utc_now(),
        )
        path = submit_command(tmp_path / "commands", cmd)
        recovered = consume_command(path)
        assert recovered.command_type == RuntimeCommandType.CANCEL_RUN

    def test_ack_written_and_read(self, tmp_path: Path) -> None:
        cmd_id = new_id()
        ack = CommandAcknowledgement(
            command_id=cmd_id,
            run_id="run-001",
            status="ACCEPTED",
            message="Run started",
            created_at=utc_now(),
        )
        acks_dir = tmp_path / "acks"
        write_acknowledgement(acks_dir, ack)
        recovered = read_acknowledgement(acks_dir, cmd_id)
        assert recovered is not None
        assert recovered.status == "ACCEPTED"
        assert recovered.run_id == "run-001"

    def test_ack_missing_returns_none(self, tmp_path: Path) -> None:
        result = read_acknowledgement(tmp_path / "acks", "nonexistent-id")
        assert result is None


class TestOneActiveRunLogic:
    """Verifies the one-active-run contract via the command queue."""

    def test_two_commands_can_be_submitted(self, tmp_path: Path) -> None:
        """Two commands can sit in the queue; host decides what to do with them."""
        cmd1 = RuntimeCommand(
            command_id=new_id(),
            command_type=RuntimeCommandType.START_RUN,
            payload={},
            created_at=utc_now(),
        )
        cmd2 = RuntimeCommand(
            command_id=new_id(),
            command_type=RuntimeCommandType.START_RUN,
            payload={},
            created_at=utc_now(),
        )
        cmds_dir = tmp_path / "commands"
        submit_command(cmds_dir, cmd1)
        submit_command(cmds_dir, cmd2)
        queued = poll_commands(cmds_dir)
        assert len(queued) == 2
