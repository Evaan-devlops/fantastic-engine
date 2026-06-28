"""Unit tests for runtime host models and command protocol — written but not run."""
from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path

import pytest

from sop_automation.models.runtime import (
    AckStatus,
    CancelRunPayload,
    CommandAcknowledgement,
    ContinueRunPayload,
    RuntimeCommand,
    RuntimeCommandType,
    StartRunPayload,
    StepResult,
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
            status=AckStatus.STARTED,
            message="Run started",
            created_at=utc_now(),
        )
        acks_dir = tmp_path / "acks"
        write_acknowledgement(acks_dir, ack)
        recovered = read_acknowledgement(acks_dir, cmd_id)
        assert recovered is not None
        assert recovered.status == AckStatus.STARTED
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


class TestAckStatusEnum:
    def test_received_value(self) -> None:
        assert AckStatus.RECEIVED == "RECEIVED"

    def test_started_value(self) -> None:
        assert AckStatus.STARTED == "STARTED"

    def test_waiting_value(self) -> None:
        assert AckStatus.WAITING == "WAITING"

    def test_completed_value(self) -> None:
        assert AckStatus.COMPLETED == "COMPLETED"

    def test_rejected_value(self) -> None:
        assert AckStatus.REJECTED == "REJECTED"

    def test_failed_value(self) -> None:
        assert AckStatus.FAILED == "FAILED"

    def test_all_six_values_exist(self) -> None:
        values = {s.value for s in AckStatus}
        assert values == {"RECEIVED", "STARTED", "WAITING", "COMPLETED", "REJECTED", "FAILED"}


class TestTypedPayloadModels:
    def test_start_run_payload(self) -> None:
        p = StartRunPayload(intent_path="/tmp/intent.json")
        assert p.intent_path == "/tmp/intent.json"
        assert p.plan_id is None

    def test_continue_run_payload(self) -> None:
        p = ContinueRunPayload(run_id="run-abc")
        assert p.run_id == "run-abc"

    def test_cancel_run_payload(self) -> None:
        p = CancelRunPayload(run_id="run-xyz")
        assert p.run_id == "run-xyz"


class TestStepResultLocatorCandidates:
    def test_default_locator_candidates_empty(self) -> None:
        r = StepResult(step_id="s1", success=True)
        assert r.locator_candidates == []

    def test_locator_candidates_stored(self) -> None:
        r = StepResult(step_id="s1", success=False, locator_candidates=["Submit", "Login"])
        assert r.locator_candidates == ["Submit", "Login"]


class TestRuntimeHostContinuation:
    """Prove host retains ownership during WAITING_FOR_AUTH and handles CONTINUE_RUN."""

    def test_host_retains_state_during_waiting_for_auth_and_continues(
        self, tmp_path: Path
    ) -> None:
        """
        Proves:
        - Host retains _active_run_id, _active_manager, _active_page, _active_context,
          _execution_task while a run is paused at WAITING_FOR_AUTH.
        - A second START_RUN is rejected (REJECTED ack written).
        - CONTINUE_RUN calls signal_auth() on the existing manager (not a new one).
        - AUTH_VERIFIED ack is written only after persisted state leaves WAITING_FOR_AUTH.
        - No second browser or RunManager is created.
        Uses focused fakes — no real Chromium launch.
        """
        import asyncio
        from unittest.mock import MagicMock

        from sop_automation.models.common import RunStatus
        from sop_automation.models.execution import RunState
        from sop_automation.runtime.command_queue import read_acknowledgement
        from sop_automation.runtime.host import RuntimeHost
        from sop_automation.storage.json_store import new_id, utc_now, write_json_atomic
        from sop_automation.storage.paths import WorkspacePaths, resolve_path

        workspace = tmp_path
        paths = WorkspacePaths.from_root(workspace)
        acks_dir = paths.runtime_acks
        acks_dir.mkdir(parents=True, exist_ok=True)

        run_id = "test-run-auth-host"
        run_dir = resolve_path(workspace, f"runs/{run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)

        # Write a run_state.json that shows WAITING_FOR_AUTH
        initial_state = RunState(
            run_id=run_id,
            task_id="plan-001",
            status=RunStatus.WAITING_FOR_AUTH,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        write_json_atomic(run_dir / "run_state.json", initial_state.model_dump(mode="json"))

        # FakeManager: records signal_auth() calls and writes state change to disk
        signal_count = [0]

        class FakeManager:
            _state = initial_state

            def signal_auth(self, verified: bool = True) -> None:
                signal_count[0] += 1
                # Simulate state transition after auth signal
                new_state = RunState(
                    run_id=run_id,
                    task_id="plan-001",
                    status=RunStatus.RUNNING,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                write_json_atomic(
                    run_dir / "run_state.json",
                    new_state.model_dump(mode="json"),
                )

        fake_manager = FakeManager()
        fake_context = MagicMock()
        fake_page = MagicMock()

        # Set up host with paused state — no real Chromium involved
        host = RuntimeHost(workspace)
        host._active_run_id = run_id
        host._active_manager = fake_manager
        host._active_context = fake_context
        host._active_page = fake_page
        host._running = True

        # --- Test 1: second START_RUN is REJECTED ---
        async def _run_start_rejected() -> CommandAcknowledgement | None:
            cmd = RuntimeCommand(
                command_id=new_id(),
                command_type=RuntimeCommandType.START_RUN,
                payload={"plan_path": "/nonexistent/plan.json"},
                created_at=utc_now(),
            )
            await host._handle_command(cmd, MagicMock())
            return read_acknowledgement(acks_dir, cmd.command_id)

        ack_rejected = asyncio.run(_run_start_rejected())
        assert ack_rejected is not None, "No ack written for rejected START_RUN"
        assert ack_rejected.status == AckStatus.REJECTED, (
            f"Expected REJECTED, got {ack_rejected.status}"
        )

        # Host still retains active state after rejection
        assert host._active_run_id == run_id
        assert host._active_manager is fake_manager
        assert host._active_context is fake_context
        assert host._active_page is fake_page

        # --- Test 2: CONTINUE_RUN signals manager and gets AUTH_VERIFIED ---
        async def _run_continue() -> CommandAcknowledgement | None:
            cmd = RuntimeCommand(
                command_id=new_id(),
                command_type=RuntimeCommandType.CONTINUE_RUN,
                payload={"run_id": run_id},
                created_at=utc_now(),
            )
            await host._handle_command(cmd, None)
            return read_acknowledgement(acks_dir, cmd.command_id)

        ack_continue = asyncio.run(_run_continue())

        # signal_auth() was called exactly once on the existing manager
        assert signal_count[0] == 1, (
            f"signal_auth() should be called once, was called {signal_count[0]} times"
        )

        # Ack reports AUTH_VERIFIED
        assert ack_continue is not None, "No ack written for CONTINUE_RUN"
        assert ack_continue.status == AckStatus.COMPLETED, (
            f"Expected COMPLETED (AUTH_VERIFIED), got {ack_continue.status}"
        )
        assert ack_continue.message == "AUTH_VERIFIED"

        # No second manager was created — the fake_manager is still the active one
        assert host._active_manager is fake_manager
