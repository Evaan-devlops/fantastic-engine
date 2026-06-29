"""Focused Milestone 1 runtime reliability tests."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

from sop_automation.models.common import ActionType, ElementType, RunStatus, StepStatus
from sop_automation.models.sop import (
    ConditionOperator,
    ConditionSpec,
    RetryPolicy,
    WaitConditionSpec,
    WaitConditionType,
)
from sop_automation.models.task import PlannedCapability, PlannedOutcome, PlannedStep, TaskPlan
from sop_automation.runtime.action_dispatcher import ActionDispatcher
from sop_automation.runtime.auth_classifier import AuthBranch, classify_auth_branch
from sop_automation.runtime.diagnostics import CandidateAttempt, classify_failure, redact_text
from sop_automation.runtime.locator_service import LocatorError
from sop_automation.runtime.postconditions import PostconditionEvaluator
from sop_automation.runtime.run_manager import RunManager


class FakeLocator:
    def __init__(
        self,
        *,
        text: str = "",
        visible: bool = True,
        count: int = 1,
        input_raises: bool = False,
    ) -> None:
        self.text = text
        self.visible = visible
        self._count = count
        self.input_raises = input_raises
        self.clicked = False

    async def count(self) -> int:
        return self._count

    def nth(self, index: int) -> "FakeLocator":
        return self

    async def wait_for(self, state: str, timeout: int) -> None:
        if state == "visible" and not self.visible:
            raise TimeoutError("not visible")

    async def scroll_into_view_if_needed(self, timeout: int) -> None:
        return None

    async def is_visible(self) -> bool:
        return self.visible

    async def is_enabled(self) -> bool:
        return True

    async def is_editable(self) -> bool:
        return True

    async def click(self) -> None:
        self.clicked = True

    async def fill(self, value: str) -> None:
        self.text = value

    async def input_value(self) -> str:
        if self.input_raises:
            raise RuntimeError("input unavailable")
        return self.text

    async def inner_text(self, timeout: int | None = None) -> str:
        return self.text


class FakePage:
    def __init__(self, url: str = "http://fixture/auth/login", body: str = "") -> None:
        self.url = url
        self.body = body
        self.locators: dict[str, FakeLocator] = {}

    async def wait_for_load_state(self, state: str, timeout: int) -> None:
        return None

    async def title(self) -> str:
        return "Fixture"

    async def screenshot(self, path: str) -> None:
        Path(path).write_bytes(b"fake screenshot")

    def locator(self, selector: str) -> FakeLocator:
        if selector == "body":
            return FakeLocator(text=self.body)
        return self.locators.get(selector, FakeLocator(count=0))


class FakeLocatorService:
    def __init__(
        self,
        mapping: dict[str, FakeLocator],
        candidates: list[tuple[str, FakeLocator]] | None = None,
    ) -> None:
        self.mapping = mapping
        self.candidates = candidates

    async def locate(self, page: FakePage, element_name: str, element_type: ElementType) -> FakeLocator:
        locator = self.mapping.get(element_name)
        if locator is None:
            raise RuntimeError(f"missing {element_name}")
        return locator

    def build_locator(self, page: FakePage, element_name: str, element_type: ElementType) -> FakeLocator:
        return self.mapping.get(element_name, FakeLocator(count=0, visible=False))

    def candidate_locators(
        self, page: FakePage, element_name: str, element_type: ElementType
    ) -> list[tuple[str, FakeLocator]]:
        if self.candidates is not None:
            return self.candidates
        return [("fake", self.build_locator(page, element_name, element_type))]


class SlowLocateService(FakeLocatorService):
    async def locate(self, page: FakePage, element_name: str, element_type: ElementType) -> FakeLocator:
        await asyncio.sleep(2)
        return await super().locate(page, element_name, element_type)


def _step(
    step_id: str,
    action: ActionType,
    *,
    element_name: str = "Next",
    element_type: ElementType = ElementType.BUTTON,
    wait_condition: WaitConditionSpec | None = None,
) -> PlannedStep:
    return PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id=step_id,
        sequence=1,
        action=action,
        element_name=element_name,
        element_type=element_type,
        wait_condition=wait_condition,
    )


def _plan(step: PlannedStep) -> TaskPlan:
    return TaskPlan(
        plan_id="plan",
        sop_id="sop",
        goal_id="goal",
        entry_capability_id="auth_cap",
        capabilities=[
            PlannedCapability(
                capability_id="auth_cap",
                name="Auth",
                application_id="fixture",
                steps=[step],
            )
        ],
        created_at=datetime.now(UTC),
    )


def test_click_requires_declared_postcondition() -> None:
    dispatcher = ActionDispatcher()
    next_button = FakeLocator()
    password_field = FakeLocator(visible=True)
    dispatcher._locator_svc = FakeLocatorService({
        "Next": next_button,
        "Password": password_field,
    })
    dispatcher._postconditions = PostconditionEvaluator(dispatcher._locator_svc)
    page = FakePage()
    step = _step(
        "click_next",
        ActionType.CLICK,
    ).model_copy(update={
        "postcondition": WaitConditionSpec(
            type=WaitConditionType.ELEMENT_VISIBLE,
            element_name="Password",
            element_type=ElementType.TEXTBOX.value,
            timeout_seconds=0.1,
        )
    })

    result = asyncio.run(dispatcher.execute(page, step, {}, None))

    assert result.success is True
    assert next_button.clicked is True


def test_fill_precondition_does_not_skip_fill_action(tmp_path: Path) -> None:
    email = FakeLocator()
    page = FakePage()
    dispatcher = ActionDispatcher()
    dispatcher._locator_svc = FakeLocatorService({"Email Address textbox": email})
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="fill_email",
        sequence=1,
        action=ActionType.FILL,
        element_name="Email Address textbox",
        element_type=ElementType.TEXTBOX,
        value="test-user@example.invalid",
        wait_condition=WaitConditionSpec(
            type=WaitConditionType.ELEMENT_VISIBLE,
            element_name="Email Address textbox",
            element_type=ElementType.TEXTBOX.value,
            timeout_seconds=0.1,
        ),
    )

    result = asyncio.run(dispatcher.execute(page, step, {}, tmp_path))

    assert result.success is True
    assert email.text == "test-user@example.invalid"


def test_failed_fill_verification_is_controlled_postcondition_failure(tmp_path: Path) -> None:
    email = FakeLocator(input_raises=True)
    page = FakePage()
    dispatcher = ActionDispatcher()
    dispatcher._locator_svc = FakeLocatorService({"Email Address textbox": email})
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="fill_email",
        sequence=1,
        action=ActionType.FILL,
        element_name="Email Address textbox",
        element_type=ElementType.TEXTBOX,
        value="test-user@example.invalid",
    )

    result = asyncio.run(dispatcher.execute(page, step, {}, tmp_path))

    assert result.success is False
    assert "POSTCONDITION_NOT_MET" in (result.error_message or "")
    assert "test-user@example.invalid" not in (result.error_message or "")


def test_reconciliation_completes_satisfied_postcondition_without_reclick(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    manager._dispatcher.execute = AsyncMock(return_value=FakeResult("click_next"))
    page = FakePage(url="http://fixture/auth/password")
    step = _step(
        "click_next",
        ActionType.CLICK,
    ).model_copy(update={
        "postcondition": WaitConditionSpec(
            type=WaitConditionType.URL_CONTAINS,
            expected_value="/auth/password",
            timeout_seconds=0.1,
        )
    })

    state = asyncio.run(manager.start_run("run-1", _plan(step), page))

    assert state.status == RunStatus.COMPLETED
    assert state.step_progress["click_next"].status == StepStatus.COMPLETED
    assert manager._dispatcher.execute.await_count == 1


def test_reconciliation_probe_does_not_delay_initial_dispatch(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    manager._dispatcher.execute = AsyncMock(return_value=FakeResult("click_next"))
    page = FakePage(url="http://fixture/auth/login")
    step = _step(
        "click_next",
        ActionType.CLICK,
    ).model_copy(update={
        "postcondition": WaitConditionSpec(
            type=WaitConditionType.URL_CONTAINS,
            expected_value="/auth/password",
            timeout_seconds=30.0,
            poll_interval_seconds=1.0,
        )
    })

    started = time.perf_counter()
    state = asyncio.run(manager.start_run("run-1", _plan(step), page))
    elapsed = time.perf_counter() - started

    assert state.status == RunStatus.COMPLETED
    assert manager._dispatcher.execute.await_count == 1
    assert elapsed < 1.0


def test_reconciliation_element_probe_does_not_use_waiting_locator_resolution(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    slow_locator_service = SlowLocateService({}, candidates=[("fake", FakeLocator(count=0))])
    manager._postconditions = PostconditionEvaluator(slow_locator_service)
    manager._dispatcher.execute = AsyncMock(return_value=FakeResult("click_next"))
    page = FakePage(url="http://fixture/auth/login")
    step = _step(
        "click_next",
        ActionType.CLICK,
    ).model_copy(update={
        "postcondition": WaitConditionSpec(
            type=WaitConditionType.ELEMENT_VISIBLE,
            element_name="Password",
            element_type=ElementType.TEXTBOX.value,
            timeout_seconds=30.0,
            poll_interval_seconds=1.0,
        )
    })

    started = time.perf_counter()
    state = asyncio.run(manager.start_run("run-1", _plan(step), page))
    elapsed = time.perf_counter() - started

    assert state.status == RunStatus.COMPLETED
    assert manager._dispatcher.execute.await_count == 1
    assert elapsed < 1.0


class FakeResult:
    def __init__(self, step_id: str) -> None:
        self.step_id = step_id
        self.success = True
        self.value = None
        self.current_url = "http://fixture/auth/login"
        self.error_message = None
        self.locator_candidates = []
        self.locator_attempts = []


def test_auth_branch_invokes_classifier_and_business_branch_does_not() -> None:
    dispatcher = ActionDispatcher()
    page = FakePage(url="http://fixture/auth/manual", body="Complete authentication")
    auth_step = _step("classify", ActionType.AUTH_BRANCH, element_name="Auth", element_type=ElementType.PAGE)
    business_step = _step("business", ActionType.BRANCH, element_name="Branch", element_type=ElementType.PAGE)

    auth_result = asyncio.run(dispatcher.execute(page, auth_step, {}, None))
    business_result = asyncio.run(dispatcher.execute(page, business_step, {}, None))

    assert auth_result.value == AuthBranch.MANUAL_AUTH_REQUIRED.value
    assert business_result.value is None


def test_auth_branch_outcome_resolves_from_runtime_context(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    page = FakePage(url="http://fixture/auth/manual", body="Complete authentication")
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="classify",
        sequence=1,
        action=ActionType.AUTH_BRANCH,
        element_name="Auth",
        element_type=ElementType.PAGE,
        outcomes=[
            PlannedOutcome(
                outcome_id="manual",
                description="Manual auth",
                is_terminal=True,
                is_success=True,
                condition=ConditionSpec(
                    source_key="steps.classify.value",
                    operator=ConditionOperator.EQUALS,
                    expected_value=AuthBranch.MANUAL_AUTH_REQUIRED.value,
                ),
            )
        ],
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), page))

    assert state.status == RunStatus.COMPLETED
    assert state.branch_decisions["classify"] == "manual"


def test_hidden_postcondition_succeeds_with_zero_visible_matches() -> None:
    evaluator = PostconditionEvaluator(FakeLocatorService({
        "Email form": FakeLocator(count=1, visible=False),
    }))
    page = FakePage()

    result = asyncio.run(evaluator.evaluate(
        page,
        WaitConditionSpec(
            type=WaitConditionType.ELEMENT_HIDDEN,
            element_name="Email form",
            element_type=ElementType.TEXTBOX.value,
            timeout_seconds=0.1,
        ),
    ))

    assert result.satisfied is True


def test_hidden_postcondition_checks_label_and_placeholder_candidates() -> None:
    evaluator = PostconditionEvaluator(FakeLocatorService(
        {},
        candidates=[
            ("role=textbox[name='Email']", FakeLocator(count=0, visible=False)),
            ("label='Email'", FakeLocator(count=1, visible=True)),
        ],
    ))

    result = asyncio.run(evaluator.evaluate(
        FakePage(),
        WaitConditionSpec(
            type=WaitConditionType.ELEMENT_HIDDEN,
            element_name="Email",
            element_type=ElementType.TEXTBOX.value,
            timeout_seconds=0.1,
        ),
    ))

    assert result.satisfied is False
    assert result.signals["visible_count"] == 1


def test_hidden_postcondition_fails_when_placeholder_candidate_visible() -> None:
    evaluator = PostconditionEvaluator(FakeLocatorService(
        {},
        candidates=[
            ("role=textbox[name='Email']", FakeLocator(count=0, visible=False)),
            ("label='Email'", FakeLocator(count=0, visible=False)),
            ("placeholder~='Email'", FakeLocator(count=1, visible=True)),
        ],
    ))

    result = asyncio.run(evaluator.evaluate(
        FakePage(),
        WaitConditionSpec(
            type=WaitConditionType.ELEMENT_HIDDEN,
            element_name="Email",
            element_type=ElementType.TEXTBOX.value,
            timeout_seconds=0.1,
        ),
    ))

    assert result.satisfied is False


def test_hidden_postcondition_succeeds_when_all_candidates_absent() -> None:
    evaluator = PostconditionEvaluator(FakeLocatorService(
        {},
        candidates=[
            ("role=textbox[name='Email']", FakeLocator(count=0, visible=False)),
            ("label='Email'", FakeLocator(count=0, visible=False)),
            ("placeholder~='Email'", FakeLocator(count=0, visible=False)),
        ],
    ))

    result = asyncio.run(evaluator.evaluate(
        FakePage(),
        WaitConditionSpec(
            type=WaitConditionType.ELEMENT_HIDDEN,
            element_name="Email",
            element_type=ElementType.TEXTBOX.value,
            timeout_seconds=0.1,
        ),
    ))

    assert result.satisfied is True


def test_auth_classifier_detects_all_branch_values() -> None:
    cases = [
        (FakePage(url="http://fixture/auth/manual", body="Complete authentication"), AuthBranch.MANUAL_AUTH_REQUIRED),
        (FakePage(url="http://fixture/sso/redirect", body=""), AuthBranch.SSO_REDIRECT),
        (FakePage(url="http://fixture/home", body="Dashboard Log out"), AuthBranch.ALREADY_AUTHENTICATED),
        (FakePage(url="http://fixture/auth/error", body="Authentication failed"), AuthBranch.AUTHENTICATION_ERROR),
        (FakePage(url="http://fixture/unknown", body="Welcome"), AuthBranch.UNKNOWN_PAGE),
    ]
    password_only = FakePage()
    password_only.locators["input[type='password']"] = FakeLocator()
    cases.append((password_only, AuthBranch.PASSWORD_ONLY))

    username_password = FakePage()
    username_password.locators[
        "input[type='text'], input[type='email'], "
        "input[name*='user' i], input[id*='user' i], "
        "input[name*='email' i], input[id*='email' i], "
        "input[name*='login' i], input[id*='login' i]"
    ] = FakeLocator()
    username_password.locators["input[type='password']"] = FakeLocator()
    cases.append((username_password, AuthBranch.USERNAME_PASSWORD))

    for page, expected in cases:
        assert asyncio.run(classify_auth_branch(page)) == expected


def test_diagnostics_classify_and_redact_secret_looking_values() -> None:
    message = "POSTCONDITION_NOT_MET password=fake-password-for-test-only token=abc user@test.invalid"

    redacted = redact_text(message)

    assert classify_failure(redacted) == "POSTCONDITION_NOT_MET"
    assert "fake-password-for-test-only" not in redacted
    assert "abc" not in redacted
    assert "user@test.invalid" not in redacted


def test_secret_postcondition_values_are_not_persisted(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    locator_service = FakeLocatorService({
        "Next": FakeLocator(),
        "Password": FakeLocator(text="different-secret-value"),
    })
    manager._dispatcher._locator_svc = locator_service
    manager._dispatcher._postconditions = PostconditionEvaluator(locator_service)
    manager._postconditions = PostconditionEvaluator(locator_service)
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="click_next",
        sequence=1,
        action=ActionType.CLICK,
        element_name="Next",
        element_type=ElementType.BUTTON,
        postcondition=WaitConditionSpec(
            type=WaitConditionType.ELEMENT_VALUE_EQUALS,
            element_name="Password",
            element_type=ElementType.TEXTBOX.value,
            expected_value="fake-password-for-test-only",
            timeout_seconds=0.01,
            poll_interval_seconds=0.001,
        ),
        retry_policy=RetryPolicy(max_attempts=1),
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), FakePage()))

    assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
    artifact_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [run_dir / "events.jsonl", run_dir / "run_state.json", run_dir / "clarification_request.json"]
    )
    clarification = json.loads((run_dir / "clarification_request.json").read_text(encoding="utf-8"))
    assert clarification["failure_code"] == "POSTCONDITION_NOT_MET"
    assert "fake-password-for-test-only" not in artifact_text
    assert "different-secret-value" not in artifact_text


# ── Stage 2.1 — FILL retention always checked ────────────────────────────────

def test_fill_retention_required_even_with_explicit_url_postcondition(tmp_path: Path) -> None:
    """FILL must verify retention even when an explicit postcondition is declared.

    Scenario: the locator's input_value() returns '' (fill ignored) but a URL
    postcondition is already satisfied. The step must still fail with
    POSTCONDITION_NOT_MET because fill retention was not verified.
    """
    ignored_locator = FakeLocator(text="")  # fill() sets text but input_value() returns ""

    class _IgnoreFillLocator(FakeLocator):
        async def fill(self, value: str) -> None:
            pass  # intentionally does not retain the value

        async def input_value(self) -> str:
            return ""  # retention always fails

    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    manager._dispatcher._locator_svc = FakeLocatorService(
        {"Email": _IgnoreFillLocator()}
    )
    page = FakePage(url="http://fixture/auth/password")
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="fill_email",
        sequence=1,
        action=ActionType.FILL,
        element_name="Email",
        element_type=ElementType.TEXTBOX,
        value="test-user@example.invalid",
        postcondition=WaitConditionSpec(
            type=WaitConditionType.URL_CONTAINS,
            expected_value="/auth/password",
            timeout_seconds=0.01,
        ),
        retry_policy=RetryPolicy(max_attempts=1),
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), page))

    assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
    prog = state.step_progress["fill_email"]
    assert "POSTCONDITION_NOT_MET" in (prog.error_code or "")


def test_fill_retention_error_message_does_not_expose_secret(tmp_path: Path) -> None:
    class _IgnoreFillLocator(FakeLocator):
        async def fill(self, value: str) -> None:
            pass

        async def input_value(self) -> str:
            return ""

    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    manager._dispatcher._locator_svc = FakeLocatorService({"Password": _IgnoreFillLocator()})
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="fill_pass",
        sequence=1,
        action=ActionType.FILL,
        element_name="Password",
        element_type=ElementType.TEXTBOX,
        value="fake-password-for-test-only",
        retry_policy=RetryPolicy(max_attempts=1),
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), FakePage()))

    assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
    prog = state.step_progress["fill_pass"]
    assert "fake-password-for-test-only" not in (prog.error_message or "")
    clarification_text = (run_dir / "clarification_request.json").read_text(encoding="utf-8")
    assert "fake-password-for-test-only" not in clarification_text


# ── Stage 2.2 — Retry policy honours retryable_error_codes ──────────────────

class _CountingDispatcher:
    """Records how many times execute() is called."""

    def __init__(self, error_code: str) -> None:
        self.calls = 0
        self._error_code = error_code

    async def execute(self, page: object, step: object, context: object, run_dir: object, resolved_value: object) -> FakeResult:
        self.calls += 1
        return FakeResult.__new__(FakeResult)  # type: ignore[arg-type]

    def __new_result(self, step_id: str, success: bool, error: str) -> FakeResult:
        r = object.__new__(FakeResult)
        r.step_id = step_id  # type: ignore[attr-defined]
        r.success = success  # type: ignore[attr-defined]
        r.value = None  # type: ignore[attr-defined]
        r.current_url = "http://fixture"  # type: ignore[attr-defined]
        r.error_message = error  # type: ignore[attr-defined]
        r.locator_candidates = []  # type: ignore[attr-defined]
        return r


def _failing_step(
    step_id: str,
    *,
    max_attempts: int,
    retryable_error_codes: list[str],
    error_code: str,
) -> PlannedStep:
    """Build a FILL step that will fail with a synthesised error code."""
    return PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id=step_id,
        sequence=1,
        action=ActionType.CLICK,
        element_name="Missing Button",
        element_type=ElementType.BUTTON,
        retry_policy=RetryPolicy(
            max_attempts=max_attempts,
            delay_seconds=0.0,
            retryable_error_codes=retryable_error_codes,
        ),
    )


def test_retry_listed_error_code_retries(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)

    class _AlwaysFailLocator(FakeLocator):
        async def click(self) -> None:
            raise RuntimeError("Could not locate element 'Missing Button'")

    manager._dispatcher._locator_svc = FakeLocatorService({"Missing Button": _AlwaysFailLocator()})
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="click_btn",
        sequence=1,
        action=ActionType.CLICK,
        element_name="Missing Button",
        element_type=ElementType.BUTTON,
        retry_policy=RetryPolicy(
            max_attempts=3,
            delay_seconds=0.0,
            retryable_error_codes=["LOCATOR_NOT_FOUND"],
        ),
    )

    class _NotFoundLocatorService(FakeLocatorService):
        async def locate(self, page: object, element_name: str, element_type: ElementType) -> FakeLocator:
            raise RuntimeError(f"Could not locate element {element_name!r}")

    manager._dispatcher._locator_svc = _NotFoundLocatorService({})
    state = asyncio.run(manager.start_run("run-1", _plan(step), FakePage()))

    assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
    assert state.step_progress["click_btn"].attempt_count == 3


def test_retry_unlisted_error_code_does_not_retry(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)

    class _NotFoundLocatorService(FakeLocatorService):
        async def locate(self, page: object, element_name: str, element_type: ElementType) -> FakeLocator:
            raise RuntimeError(f"Could not locate element {element_name!r}")

    manager._dispatcher._locator_svc = _NotFoundLocatorService({})
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="click_btn",
        sequence=1,
        action=ActionType.CLICK,
        element_name="Missing Button",
        element_type=ElementType.BUTTON,
        retry_policy=RetryPolicy(
            max_attempts=3,
            delay_seconds=0.0,
            retryable_error_codes=["ACTION_TIMEOUT"],  # LOCATOR_NOT_FOUND not in list
        ),
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), FakePage()))

    assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
    assert state.step_progress["click_btn"].attempt_count == 1  # no retry


def test_locator_ambiguous_never_retries(tmp_path: Path) -> None:
    from sop_automation.runtime.locator_service import LocatorAmbiguityError

    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)

    class _AmbiguousLocatorService(FakeLocatorService):
        async def locate(self, page: object, element_name: str, element_type: ElementType) -> FakeLocator:
            raise LocatorAmbiguityError(element_name, "label", 2, ["Next 1", "Next 2"])

    manager._dispatcher._locator_svc = _AmbiguousLocatorService({})
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="click_btn",
        sequence=1,
        action=ActionType.CLICK,
        element_name="Next",
        element_type=ElementType.BUTTON,
        retry_policy=RetryPolicy(
            max_attempts=5,
            delay_seconds=0.0,
            retryable_error_codes=[],  # default set — but LOCATOR_AMBIGUOUS is always excluded
        ),
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), FakePage()))

    assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
    assert state.step_progress["click_btn"].attempt_count == 1


def test_default_retryable_set_used_when_retryable_error_codes_empty(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    call_count = {"n": 0}

    class _TransientLocatorService(FakeLocatorService):
        async def locate(self, page: object, element_name: str, element_type: ElementType) -> FakeLocator:
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RuntimeError("Element not visible yet")
            return FakeLocator()

    manager._dispatcher._locator_svc = _TransientLocatorService({})
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="click_btn",
        sequence=1,
        action=ActionType.CLICK,
        element_name="Next",
        element_type=ElementType.BUTTON,
        retry_policy=RetryPolicy(
            max_attempts=5,
            delay_seconds=0.0,
            retryable_error_codes=[],  # use default set
        ),
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), FakePage()))

    assert state.status == RunStatus.COMPLETED
    assert state.step_progress["click_btn"].attempt_count >= 3


# ── Stage 2.3 — Postcondition timing is bounded ──────────────────────────────

def test_evaluate_loop_does_not_use_waiting_locate_for_element_postcondition(tmp_path: Path) -> None:
    """evaluate() must use non-waiting locator resolution inside the polling loop.

    SlowLocateService.locate() sleeps 2 s. A postcondition with timeout_seconds=0.2
    must return well before 2 s because the loop uses candidate_locators() (non-waiting).
    """
    import time

    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    slow_locator_service = SlowLocateService({}, candidates=[("fake", FakeLocator(count=0))])
    # Action dispatch uses fast locator so the CLICK itself completes instantly.
    # Only postcondition evaluation uses the slow-locate service (which returns non-waiting
    # candidates via candidate_locators()), proving the evaluator never calls locate().
    manager._dispatcher._locator_svc = FakeLocatorService({"Next": FakeLocator()})
    manager._dispatcher._postconditions = PostconditionEvaluator(slow_locator_service)
    manager._postconditions = PostconditionEvaluator(slow_locator_service)

    step = _step("click_next", ActionType.CLICK).model_copy(update={
        "postcondition": WaitConditionSpec(
            type=WaitConditionType.ELEMENT_VISIBLE,
            element_name="Password",
            element_type=ElementType.TEXTBOX.value,
            timeout_seconds=0.2,
            poll_interval_seconds=0.05,
        ),
        "retry_policy": RetryPolicy(max_attempts=1),
    })

    started = time.perf_counter()
    state = asyncio.run(manager.start_run("run-1", _plan(step), FakePage()))
    elapsed = time.perf_counter() - started

    assert elapsed < 1.5, f"postcondition evaluate exceeded bounded timeout: {elapsed:.2f}s"
    assert state.status == RunStatus.WAITING_FOR_CLARIFICATION


# ── Stage 3 — AUTH_BRANCH contract ───────────────────────────────────────────

def test_auth_branch_without_outcomes_causes_branch_not_recognized(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    page = FakePage(url="http://fixture/auth/manual", body="Complete authentication")
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="classify",
        sequence=1,
        action=ActionType.AUTH_BRANCH,
        element_name="Auth",
        element_type=ElementType.PAGE,
        outcomes=[
            PlannedOutcome(
                outcome_id="up",
                description="Username+Password",
                is_terminal=True,
                is_success=True,
                condition=ConditionSpec(
                    source_key="steps.classify.value",
                    operator=ConditionOperator.EQUALS,
                    expected_value="USERNAME_PASSWORD",
                ),
            )
        ],
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), page))

    assert state.status == RunStatus.FAILED
    assert state.step_progress["classify"].error_code == "BRANCH_NOT_RECOGNIZED"


def test_authentication_error_outcome_cannot_produce_completed(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    page = FakePage(url="http://fixture/auth/error", body="Authentication failed")
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="classify",
        sequence=1,
        action=ActionType.AUTH_BRANCH,
        element_name="Auth",
        element_type=ElementType.PAGE,
        outcomes=[
            PlannedOutcome(
                outcome_id="auth_error",
                description="Auth error",
                is_terminal=True,
                is_success=False,
                condition=ConditionSpec(
                    source_key="steps.classify.value",
                    operator=ConditionOperator.EQUALS,
                    expected_value="AUTHENTICATION_ERROR",
                ),
            )
        ],
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), page))

    assert state.status == RunStatus.FAILED


def test_unknown_page_with_no_matching_outcome_fails_not_completes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    page = FakePage(url="http://fixture/unknown", body="")
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="classify",
        sequence=1,
        action=ActionType.AUTH_BRANCH,
        element_name="Auth",
        element_type=ElementType.PAGE,
        outcomes=[
            PlannedOutcome(
                outcome_id="up",
                description="Username+Password",
                is_terminal=True,
                is_success=True,
                condition=ConditionSpec(
                    source_key="steps.classify.value",
                    operator=ConditionOperator.EQUALS,
                    expected_value="USERNAME_PASSWORD",
                ),
            )
        ],
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), page))

    assert state.status == RunStatus.FAILED
    assert state.step_progress["classify"].error_code == "BRANCH_NOT_RECOGNIZED"


def test_sso_redirect_not_misclassified_as_manual_auth() -> None:
    page = FakePage(
        url="http://fixture/sso/redirect",
        body="single sign-on redirecting",
    )

    result = asyncio.run(classify_auth_branch(page))

    assert result == AuthBranch.SSO_REDIRECT


def test_email_type_username_plus_password_classified_as_username_password() -> None:
    page = FakePage(url="http://fixture/auth/login")
    page.locators["input[type='text'], input[type='email'], input[name*='user' i], input[id*='user' i], input[name*='email' i], input[id*='email' i], input[name*='login' i], input[id*='login' i]"] = FakeLocator()
    page.locators["input[type='password']"] = FakeLocator()

    result = asyncio.run(classify_auth_branch(page))

    assert result == AuthBranch.USERNAME_PASSWORD


def test_ordinary_branch_is_unaffected_by_auth_branch_not_recognized(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    page = FakePage()
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="business",
        sequence=1,
        action=ActionType.BRANCH,
        element_name="Branch",
        element_type=ElementType.PAGE,
        outcomes=[],
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), page))

    assert state.status == RunStatus.COMPLETED


# ── Stage 5 — Structured Diagnostics ─────────────────────────────────────────

class _StructuredErrorLocatorService(FakeLocatorService):
    """Raises LocatorError pre-populated with CandidateAttempt records."""

    def __init__(self, attempts: list[CandidateAttempt]) -> None:
        super().__init__({})
        self._attempts = attempts

    async def locate(
        self, page: object, element_name: str, element_type: ElementType
    ) -> FakeLocator:
        raise LocatorError(
            element_name,
            [a.strategy for a in self._attempts],
            [],
            self._attempts,
        )


def test_locator_error_attempts_flow_into_clarification_request(tmp_path: Path) -> None:
    """CandidateAttempt records from LocatorError must appear in clarification_request.json."""
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    attempts = [
        CandidateAttempt(strategy="role=button[name='Submit']", match_count=0, rejection_reason="NO_MATCH"),
        CandidateAttempt(strategy="label='Submit'", match_count=1, visible=False, rejection_reason="NOT_VISIBLE"),
    ]
    manager._dispatcher._locator_svc = _StructuredErrorLocatorService(attempts)
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="click_submit",
        sequence=1,
        action=ActionType.CLICK,
        element_name="Submit",
        element_type=ElementType.BUTTON,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), FakePage()))

    assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
    clarification = json.loads((run_dir / "clarification_request.json").read_text(encoding="utf-8"))
    assert "locator_attempts" in clarification
    assert len(clarification["locator_attempts"]) == 2
    attempt_strategies = [a["strategy"] for a in clarification["locator_attempts"]]
    assert "role=button[name='Submit']" in attempt_strategies
    assert clarification["locator_attempts"][0]["match_count"] == 0
    assert clarification["locator_attempts"][0]["rejection_reason"] == "NO_MATCH"
    assert clarification["locator_attempts"][1]["visible"] is False
    assert clarification["locator_attempts"][1]["rejection_reason"] == "NOT_VISIBLE"


def test_locator_attempts_have_no_secrets_in_clarification_artifact(tmp_path: Path) -> None:
    """Secret-like content in rejection reasons or strategy strings must be redacted."""
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    secret = "fake-password-for-test-only"
    attempts = [
        CandidateAttempt(
            strategy="role=textbox[name='Password']",
            match_count=1,
            visible=True,
            enabled=True,
            editable=True,
        ),
    ]
    manager._dispatcher._locator_svc = _StructuredErrorLocatorService(attempts)
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="fill_pass",
        sequence=1,
        action=ActionType.FILL,
        element_name="Password",
        element_type=ElementType.TEXTBOX,
        value=secret,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), FakePage()))

    assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
    artifact_text = (run_dir / "clarification_request.json").read_text(encoding="utf-8")
    assert secret not in artifact_text


def test_locator_attempts_match_count_and_state_flags_preserved(tmp_path: Path) -> None:
    """All CandidateAttempt fields are preserved faithfully in the clarification artifact."""
    run_dir = tmp_path / "run"
    manager = RunManager(run_dir)
    attempts = [
        CandidateAttempt(
            strategy="label='Username'",
            match_count=2,
            visible=True,
            enabled=True,
            editable=True,
            rejection_reason=None,  # found but timed out / ambiguous
        ),
    ]
    manager._dispatcher._locator_svc = _StructuredErrorLocatorService(attempts)
    step = PlannedStep(
        capability_id="auth_cap",
        capability_name="Authenticate",
        application_id="fixture",
        step_id="fill_user",
        sequence=1,
        action=ActionType.FILL,
        element_name="Username",
        element_type=ElementType.TEXTBOX,
        value="testuser",
        retry_policy=RetryPolicy(max_attempts=1),
    )

    state = asyncio.run(manager.start_run("run-1", _plan(step), FakePage()))

    assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
    clarification = json.loads((run_dir / "clarification_request.json").read_text(encoding="utf-8"))
    recorded = clarification["locator_attempts"][0]
    assert recorded["strategy"] == "label='Username'"
    assert recorded["match_count"] == 2
    assert recorded["visible"] is True
    assert recorded["enabled"] is True
    assert recorded["editable"] is True
    assert "rejection_reason" not in recorded  # None fields are omitted by to_dict()


def test_locator_service_attaches_structured_attempts_on_timeout() -> None:
    """LocatorService.locate() populates attempts on LocatorError when all strategies miss."""
    from sop_automation.runtime.locator_service import LocatorError, LocatorService

    class _ZeroPage:
        url = "http://fixture"

        def get_by_role(self, role: str, **kwargs: object) -> FakeLocator:
            return FakeLocator(count=0)

        def get_by_label(self, label: object, **kwargs: object) -> FakeLocator:
            return FakeLocator(count=0)

        def get_by_placeholder(self, placeholder: object, **kwargs: object) -> FakeLocator:
            return FakeLocator(count=0)

        def get_by_text(self, text: str, **kwargs: object) -> FakeLocator:
            return FakeLocator(count=0)

        async def query_selector_all(self, selector: str) -> list:
            return []

    svc = LocatorService(timeout_seconds=0.05, poll_seconds=0.01)
    page = _ZeroPage()
    exc: LocatorError | None = None
    try:
        asyncio.run(svc.locate(page, "Submit", ElementType.BUTTON))
    except LocatorError as e:
        exc = e

    assert exc is not None, "LocatorService.locate() should have raised LocatorError"
    assert len(exc.attempts) >= 1, "attempts list must be non-empty"
    for attempt in exc.attempts:
        assert isinstance(attempt, CandidateAttempt)
        assert attempt.match_count == 0
        assert attempt.rejection_reason == "NO_MATCH"
        d = attempt.to_dict()
        assert "strategy" in d
        assert "match_count" in d


def test_locator_service_attempts_record_visible_false_when_element_present_but_hidden() -> None:
    """When a locator matches elements but none are visible, attempts record NOT_VISIBLE."""
    from sop_automation.runtime.locator_service import LocatorError, LocatorService

    class _HiddenPage:
        url = "http://fixture"

        def get_by_role(self, role: str, **kwargs: object) -> FakeLocator:
            # Returns 1 match, but is_visible() → False
            return FakeLocator(count=1, visible=False)

        def get_by_label(self, label: object, **kwargs: object) -> FakeLocator:
            return FakeLocator(count=0)

        def get_by_placeholder(self, placeholder: object, **kwargs: object) -> FakeLocator:
            return FakeLocator(count=0)

        def get_by_text(self, text: str, **kwargs: object) -> FakeLocator:
            return FakeLocator(count=0)

        async def query_selector_all(self, selector: str) -> list:
            return []

    svc = LocatorService(timeout_seconds=0.05, poll_seconds=0.01)
    page = _HiddenPage()
    exc: LocatorError | None = None
    try:
        asyncio.run(svc.locate(page, "Submit", ElementType.BUTTON))
    except LocatorError as e:
        exc = e

    assert exc is not None
    # The role=button strategy should have matched 1 element but found it not visible
    role_attempts = [a for a in exc.attempts if "role" in a.strategy]
    assert role_attempts, "expected at least one role-strategy attempt"
    role_attempt = role_attempts[0]
    assert role_attempt.match_count == 1
    assert role_attempt.visible is False
    assert role_attempt.rejection_reason == "NOT_VISIBLE"
