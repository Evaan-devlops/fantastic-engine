"""Unit tests for ActionDispatcher — written but not run."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from sop_automation.models.common import ActionType, ElementType
from sop_automation.models.runtime import StepResult
from sop_automation.models.task import PlannedStep
from sop_automation.runtime.action_dispatcher import ActionDispatcher


def _make_step(action: ActionType, **kwargs) -> PlannedStep:
    return PlannedStep(
        capability_id="cap1",
        capability_name="Cap1",
        application_id="app1",
        step_id="s1",
        sequence=1,
        action=action,
        element_name=kwargs.get("element_name", "element"),
        element_type=kwargs.get("element_type", ElementType.PAGE),
        value=kwargs.get("value", None),
    )


def _make_page() -> AsyncMock:
    page = AsyncMock()
    page.wait_for_load_state = AsyncMock(return_value=None)
    page.url = "http://localhost/"
    return page


class TestActionDispatcherImport:
    def test_can_be_instantiated(self) -> None:
        d = ActionDispatcher()
        assert d is not None

    def test_execute_method_exists(self) -> None:
        d = ActionDispatcher()
        assert hasattr(d, "execute")


class TestTerminalActions:
    def test_end_success_returns_success_result(self, tmp_path: Path) -> None:
        dispatcher = ActionDispatcher()
        step = _make_step(ActionType.END_SUCCESS)
        page = _make_page()
        result = asyncio.run(dispatcher.execute(page, step, {}, tmp_path))
        assert isinstance(result, StepResult)
        assert result.success is True

    def test_end_failure_returns_failure_result(self, tmp_path: Path) -> None:
        dispatcher = ActionDispatcher()
        step = _make_step(ActionType.END_FAILURE)
        page = _make_page()
        result = asyncio.run(dispatcher.execute(page, step, {}, tmp_path))
        assert isinstance(result, StepResult)
        assert result.success is False

    def test_manual_auth_returns_false_with_error_message(self, tmp_path: Path) -> None:
        dispatcher = ActionDispatcher()
        step = _make_step(ActionType.MANUAL_AUTH)
        page = _make_page()
        result = asyncio.run(dispatcher.execute(page, step, {}, tmp_path))
        assert isinstance(result, StepResult)
        assert result.success is False
        assert result.error_message == "MANUAL_AUTH_REQUIRED"

    def test_deferred_returns_failure(self, tmp_path: Path) -> None:
        dispatcher = ActionDispatcher()
        step = _make_step(ActionType.DEFERRED)
        page = _make_page()
        result = asyncio.run(dispatcher.execute(page, step, {}, tmp_path))
        assert isinstance(result, StepResult)
        assert result.success is False
        assert result.error_message == "DEFERRED_CAPABILITY"
