"""Unit tests for RunManager — written but not run."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from sop_automation.models.common import ActionType, ElementType
from sop_automation.models.task import PlannedStep, TaskPlan
from sop_automation.runtime.run_manager import RunManager, _is_credential_step
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
