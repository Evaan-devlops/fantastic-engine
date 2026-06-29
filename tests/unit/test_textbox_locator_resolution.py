"""Textbox locator resolution tests."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from sop_automation.models.common import ActionType, ElementType, RunStatus, StepStatus
from sop_automation.models.task import PlannedCapability, PlannedStep, TaskPlan
from sop_automation.runtime.action_dispatcher import ActionDispatcher
from sop_automation.runtime.locator_service import (
    LocatorAmbiguityError,
    LocatorError,
    LocatorService,
    normalize_element_name,
)
from sop_automation.runtime.run_manager import RunManager


FILL_VALUE = "test-user@example.invalid"


class FakeLocator:
    def __init__(
        self,
        count: int = 0,
        *,
        visible: bool = True,
        visible_by_index: list[bool] | None = None,
        count_sequence: list[int] | None = None,
        parent: "FakeLocator | None" = None,
    ) -> None:
        self._count = count
        self._visible = visible
        self._visible_by_index = visible_by_index
        self._count_sequence = count_sequence or []
        self._parent = parent
        self.count_calls = 0
        self.filled_value: str | None = None

    async def count(self) -> int:
        self.count_calls += 1
        if self._count_sequence:
            self._count = self._count_sequence.pop(0)
        return self._count

    def nth(self, index: int) -> "FakeLocator":
        visible = True
        if self._visible_by_index is not None:
            visible = self._visible_by_index[index]
        return FakeLocator(count=1, visible=visible, parent=self)

    async def is_visible(self) -> bool:
        return self._visible

    async def wait_for(self, state: str, timeout: int) -> None:
        return None

    async def is_enabled(self) -> bool:
        return True

    async def is_editable(self) -> bool:
        return True

    async def fill(self, value: str) -> None:
        target = self._parent or self
        target.filled_value = value

    async def input_value(self) -> str:
        target = self._parent or self
        return target.filled_value or ""


class FakeElement:
    async def inner_text(self) -> str:
        return ""

    async def get_attribute(self, name: str) -> str | None:
        return None

    async def is_visible(self) -> bool:
        return True


class FakePage:
    def __init__(
        self,
        *,
        role: dict[tuple[str, str], FakeLocator] | None = None,
        label: dict[str, FakeLocator] | None = None,
        placeholder: dict[str, FakeLocator] | None = None,
    ) -> None:
        self.role = role or {}
        self.label = label or {}
        self.placeholder = placeholder or {}
        self.text: dict[str, FakeLocator] = {}
        self.url = "http://fixture.local/email-login"

    def get_by_role(self, role: str, *, name: re.Pattern[str] | str) -> FakeLocator:
        pattern = name.pattern if isinstance(name, re.Pattern) else name
        return self.role.get((role, pattern.lower()), FakeLocator())

    def get_by_label(self, name: re.Pattern[str] | str) -> FakeLocator:
        pattern = name.pattern if isinstance(name, re.Pattern) else name
        return self.label.get(pattern.lower(), FakeLocator())

    def get_by_placeholder(self, name: re.Pattern[str] | str) -> FakeLocator:
        pattern = name.pattern if isinstance(name, re.Pattern) else name
        return self.placeholder.get(pattern.lower(), FakeLocator())

    def get_by_text(self, text: str, exact: bool) -> FakeLocator:
        return self.text.get(text, FakeLocator())

    async def wait_for_load_state(self, state: str, timeout: int) -> None:
        return None

    async def query_selector_all(self, selector: str) -> list[FakeElement]:
        return []

    async def screenshot(self, path: str) -> None:
        Path(path).write_bytes(b"fake screenshot")


def _pattern(text: str) -> str:
    return f"^{re.escape(text)}$".lower()


def _contains_pattern(text: str) -> str:
    escaped = re.escape(text).replace(r"\ ", r"\s+")
    return rf"\b{escaped}\b".lower()


def _fill_step(element_name: str) -> PlannedStep:
    return PlannedStep(
        capability_id="login_cap",
        capability_name="Login",
        application_id="fixture_app",
        step_id="fill_email",
        sequence=1,
        action=ActionType.FILL,
        element_name=element_name,
        element_type=ElementType.TEXTBOX,
        value=FILL_VALUE,
    )


def _fill_plan(element_name: str) -> TaskPlan:
    return TaskPlan(
        plan_id="textbox-plan",
        sop_id="textbox-sop",
        goal_id="textbox-goal",
        entry_capability_id="login_cap",
        capabilities=[
            PlannedCapability(
                capability_id="login_cap",
                name="Login",
                application_id="fixture_app",
                steps=[_fill_step(element_name)],
            )
        ],
        inputs={},
        created_at=datetime.now(UTC),
    )


def _fill_then_missing_click_plan() -> TaskPlan:
    return TaskPlan(
        plan_id="textbox-redaction-plan",
        sop_id="textbox-sop",
        goal_id="textbox-goal",
        entry_capability_id="login_cap",
        capabilities=[
            PlannedCapability(
                capability_id="login_cap",
                name="Login",
                application_id="fixture_app",
                steps=[
                    _fill_step("Email Address textbox"),
                    PlannedStep(
                        capability_id="login_cap",
                        capability_name="Login",
                        application_id="fixture_app",
                        step_id="click_missing",
                        sequence=2,
                        action=ActionType.CLICK,
                        element_name="Missing Next button",
                        element_type=ElementType.BUTTON,
                    ),
                ],
            )
        ],
        inputs={},
        created_at=datetime.now(UTC),
    )


class TestTextboxLocatorResolution:
    def test_textbox_suffix_is_removed_for_accessible_name(self) -> None:
        assert normalize_element_name("Email Address textbox", ElementType.TEXTBOX) == "Email Address"
        assert normalize_element_name("Email Address input field", ElementType.TEXTBOX) == "Email Address"
        assert normalize_element_name("Email Address text box", ElementType.TEXTBOX) == "Email Address"

    def test_label_lookup_fills_normalized_textbox_name(self, tmp_path: Path) -> None:
        locator = FakeLocator(count=1)
        page = FakePage(label={_pattern("Email Address"): locator})
        dispatcher = ActionDispatcher()
        result = asyncio.run(
            dispatcher.execute(page, _fill_step("Email Address textbox"), {}, tmp_path)
        )

        assert result.success is True
        assert locator.filled_value == FILL_VALUE

    def test_waits_for_delayed_textbox_before_reporting_missing(self, tmp_path: Path) -> None:
        locator = FakeLocator(count_sequence=[0, 0, 1])
        page = FakePage(label={_pattern("Email Address"): locator})
        dispatcher = ActionDispatcher()
        dispatcher._locator_svc = LocatorService(timeout_seconds=0.5, poll_seconds=0.01)

        result = asyncio.run(
            dispatcher.execute(page, _fill_step("Email Address textbox"), {}, tmp_path)
        )

        assert result.success is True
        assert locator.count_calls > 1
        assert locator.filled_value == FILL_VALUE

    def test_placeholder_fallback_uses_semantic_textbox_name(self, tmp_path: Path) -> None:
        locator = FakeLocator(count=1)
        page = FakePage(placeholder={_contains_pattern("Email Address"): locator})
        dispatcher = ActionDispatcher()
        result = asyncio.run(
            dispatcher.execute(page, _fill_step("Email Address textbox"), {}, tmp_path)
        )

        assert result.success is True
        assert locator.filled_value == FILL_VALUE

    def test_missing_textbox_returns_controlled_locator_error(self) -> None:
        page = FakePage()
        service = LocatorService(timeout_seconds=0.01, poll_seconds=0.001)

        try:
            asyncio.run(service.locate(page, "Email Address textbox", ElementType.TEXTBOX))
        except LocatorError as exc:
            assert "Email Address textbox" in str(exc)
            assert "role=textbox[name='Email Address']" in str(exc)
        else:
            raise AssertionError("expected LocatorError")

    def test_hidden_duplicate_textbox_does_not_create_false_ambiguity(self, tmp_path: Path) -> None:
        locator = FakeLocator(count=2, visible_by_index=[False, True])
        page = FakePage(role={("textbox", _pattern("Email Address")): locator})
        dispatcher = ActionDispatcher()

        result = asyncio.run(
            dispatcher.execute(page, _fill_step("Email Address textbox"), {}, tmp_path)
        )

        assert result.success is True
        assert locator.filled_value == FILL_VALUE

    def test_multiple_visible_matching_textboxes_return_ambiguity_error(self) -> None:
        page = FakePage(
            role={("textbox", _pattern("Email Address")): FakeLocator(
                count=2, visible_by_index=[True, True]
            )}
        )
        service = LocatorService(timeout_seconds=0.01, poll_seconds=0.001)

        try:
            asyncio.run(service.locate(page, "Email Address textbox", ElementType.TEXTBOX))
        except LocatorAmbiguityError as exc:
            assert exc.count == 2
            assert "Ambiguous locator" in str(exc)
        else:
            raise AssertionError("expected LocatorAmbiguityError")

    def test_successful_fill_value_is_not_persisted_in_later_failure_diagnostics(
        self, tmp_path: Path
    ) -> None:
        run_dir = tmp_path / "runs" / "textbox-run"
        manager = RunManager(run_dir)
        manager._dispatcher._locator_svc = LocatorService(timeout_seconds=0.01, poll_seconds=0.001)
        page = FakePage(label={_pattern("Email Address"): FakeLocator(count=1)})

        state = asyncio.run(manager.start_run("textbox-run", _fill_then_missing_click_plan(), page))

        assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
        assert state.step_progress["fill_email"].status == StepStatus.COMPLETED
        assert state.step_progress["click_missing"].status == StepStatus.FAILED
        diagnostic_paths = [
            run_dir / "events.jsonl",
            run_dir / "run_state.json",
            run_dir / "clarification_request.json",
        ]
        diagnostic_text = "\n".join(path.read_text(encoding="utf-8") for path in diagnostic_paths)
        clarification = json.loads((run_dir / "clarification_request.json").read_text())
        assert clarification["expected_element"] == "Missing Next button"
        assert FILL_VALUE not in diagnostic_text
