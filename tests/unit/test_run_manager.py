"""Unit tests for RunManager — written but not run."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sop_automation.errors import DependencyError
from sop_automation.models.common import ActionType, ElementType, RunStatus, StepStatus
from sop_automation.models.runtime import StepResult
from sop_automation.models.task import PlannedCapability, PlannedOutcome, PlannedStep, TaskPlan
from sop_automation.runtime.run_manager import RunManager, _is_credential_step, _topological_sort
from sop_automation.storage.json_store import new_id


def _make_empty_plan() -> TaskPlan:
    return TaskPlan(
        plan_id="plan-001",
        sop_id="sop-001",
        goal_id="goal-001",
        entry_capability_id="cap-001",
        capabilities=[],
        created_at=datetime.now(UTC),
    )


def _make_step_with_name(name: str) -> PlannedStep:
    return PlannedStep(
        capability_id="cap1",
        capability_name="Cap1",
        application_id="app1",
        step_id="s1",
        sequence=1,
        action=ActionType.FILL,
        element_name=name,
        element_type=ElementType.TEXTBOX,
        value="test",
    )


class TestIsCredentialStep:
    def test_password_element_is_credential(self) -> None:
        step = _make_step_with_name("password_field")
        assert _is_credential_step(step) is True

    def test_submit_button_is_not_credential(self) -> None:
        step = _make_step_with_name("submit_button")
        assert _is_credential_step(step) is False

    def test_otp_element_is_credential(self) -> None:
        step = _make_step_with_name("otp_input")
        assert _is_credential_step(step) is True

    def test_username_field_is_not_credential(self) -> None:
        step = _make_step_with_name("username_field")
        assert _is_credential_step(step) is False


class TestRunManagerInit:
    def test_can_be_instantiated(self, tmp_path: Path) -> None:
        mgr = RunManager(tmp_path / "run-001")
        assert mgr is not None

    def test_run_dir_set(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-001"
        mgr = RunManager(run_dir)
        assert mgr.run_dir == run_dir


class TestRunManagerStartRun:
    def test_start_run_creates_run_state_json(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-001"
        mgr = RunManager(run_dir)
        page = AsyncMock()
        page.wait_for_load_state = AsyncMock(return_value=None)
        plan = _make_empty_plan()
        asyncio.run(mgr.start_run(new_id(), plan, page))
        assert (run_dir / "run_state.json").exists()

    def test_start_run_creates_events_jsonl(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-001"
        mgr = RunManager(run_dir)
        page = AsyncMock()
        page.wait_for_load_state = AsyncMock(return_value=None)
        plan = _make_empty_plan()
        asyncio.run(mgr.start_run(new_id(), plan, page))
        assert (run_dir / "events.jsonl").exists()

    def test_start_run_run_state_has_correct_schema(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-001"
        mgr = RunManager(run_dir)
        page = AsyncMock()
        page.wait_for_load_state = AsyncMock(return_value=None)
        plan = _make_empty_plan()
        run_id = new_id()
        asyncio.run(mgr.start_run(run_id, plan, page))
        state_data = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))
        assert "run_id" in state_data
        assert "status" in state_data

    def test_start_run_populates_context_inputs(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-002"
        mgr = RunManager(run_dir)
        page = AsyncMock()
        page.wait_for_load_state = AsyncMock(return_value=None)
        plan = TaskPlan(
            plan_id="plan-x",
            sop_id="sop-x",
            goal_id="goal-x",
            entry_capability_id="cap-x",
            capabilities=[],
            inputs={"email": "test@example.com"},
            created_at=datetime.now(UTC),
        )
        asyncio.run(mgr.start_run(new_id(), plan, page))
        assert mgr._context["inputs"]["email"] == "test@example.com"


class TestTopologicalSort:
    def _make_step(self, step_id: str, deps: list[str]) -> PlannedStep:
        return PlannedStep(
            capability_id="cap1",
            capability_name="Cap1",
            application_id="app1",
            step_id=step_id,
            sequence=1,
            action=ActionType.CLICK,
            element_name="btn",
            element_type=ElementType.BUTTON,
            dependencies=deps,
        )

    def test_no_dependencies_returns_same_steps(self) -> None:
        steps = [self._make_step("a", []), self._make_step("b", [])]
        result = _topological_sort(steps)
        assert len(result) == 2
        assert {s.step_id for s in result} == {"a", "b"}

    def test_b_depends_on_a_a_comes_first(self) -> None:
        a = self._make_step("a", [])
        b = self._make_step("b", ["a"])
        result = _topological_sort([b, a])
        ids = [s.step_id for s in result]
        assert ids.index("a") < ids.index("b")

    def test_cycle_raises_dependency_error(self) -> None:
        a = self._make_step("a", ["b"])
        b = self._make_step("b", ["a"])
        with pytest.raises(DependencyError):
            _topological_sort([a, b])

    def test_missing_dependency_raises_dependency_error(self) -> None:
        a = self._make_step("a", ["nonexistent"])
        with pytest.raises(DependencyError):
            _topological_sort([a])


# ---------------------------------------------------------------------------
# Helpers for terminal/failure semantics tests
# ---------------------------------------------------------------------------

def _make_full_step(
    step_id: str,
    action: ActionType,
    capability_id: str = "cap1",
    element_name: str = "element",
    element_type: ElementType = ElementType.BUTTON,
    value: str | None = None,
    outcomes: list[PlannedOutcome] | None = None,
    sequence: int = 1,
) -> PlannedStep:
    return PlannedStep(
        capability_id=capability_id,
        capability_name="Cap1",
        application_id="app1",
        step_id=step_id,
        sequence=sequence,
        action=action,
        element_name=element_name,
        element_type=element_type,
        value=value,
        outcomes=outcomes or [],
    )


def _make_plan_with_steps(steps: list[PlannedStep], cap_id: str = "cap1") -> TaskPlan:
    cap = PlannedCapability(
        capability_id=cap_id,
        name="Cap1",
        application_id="app1",
        steps=steps,
    )
    return TaskPlan(
        plan_id="plan-001",
        sop_id="sop-001",
        goal_id="goal-001",
        entry_capability_id=cap_id,
        capabilities=[cap],
        created_at=datetime.now(UTC),
    )


def _mock_page(url: str = "http://test/") -> AsyncMock:
    page = AsyncMock()
    page.url = url
    page.wait_for_load_state = AsyncMock(return_value=None)
    return page


# ---------------------------------------------------------------------------
# TestTerminalAndFailureSemantics
# ---------------------------------------------------------------------------

class TestTerminalAndFailureSemantics:
    """Focused tests for every terminal/failure semantic rule (PE items)."""

    def test_end_failure_status_is_failed(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        mgr = RunManager(run_dir)
        step = _make_full_step("s_fail", ActionType.END_FAILURE)
        plan = _make_plan_with_steps([step])
        asyncio.run(mgr.start_run("run-1", plan, _mock_page()))
        assert mgr._state.status == RunStatus.FAILED

    def test_end_failure_no_retry(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        mgr = RunManager(run_dir)
        step = _make_full_step("s_fail", ActionType.END_FAILURE)
        plan = _make_plan_with_steps([step])
        asyncio.run(mgr.start_run("run-1", plan, _mock_page()))
        prog = mgr._state.step_progress.get("s_fail")
        assert prog is not None
        assert prog.attempt_count == 1  # exactly one attempt, no retry

    def test_end_failure_no_clarification(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        mgr = RunManager(run_dir)
        step = _make_full_step("s_fail", ActionType.END_FAILURE)
        plan = _make_plan_with_steps([step])
        asyncio.run(mgr.start_run("run-1", plan, _mock_page()))
        assert not (run_dir / "clarification_request.json").exists()

    def test_end_success_status_is_completed(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        mgr = RunManager(run_dir)
        step = _make_full_step("s_ok", ActionType.END_SUCCESS)
        plan = _make_plan_with_steps([step])
        asyncio.run(mgr.start_run("run-1", plan, _mock_page()))
        assert mgr._state.status == RunStatus.COMPLETED

    def test_deferred_step_status_is_waiting_for_deferred(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        mgr = RunManager(run_dir)
        step = _make_full_step("s_def", ActionType.DEFERRED)
        plan = _make_plan_with_steps([step])
        asyncio.run(mgr.start_run("run-1", plan, _mock_page()))
        assert mgr._state.status == RunStatus.WAITING_FOR_DEFERRED_CAPABILITY

    def test_value_resolution_failure_is_terminal_failed(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        mgr = RunManager(run_dir)
        # {{input.missing_key}} — key does not exist in plan inputs
        step = _make_full_step(
            "s_resolve", ActionType.FILL,
            element_name="email", element_type=ElementType.TEXTBOX,
            value="{{input.missing_key}}",
        )
        plan = _make_plan_with_steps([step])
        asyncio.run(mgr.start_run("run-1", plan, _mock_page()))
        assert mgr._state.status == RunStatus.FAILED
        prog = mgr._state.step_progress.get("s_resolve")
        assert prog is not None
        assert "VALUE_RESOLUTION_FAILED" in (prog.error_message or "")

    def test_cancel_during_auth_stays_cancelled(self, tmp_path: Path) -> None:
        """cancel() during MANUAL_AUTH sets CANCELLED; state is not overwritten with WAITING_FOR_AUTH."""
        run_dir = tmp_path / "run"
        step = _make_full_step("s_auth", ActionType.MANUAL_AUTH)
        plan = _make_plan_with_steps([step])

        async def _run_and_cancel() -> RunManager:
            mgr = RunManager(run_dir)
            task = asyncio.create_task(mgr.start_run("run-1", plan, _mock_page()))

            # Wait until WAITING_FOR_AUTH
            deadline = asyncio.get_event_loop().time() + 5.0
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(0.05)
                if mgr._state and mgr._state.status == RunStatus.WAITING_FOR_AUTH:
                    break

            mgr.cancel()
            await asyncio.wait_for(task, timeout=5.0)
            return mgr

        mgr = asyncio.run(_run_and_cancel())
        assert mgr._state.status == RunStatus.CANCELLED

    def test_terminal_outcome_stops_later_steps(self, tmp_path: Path) -> None:
        """A step with a terminal outcome causes subsequent steps to be skipped."""
        run_dir = tmp_path / "run"
        mgr = RunManager(run_dir)
        # Step 1: END_FAILURE (terminal) — sets FAILED
        step1 = _make_full_step("s_terminal", ActionType.END_FAILURE, sequence=1)
        # Step 2: END_SUCCESS — should NOT be executed
        step2 = _make_full_step("s_never", ActionType.END_SUCCESS, sequence=2)
        plan = _make_plan_with_steps([step1, step2])
        asyncio.run(mgr.start_run("run-1", plan, _mock_page()))
        assert mgr._state.status == RunStatus.FAILED
        assert "s_never" not in mgr._state.step_progress
