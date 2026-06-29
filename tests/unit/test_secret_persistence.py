"""Stage 1 gate tests — no secret appears in any persisted run artifact."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sop_automation.models.common import ActionType, ElementType, RunStatus
from sop_automation.models.sop import RetryPolicy, WaitConditionSpec, WaitConditionType
from sop_automation.models.task import PlannedCapability, PlannedOutcome, PlannedStep, TaskPlan
from sop_automation.runtime.postconditions import PostconditionEvaluator
from sop_automation.runtime.run_manager import RunManager

_SECRET = "fake-password-for-test-only"
_SAFE_URL = "https://abc.com/login"


# ── shared fakes ─────────────────────────────────────────────────────────────

class _FakeLocator:
    def __init__(self, *, text: str = "", visible: bool = True, count: int = 1) -> None:
        self.text = text
        self.visible = visible
        self._count = count

    async def count(self) -> int:
        return self._count

    def nth(self, index: int) -> "_FakeLocator":
        return self

    async def wait_for(self, state: str, timeout: int) -> None:
        pass

    async def scroll_into_view_if_needed(self, timeout: int) -> None:
        pass

    async def is_visible(self) -> bool:
        return self.visible

    async def is_enabled(self) -> bool:
        return True

    async def is_editable(self) -> bool:
        return True

    async def click(self) -> None:
        pass

    async def fill(self, value: str) -> None:
        self.text = value

    async def input_value(self) -> str:
        return self.text

    async def inner_text(self, timeout: int | None = None) -> str:
        return self.text


class _FakeLocatorService:
    def __init__(self, mapping: dict[str, _FakeLocator]) -> None:
        self.mapping = mapping

    async def locate(self, page: object, element_name: str, element_type: ElementType) -> _FakeLocator:
        loc = self.mapping.get(element_name)
        if loc is None:
            raise RuntimeError(f"missing {element_name}")
        return loc

    def build_locator(self, page: object, element_name: str, element_type: ElementType) -> _FakeLocator:
        return self.mapping.get(element_name, _FakeLocator(count=0, visible=False))

    def candidate_locators(
        self, page: object, element_name: str, element_type: ElementType
    ) -> list[tuple[str, _FakeLocator]]:
        return [("fake", self.build_locator(page, element_name, element_type))]


class _FakePage:
    def __init__(self, url: str = _SAFE_URL) -> None:
        self.url = url

    async def wait_for_load_state(self, state: str, timeout: int) -> None:
        pass

    async def title(self) -> str:
        return "Fixture"

    async def screenshot(self, path: str) -> None:
        Path(path).write_bytes(b"fake")

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(count=0, visible=False)


def _plan_with_inputs(inputs: dict[str, str], steps: list[PlannedStep]) -> TaskPlan:
    return TaskPlan(
        plan_id="plan-1",
        sop_id="sop-1",
        goal_id="goal-1",
        entry_capability_id="cap",
        capabilities=[
            PlannedCapability(
                capability_id="cap",
                name="Cap",
                application_id="fixture",
                steps=steps,
            )
        ],
        inputs=inputs,
        created_at=datetime.now(UTC),
    )


def _all_artifact_text(run_dir: Path) -> str:
    """Read all text-readable files under run_dir."""
    parts: list[str] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.suffix in (".json", ".jsonl", ".txt", ".md", ".log"):
            try:
                parts.append(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
    return "\n".join(parts)


# ── Stage 1 gate: task_plan.json and run_state.json ──────────────────────────

def test_task_plan_json_does_not_contain_raw_password(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    step = PlannedStep(
        capability_id="cap",
        capability_name="Cap",
        application_id="fixture",
        step_id="open",
        sequence=1,
        action=ActionType.OPEN,
        element_name="Page",
        element_type=ElementType.PAGE,
        value=_SAFE_URL,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    plan = _plan_with_inputs({"password": _SECRET, "target_url": _SAFE_URL}, [step])
    manager._dispatcher._locator_svc = _FakeLocatorService({})

    asyncio.run(manager.start_run("run-1", plan, _FakePage()))

    task_plan_text = (run_dir / "task_plan.json").read_text(encoding="utf-8")
    assert _SECRET not in task_plan_text, "task_plan.json must not contain raw password"
    assert _SAFE_URL in task_plan_text, "non-secret URL must be preserved in task_plan.json"


def test_run_state_json_does_not_contain_raw_password(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    step = PlannedStep(
        capability_id="cap",
        capability_name="Cap",
        application_id="fixture",
        step_id="open",
        sequence=1,
        action=ActionType.OPEN,
        element_name="Page",
        element_type=ElementType.PAGE,
        value=_SAFE_URL,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    plan = _plan_with_inputs({"password": _SECRET, "target_url": _SAFE_URL}, [step])
    manager._dispatcher._locator_svc = _FakeLocatorService({})

    asyncio.run(manager.start_run("run-1", plan, _FakePage()))

    run_state_text = (run_dir / "run_state.json").read_text(encoding="utf-8")
    assert _SECRET not in run_state_text, "run_state.json must not contain raw password"
    assert _SAFE_URL in run_state_text, "non-secret URL must be preserved in run_state.json"


def test_events_jsonl_does_not_contain_raw_password(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    step = PlannedStep(
        capability_id="cap",
        capability_name="Cap",
        application_id="fixture",
        step_id="open",
        sequence=1,
        action=ActionType.OPEN,
        element_name="Page",
        element_type=ElementType.PAGE,
        value=_SAFE_URL,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    plan = _plan_with_inputs({"password": _SECRET}, [step])
    manager._dispatcher._locator_svc = _FakeLocatorService({})

    asyncio.run(manager.start_run("run-1", plan, _FakePage()))

    events_text = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    assert _SECRET not in events_text, "events.jsonl must not contain raw password"


def test_failed_execution_does_not_leak_password(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    step = PlannedStep(
        capability_id="cap",
        capability_name="Cap",
        application_id="fixture",
        step_id="fill_password",
        sequence=1,
        action=ActionType.FILL,
        element_name="Password",
        element_type=ElementType.TEXTBOX,
        value="{{input.password}}",
        retry_policy=RetryPolicy(max_attempts=1),
    )
    plan = _plan_with_inputs({"password": _SECRET}, [step])
    password_locator = _FakeLocator()
    manager._dispatcher._locator_svc = _FakeLocatorService({"Password": password_locator})

    state = asyncio.run(manager.start_run("run-1", plan, _FakePage()))

    assert state.status in (RunStatus.COMPLETED, RunStatus.WAITING_FOR_CLARIFICATION, RunStatus.FAILED)
    artifact_text = _all_artifact_text(run_dir)
    assert _SECRET not in artifact_text, "No run artifact must contain raw password"


def test_clarification_request_does_not_contain_password(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    step = PlannedStep(
        capability_id="cap",
        capability_name="Cap",
        application_id="fixture",
        step_id="fill_pass",
        sequence=1,
        action=ActionType.FILL,
        element_name="Password",
        element_type=ElementType.TEXTBOX,
        value="{{input.password}}",
        retry_policy=RetryPolicy(max_attempts=1),
    )
    plan = _plan_with_inputs({"password": _SECRET}, [step])
    locator_svc = _FakeLocatorService({})

    class _RaiseLocatorService(_FakeLocatorService):
        async def locate(self, page: object, element_name: str, element_type: ElementType) -> _FakeLocator:
            raise RuntimeError(f"Could not locate element {element_name!r}")

    manager._dispatcher._locator_svc = _RaiseLocatorService({})

    state = asyncio.run(manager.start_run("run-1", plan, _FakePage()))

    assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
    clarification_path = run_dir / "clarification_request.json"
    assert clarification_path.exists()
    clarification_text = clarification_path.read_text(encoding="utf-8")
    assert _SECRET not in clarification_text, "clarification_request.json must not contain raw password"


def test_postcondition_failure_does_not_expose_secret_expected_value(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    password_field = _FakeLocator(text="wrong-value")
    locator_svc = _FakeLocatorService({"Password": password_field})
    manager._dispatcher._locator_svc = locator_svc
    manager._dispatcher._postconditions = PostconditionEvaluator(locator_svc)
    manager._postconditions = PostconditionEvaluator(locator_svc)

    step = PlannedStep(
        capability_id="cap",
        capability_name="Cap",
        application_id="fixture",
        step_id="click_next",
        sequence=1,
        action=ActionType.CLICK,
        element_name="Password",
        element_type=ElementType.BUTTON,
        postcondition=WaitConditionSpec(
            type=WaitConditionType.ELEMENT_VALUE_EQUALS,
            element_name="Password",
            element_type=ElementType.TEXTBOX.value,
            expected_value=_SECRET,
            timeout_seconds=0.01,
            poll_interval_seconds=0.001,
        ),
        retry_policy=RetryPolicy(max_attempts=1),
    )
    plan = _plan_with_inputs({"password": _SECRET}, [step])

    state = asyncio.run(manager.start_run("run-1", plan, _FakePage()))

    assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
    artifact_text = _all_artifact_text(run_dir)
    assert _SECRET not in artifact_text


def test_ordinary_non_secret_value_preserved_in_persisted_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    step = PlannedStep(
        capability_id="cap",
        capability_name="Cap",
        application_id="fixture",
        step_id="open",
        sequence=1,
        action=ActionType.OPEN,
        element_name="Page",
        element_type=ElementType.PAGE,
        value=_SAFE_URL,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    plan = _plan_with_inputs({"target_url": _SAFE_URL}, [step])
    manager._dispatcher._locator_svc = _FakeLocatorService({})

    asyncio.run(manager.start_run("run-1", plan, _FakePage()))

    task_plan = json.loads((run_dir / "task_plan.json").read_text(encoding="utf-8"))
    assert task_plan["inputs"]["target_url"] == _SAFE_URL


def test_api_key_keyword_is_redacted(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    api_key_value = "sk-super-secret-api-key-value"
    step = PlannedStep(
        capability_id="cap",
        capability_name="Cap",
        application_id="fixture",
        step_id="open",
        sequence=1,
        action=ActionType.OPEN,
        element_name="Page",
        element_type=ElementType.PAGE,
        value=_SAFE_URL,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    plan = _plan_with_inputs({"api_key": api_key_value}, [step])
    manager._dispatcher._locator_svc = _FakeLocatorService({})

    asyncio.run(manager.start_run("run-1", plan, _FakePage()))

    artifact_text = _all_artifact_text(run_dir)
    assert api_key_value not in artifact_text


def test_expected_value_in_postcondition_spec_is_redacted(tmp_path: Path) -> None:
    """task_plan.json must not contain the raw secret even as postcondition expected_value."""
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    password_field = _FakeLocator(text=_SECRET)
    locator_svc = _FakeLocatorService({"Password": password_field})
    manager._dispatcher._locator_svc = locator_svc
    manager._dispatcher._postconditions = PostconditionEvaluator(locator_svc)
    manager._postconditions = PostconditionEvaluator(locator_svc)

    step = PlannedStep(
        capability_id="cap",
        capability_name="Cap",
        application_id="fixture",
        step_id="fill_pass",
        sequence=1,
        action=ActionType.FILL,
        element_name="Password",
        element_type=ElementType.TEXTBOX,
        value=_SECRET,
        postcondition=WaitConditionSpec(
            type=WaitConditionType.ELEMENT_VALUE_EQUALS,
            element_name="Password",
            element_type=ElementType.TEXTBOX.value,
            expected_value=_SECRET,
            timeout_seconds=0.01,
            poll_interval_seconds=0.001,
        ),
        retry_policy=RetryPolicy(max_attempts=1),
    )
    plan = _plan_with_inputs({"password": _SECRET}, [step])

    asyncio.run(manager.start_run("run-1", plan, _FakePage()))

    task_plan_text = (run_dir / "task_plan.json").read_text(encoding="utf-8")
    assert _SECRET not in task_plan_text, "task_plan.json must not contain raw password in postcondition expected_value"


def test_non_credential_expected_value_is_preserved(tmp_path: Path) -> None:
    """expected_value in a non-credential postcondition (URL) must NOT be redacted."""
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    locator_svc = _FakeLocatorService({})
    manager._dispatcher._locator_svc = locator_svc
    manager._dispatcher._postconditions = PostconditionEvaluator(locator_svc)
    manager._postconditions = PostconditionEvaluator(locator_svc)

    step = PlannedStep(
        capability_id="cap",
        capability_name="Cap",
        application_id="fixture",
        step_id="open_page",
        sequence=1,
        action=ActionType.OPEN,
        element_name="Page",
        element_type=ElementType.PAGE,
        value=_SAFE_URL,
        postcondition=WaitConditionSpec(
            type=WaitConditionType.URL_CONTAINS,
            expected_value="/login",
            timeout_seconds=0.01,
        ),
        retry_policy=RetryPolicy(max_attempts=1),
    )
    plan = _plan_with_inputs({"target_url": _SAFE_URL}, [step])

    asyncio.run(manager.start_run("run-1", plan, _FakePage(url=_SAFE_URL)))

    task_plan_text = (run_dir / "task_plan.json").read_text(encoding="utf-8")
    assert "/login" in task_plan_text, "non-credential expected_value (URL fragment) must be preserved in task_plan.json"
