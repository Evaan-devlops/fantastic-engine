"""Local authentication-route Playwright fixture tests — Stage 4 complete coverage."""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
from tests.fixtures.local_fixture_app import running_fixture_app

from sop_automation.models.common import ActionType, ElementType, RunStatus, StepStatus
from sop_automation.models.sop import (
    ConditionOperator,
    ConditionSpec,
    RetryPolicy,
    WaitConditionSpec,
    WaitConditionType,
)
from sop_automation.models.task import (
    PlannedCapability,
    PlannedOutcome,
    PlannedStep,
    TaskPlan,
)
from sop_automation.runtime.auth_classifier import AuthBranch, classify_auth_branch
from sop_automation.runtime.run_manager import RunManager

pytestmark = pytest.mark.playwright

EMAIL_VALUE = "test-user@example.invalid"
PASSWORD_VALUE = "fake-password-for-test-only"


def _auth_plan(base_url: str, path: str = "/auth/login") -> TaskPlan:
    return TaskPlan(
        plan_id="auth-route-plan",
        sop_id="auth-route-sop",
        goal_id="auth-route-goal",
        entry_capability_id="auth_cap",
        capabilities=[
            PlannedCapability(
                capability_id="auth_cap",
                name="Authenticate",
                application_id="fixture",
                steps=[
                    PlannedStep(
                        capability_id="auth_cap",
                        capability_name="Authenticate",
                        application_id="fixture",
                        step_id="open_auth",
                        sequence=1,
                        action=ActionType.OPEN,
                        element_name="Auth page",
                        element_type=ElementType.PAGE,
                        value=f"{base_url}{path}",
                    ),
                    PlannedStep(
                        capability_id="auth_cap",
                        capability_name="Authenticate",
                        application_id="fixture",
                        step_id="fill_email",
                        sequence=2,
                        action=ActionType.FILL,
                        element_name="Email Address textbox",
                        element_type=ElementType.TEXTBOX,
                        value=EMAIL_VALUE,
                    ),
                    PlannedStep(
                        capability_id="auth_cap",
                        capability_name="Authenticate",
                        application_id="fixture",
                        step_id="click_next",
                        sequence=3,
                        action=ActionType.CLICK,
                        element_name="Next",
                        element_type=ElementType.BUTTON,
                        postcondition=WaitConditionSpec(
                            type=WaitConditionType.ELEMENT_VISIBLE,
                            element_name="Password",
                            element_type=ElementType.TEXTBOX.value,
                            timeout_seconds=3.0,
                            poll_interval_seconds=0.1,
                        ),
                    ),
                    PlannedStep(
                        capability_id="auth_cap",
                        capability_name="Authenticate",
                        application_id="fixture",
                        step_id="classify_idp",
                        sequence=4,
                        action=ActionType.AUTH_BRANCH,
                        element_name="Identity provider page",
                        element_type=ElementType.PAGE,
                    ),
                ],
            )
        ],
        created_at=datetime.now(UTC),
    )


async def _run_auth_route(tmp_path: Path, base_url: str, path: str = "/auth/login") -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            manager = RunManager(tmp_path / "runs" / "auth-route")
            state = await manager.start_run("auth-route", _auth_plan(base_url, path), page)

            assert state.status == RunStatus.COMPLETED
            assert await page.locator("#password").is_visible()
            assert manager._context["steps"]["classify_idp"]["value"] == AuthBranch.PASSWORD_ONLY.value
        finally:
            await browser.close()


def test_auth_route_fill_click_postcondition_and_branch_classification(tmp_path: Path) -> None:
    with running_fixture_app() as app:
        asyncio.run(_run_auth_route(tmp_path, app.base_url))


def test_auth_route_delayed_identity_provider_transition(tmp_path: Path) -> None:
    with running_fixture_app() as app:
        asyncio.run(_run_auth_route(tmp_path, app.base_url, "/auth/login-delayed"))


async def _assert_next_button_enablement(base_url: str) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(f"{base_url}/auth/login")
            next_button = page.get_by_role("button", name="Next")
            assert await next_button.is_disabled()
            await page.get_by_role("textbox", name="Email address").fill(EMAIL_VALUE)
            await page.get_by_role("textbox", name="Email address").blur()
            assert await next_button.is_enabled()
        finally:
            await browser.close()


def test_auth_route_next_button_enables_after_fill_or_blur() -> None:
    with running_fixture_app() as app:
        asyncio.run(_assert_next_button_enablement(app.base_url))


async def _assert_auth_branch_fixture_pages(base_url: str) -> None:
    from playwright.async_api import async_playwright

    cases = [
        ("/auth/username-password", AuthBranch.USERNAME_PASSWORD),
        ("/auth/password-only", AuthBranch.PASSWORD_ONLY),
        ("/auth/sso/redirect", AuthBranch.SSO_REDIRECT),
        ("/auth/manual", AuthBranch.MANUAL_AUTH_REQUIRED),
        ("/auth/dashboard", AuthBranch.ALREADY_AUTHENTICATED),
        ("/auth/error", AuthBranch.AUTHENTICATION_ERROR),
    ]
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            for path, expected in cases:
                await page.goto(f"{base_url}{path}")
                assert await classify_auth_branch(page) == expected
        finally:
            await browser.close()


def test_auth_branch_classifier_fixture_pages() -> None:
    with running_fixture_app() as app:
        asyncio.run(_assert_auth_branch_fixture_pages(app.base_url))


# ── Stage 4: complete authentication vertical slice ──────────────────────────

def _full_auth_plan(base_url: str) -> TaskPlan:
    """Complete plan: email → Next → AUTH_BRANCH → password-only → fill pass → submit → MANUAL_AUTH."""
    auth_cap_steps = [
        PlannedStep(
            capability_id="auth_cap",
            capability_name="Authenticate",
            application_id="fixture",
            step_id="open_login",
            sequence=1,
            action=ActionType.OPEN,
            element_name="Login page",
            element_type=ElementType.PAGE,
            value=f"{base_url}/auth/login",
            postcondition=WaitConditionSpec(
                type=WaitConditionType.ELEMENT_VISIBLE,
                element_name="Email address",
                element_type=ElementType.TEXTBOX.value,
                timeout_seconds=5.0,
            ),
        ),
        PlannedStep(
            capability_id="auth_cap",
            capability_name="Authenticate",
            application_id="fixture",
            step_id="fill_email",
            sequence=2,
            action=ActionType.FILL,
            element_name="Email address",
            element_type=ElementType.TEXTBOX,
            value=EMAIL_VALUE,
            postcondition=WaitConditionSpec(
                type=WaitConditionType.ELEMENT_ENABLED,
                element_name="Next",
                element_type=ElementType.BUTTON.value,
                timeout_seconds=3.0,
            ),
        ),
        PlannedStep(
            capability_id="auth_cap",
            capability_name="Authenticate",
            application_id="fixture",
            step_id="click_next",
            sequence=3,
            action=ActionType.CLICK,
            element_name="Next",
            element_type=ElementType.BUTTON,
            postcondition=WaitConditionSpec(
                type=WaitConditionType.ELEMENT_VISIBLE,
                element_name="Password",
                element_type=ElementType.TEXTBOX.value,
                timeout_seconds=5.0,
                poll_interval_seconds=0.1,
            ),
            retry_policy=RetryPolicy(max_attempts=2, delay_seconds=0.5),
        ),
        PlannedStep(
            capability_id="auth_cap",
            capability_name="Authenticate",
            application_id="fixture",
            step_id="classify_idp",
            sequence=4,
            action=ActionType.AUTH_BRANCH,
            element_name="Identity provider page",
            element_type=ElementType.PAGE,
            outcomes=[
                PlannedOutcome(
                    outcome_id="password_only",
                    description="Password-only page",
                    is_terminal=False,
                    is_success=True,
                    next_capability_id="password_cap",
                    condition=ConditionSpec(
                        source_key="steps.classify_idp.value",
                        operator=ConditionOperator.EQUALS,
                        expected_value=AuthBranch.PASSWORD_ONLY.value,
                    ),
                ),
                PlannedOutcome(
                    outcome_id="username_password",
                    description="Username+Password page",
                    is_terminal=False,
                    is_success=True,
                    next_capability_id="password_cap",
                    condition=ConditionSpec(
                        source_key="steps.classify_idp.value",
                        operator=ConditionOperator.EQUALS,
                        expected_value=AuthBranch.USERNAME_PASSWORD.value,
                    ),
                ),
                PlannedOutcome(
                    outcome_id="safe_fallback",
                    description="Safe failure for any other page",
                    is_terminal=True,
                    is_success=False,
                    is_default=True,
                ),
            ],
        ),
    ]
    password_cap_steps = [
        PlannedStep(
            capability_id="password_cap",
            capability_name="Fill Password",
            application_id="fixture",
            step_id="fill_password",
            sequence=1,
            action=ActionType.FILL,
            element_name="Password",
            element_type=ElementType.TEXTBOX,
            value=PASSWORD_VALUE,
        ),
        PlannedStep(
            capability_id="password_cap",
            capability_name="Fill Password",
            application_id="fixture",
            step_id="submit_signin",
            sequence=2,
            action=ActionType.CLICK,
            element_name="Sign in",
            element_type=ElementType.BUTTON,
            postcondition=WaitConditionSpec(
                type=WaitConditionType.URL_CONTAINS,
                expected_value="/auth/manual",
                timeout_seconds=5.0,
                poll_interval_seconds=0.1,
            ),
            outcomes=[
                PlannedOutcome(
                    outcome_id="manual_auth",
                    description="Manual auth required",
                    is_terminal=False,
                    is_success=True,
                    next_capability_id="manual_auth_cap",
                ),
            ],
        ),
    ]
    manual_auth_cap_steps = [
        PlannedStep(
            capability_id="manual_auth_cap",
            capability_name="Manual Auth",
            application_id="fixture",
            step_id="wait_for_auth",
            sequence=1,
            action=ActionType.MANUAL_AUTH,
            element_name="Manual authentication",
            element_type=ElementType.PAGE,
            postcondition=WaitConditionSpec(
                type=WaitConditionType.URL_CONTAINS,
                expected_value="/auth/manual",
                timeout_seconds=10.0,
                poll_interval_seconds=0.2,
            ),
            outcomes=[
                PlannedOutcome(
                    outcome_id="auth_done",
                    description="Auth completed",
                    is_terminal=True,
                    is_success=True,
                ),
            ],
        ),
    ]
    return TaskPlan(
        plan_id="full-auth-plan",
        sop_id="auth-sop",
        goal_id="auth-goal",
        entry_capability_id="auth_cap",
        capabilities=[
            PlannedCapability(
                capability_id="auth_cap",
                name="Authenticate",
                application_id="fixture",
                steps=auth_cap_steps,
            ),
            PlannedCapability(
                capability_id="password_cap",
                name="Fill Password",
                application_id="fixture",
                steps=password_cap_steps,
            ),
            PlannedCapability(
                capability_id="manual_auth_cap",
                name="Manual Auth",
                application_id="fixture",
                steps=manual_auth_cap_steps,
            ),
        ],
        created_at=datetime.now(UTC),
    )


async def _run_full_auth_with_manual_signal(tmp_path: Path, base_url: str) -> tuple:
    """Run the full auth route; signal manual auth after WAITING_FOR_AUTH; return state + context."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            manager = RunManager(tmp_path / "runs" / "full-auth")
            plan = _full_auth_plan(base_url)

            run_task = asyncio.create_task(
                manager.start_run("full-auth", plan, page)
            )

            deadline = asyncio.get_event_loop().time() + 20.0
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(0.1)
                if manager._state and manager._state.status.value == "WAITING_FOR_AUTH":
                    break

            manager.signal_auth()
            state = await run_task
            return state, manager._context, page
        finally:
            await context.close()


def test_full_auth_route_email_next_password_manual_auth(tmp_path: Path) -> None:
    with running_fixture_app() as app:
        state, ctx, page = asyncio.run(_run_full_auth_with_manual_signal(tmp_path, app.base_url))

    assert state.status == RunStatus.COMPLETED
    assert state.step_progress["fill_email"].status == StepStatus.COMPLETED
    assert state.step_progress["click_next"].status == StepStatus.COMPLETED
    assert state.step_progress["fill_password"].status == StepStatus.COMPLETED
    assert "classify_idp" in state.branch_decisions


def test_full_auth_route_no_secret_in_persisted_artifacts(tmp_path: Path) -> None:
    with running_fixture_app() as app:
        asyncio.run(_run_full_auth_with_manual_signal(tmp_path, app.base_url))

    run_dir = tmp_path / "runs" / "full-auth"
    all_text: list[str] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.suffix in (".json", ".jsonl"):
            all_text.append(path.read_text(encoding="utf-8", errors="replace"))
    artifact_text = "\n".join(all_text)

    assert PASSWORD_VALUE not in artifact_text, "Password must not appear in any persisted artifact"


async def _assert_all_branch_fixture_routes(base_url: str, tmp_path: Path) -> dict[str, str]:
    """Run AUTH_BRANCH classifier via RunManager for all 7 fixture routes."""
    from playwright.async_api import async_playwright

    _FIXTURE_PATHS = {
        "/auth/username-password": AuthBranch.USERNAME_PASSWORD.value,
        "/auth/password-only": AuthBranch.PASSWORD_ONLY.value,
        "/auth/sso/redirect": AuthBranch.SSO_REDIRECT.value,
        "/auth/manual": AuthBranch.MANUAL_AUTH_REQUIRED.value,
        "/auth/dashboard": AuthBranch.ALREADY_AUTHENTICATED.value,
        "/auth/error": AuthBranch.AUTHENTICATION_ERROR.value,
    }

    results: dict[str, str] = {}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            for path, expected in _FIXTURE_PATHS.items():
                await page.goto(f"{base_url}{path}")
                branch = await classify_auth_branch(page)
                results[path] = branch.value
                assert branch.value == expected, f"{path}: expected {expected}, got {branch.value}"
        finally:
            await browser.close()
    return results


def test_all_branch_fixture_routes_via_classifier(tmp_path: Path) -> None:
    with running_fixture_app() as app:
        results = asyncio.run(_assert_all_branch_fixture_routes(app.base_url, tmp_path))
    assert len(results) == 6


async def _run_auth_error_plan(base_url: str, tmp_path: Path) -> RunStatus:
    """AUTH_BRANCH with auth-error → run must end as FAILED, not COMPLETED."""
    from playwright.async_api import async_playwright

    plan = TaskPlan(
        plan_id="error-plan",
        sop_id="sop",
        goal_id="goal",
        entry_capability_id="auth_cap",
        capabilities=[
            PlannedCapability(
                capability_id="auth_cap",
                name="Authenticate",
                application_id="fixture",
                steps=[
                    PlannedStep(
                        capability_id="auth_cap",
                        capability_name="Authenticate",
                        application_id="fixture",
                        step_id="open_error",
                        sequence=1,
                        action=ActionType.OPEN,
                        element_name="Error page",
                        element_type=ElementType.PAGE,
                        value=f"{base_url}/auth/error",
                    ),
                    PlannedStep(
                        capability_id="auth_cap",
                        capability_name="Authenticate",
                        application_id="fixture",
                        step_id="classify",
                        sequence=2,
                        action=ActionType.AUTH_BRANCH,
                        element_name="Page",
                        element_type=ElementType.PAGE,
                        outcomes=[
                            PlannedOutcome(
                                outcome_id="auth_error",
                                description="Auth failed",
                                is_terminal=True,
                                is_success=False,
                                condition=ConditionSpec(
                                    source_key="steps.classify.value",
                                    operator=ConditionOperator.EQUALS,
                                    expected_value=AuthBranch.AUTHENTICATION_ERROR.value,
                                ),
                            ),
                            PlannedOutcome(
                                outcome_id="fallback",
                                description="Fallback",
                                is_terminal=True,
                                is_success=False,
                                is_default=True,
                            ),
                        ],
                    ),
                ],
            )
        ],
        created_at=datetime.now(UTC),
    )

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            manager = RunManager(tmp_path / "runs" / "error-plan")
            state = await manager.start_run("error-run", plan, page)
            return state.status
        finally:
            await browser.close()


def test_authentication_error_route_ends_as_failed_not_completed(tmp_path: Path) -> None:
    with running_fixture_app() as app:
        status = asyncio.run(_run_auth_error_plan(app.base_url, tmp_path))
    assert status == RunStatus.FAILED


async def _run_delayed_auth_route(tmp_path: Path, base_url: str) -> RunStatus:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            manager = RunManager(tmp_path / "runs" / "delayed-auth")
            state = await manager.start_run("delayed-auth", _auth_plan(base_url, "/auth/login-delayed"), page)
            return state.status
        finally:
            await browser.close()


def test_auth_route_delayed_idp_rendering(tmp_path: Path) -> None:
    """The password postcondition must wait through the IDP rendering delay."""
    with running_fixture_app() as app:
        status = asyncio.run(_run_delayed_auth_route(tmp_path, app.base_url))
    assert status == RunStatus.COMPLETED


async def _assert_fill_and_next_not_repeated(base_url: str, tmp_path: Path) -> tuple[int, int]:
    """Resume after manual auth must not repeat completed fill_email and click_next steps."""
    from playwright.async_api import async_playwright

    email_fills = {"count": 0}
    next_clicks = {"count": 0}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            manager = RunManager(tmp_path / "runs" / "resume-test")
            plan = _full_auth_plan(base_url)

            original_execute = manager._dispatcher.execute

            async def _counting_execute(page_, step_, ctx_, run_dir_, resolved_):
                if step_.step_id == "fill_email":
                    email_fills["count"] += 1
                elif step_.step_id == "click_next":
                    next_clicks["count"] += 1
                return await original_execute(page_, step_, ctx_, run_dir_, resolved_)

            manager._dispatcher.execute = _counting_execute  # type: ignore[method-assign]

            run_task = asyncio.create_task(
                manager.start_run("resume-test", plan, page)
            )

            deadline = asyncio.get_event_loop().time() + 20.0
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(0.1)
                if manager._state and manager._state.status.value == "WAITING_FOR_AUTH":
                    break

            manager.signal_auth()
            await run_task
        finally:
            await context.close()

    return email_fills["count"], next_clicks["count"]


def test_resume_does_not_repeat_fill_email_or_click_next(tmp_path: Path) -> None:
    with running_fixture_app() as app:
        email_count, next_count = asyncio.run(
            _assert_fill_and_next_not_repeated(app.base_url, tmp_path)
        )
    assert email_count == 1, f"fill_email dispatched {email_count} times (expected 1)"
    assert next_count == 1, f"click_next dispatched {next_count} times (expected 1)"
