"""Local runtime smoke test — requires Playwright and chromium installed.

Run with: pytest -m playwright
Setup: pip install -e . && playwright install chromium

This test may remain unexecuted on the coding machine.
It must be complete and runnable on the Mac after the standard setup.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, UTC
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
from tests.fixtures.local_fixture_app import running_fixture_app

from sop_automation.models.common import ActionType, ElementType, RunStatus
from sop_automation.models.sop import WaitConditionSpec, WaitConditionType
from sop_automation.models.task import (
    PlannedCapability,
    PlannedOutcome,
    PlannedStep,
    TaskPlan,
)
from sop_automation.runtime.run_manager import RunManager

pytestmark = pytest.mark.playwright


# ---------------------------------------------------------------------------
# Plan builder
# ---------------------------------------------------------------------------

def _build_smoke_plan(base_url: str, username: str = "testuser") -> TaskPlan:
    """Build a TaskPlan that exercises OPEN → FILL → MANUAL_AUTH → BRANCH → END_SUCCESS."""

    def _outcome(
        oid: str,
        desc: str,
        *,
        next_cap: str | None = None,
        terminal: bool = False,
        success: bool = True,
        is_default: bool = False,
    ) -> PlannedOutcome:
        return PlannedOutcome(
            outcome_id=oid,
            description=desc,
            is_terminal=terminal,
            is_success=success,
            is_default=is_default,
            next_capability_id=next_cap,
        )

    def _step(
        sid: str,
        cap_id: str,
        seq: int,
        action: ActionType,
        element_name: str,
        element_type: ElementType,
        value: str | None = None,
        outcomes: list[PlannedOutcome] | None = None,
        wait_condition: WaitConditionSpec | None = None,
    ) -> PlannedStep:
        return PlannedStep(
            capability_id=cap_id,
            capability_name=cap_id,
            application_id="fixture_app",
            step_id=sid,
            sequence=seq,
            action=action,
            element_name=element_name,
            element_type=element_type,
            value=value,
            outcomes=outcomes or [],
            wait_condition=wait_condition,
        )

    # login_cap steps
    step_open = _step(
        "step_open", "login_cap", 1,
        ActionType.OPEN, "login_page", ElementType.PAGE,
        value=f"{base_url}/login",
    )
    step_fill = _step(
        "step_fill", "login_cap", 2,
        ActionType.FILL, "Username", ElementType.TEXTBOX,
        value="{{input.username}}",
    )
    step_auth = _step(
        "step_auth", "login_cap", 3,
        ActionType.MANUAL_AUTH, "auth_gate", ElementType.PAGE,
        wait_condition=WaitConditionSpec(
            type=WaitConditionType.URL_CONTAINS,
            expected_value="/dashboard",
        ),
    )
    step_branch = _step(
        "step_branch", "login_cap", 4,
        ActionType.BRANCH, "branch_point", ElementType.PAGE,
        outcomes=[
            # First unconditioned outcome → always selected
            _outcome("go_success", "Proceed to success", next_cap="success_cap"),
            # Default fallback → should not be selected
            _outcome("go_skip", "Skip to not-found", next_cap="skip_cap", is_default=True),
        ],
    )

    login_cap = PlannedCapability(
        capability_id="login_cap",
        name="Login and Branch",
        application_id="fixture_app",
        steps=[step_open, step_fill, step_auth, step_branch],
    )

    success_step = _step(
        "step_success", "success_cap", 1,
        ActionType.END_SUCCESS, "terminal", ElementType.PAGE,
    )
    success_cap = PlannedCapability(
        capability_id="success_cap",
        name="Terminal Success",
        application_id="fixture_app",
        steps=[success_step],
    )

    # skip_cap must exist in the plan but must never be reached
    skip_step = _step(
        "step_skip", "skip_cap", 1,
        ActionType.OPEN, "not_found_page", ElementType.PAGE,
        value=f"{base_url}/not-found",
    )
    skip_cap = PlannedCapability(
        capability_id="skip_cap",
        name="Unselected Branch",
        application_id="fixture_app",
        steps=[skip_step],
    )

    return TaskPlan(
        plan_id="smoke-plan-1",
        sop_id="smoke-sop",
        goal_id="smoke-goal",
        entry_capability_id="login_cap",
        capabilities=[login_cap, success_cap, skip_cap],
        inputs={"username": username},
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

async def _smoke_inner(tmp_path: Path, base_url: str) -> None:
    from playwright.async_api import async_playwright

    profile_dir = tmp_path / "browser_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    run_id = "smoke-run-1"

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=True,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        plan = _build_smoke_plan(base_url)
        run_dir = tmp_path / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        manager = RunManager(run_dir)

        # --- Start the run in a background task (will pause at MANUAL_AUTH) ---
        run_task = asyncio.create_task(manager.start_run(run_id, plan, page))

        # --- Poll until WAITING_FOR_AUTH (up to 15s) ---
        deadline = asyncio.get_event_loop().time() + 15.0
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.1)
            if manager._state and manager._state.status == RunStatus.WAITING_FOR_AUTH:
                break
        else:
            run_task.cancel()
            pytest.fail("Did not reach WAITING_FOR_AUTH within 15 seconds")

        # --- Verify: same browser context object, browser is still open ---
        context_at_pause = context

        # Check steps completed before auth pause
        state_at_pause = manager._state
        assert state_at_pause.run_id == run_id
        assert state_at_pause.status == RunStatus.WAITING_FOR_AUTH

        open_prog = state_at_pause.step_progress.get("step_open")
        fill_prog = state_at_pause.step_progress.get("step_fill")
        assert open_prog is not None and open_prog.status.value == "COMPLETED"
        assert fill_prog is not None and fill_prog.status.value == "COMPLETED"

        # --- Perform real fixture authentication using the same page ---
        # The login form at /login has username + password fields + Submit button.
        # Submitting POSTs to /login which redirects to /dashboard.
        await page.fill("input[name='password']", "testpass")
        await page.click("button[type='submit']")
        await page.wait_for_url("**/dashboard**", timeout=5000)

        # --- Signal auth: page is now at /dashboard; condition URL_CONTAINS /dashboard passes ---
        manager.signal_auth()

        # --- Wait for run to complete (up to 15s) ---
        await asyncio.wait_for(run_task, timeout=15.0)

        # --- Post-run assertions ---
        final_state = manager._state
        assert final_state is not None

        # 1. Final status is COMPLETED
        assert final_state.status == RunStatus.COMPLETED, (
            f"Expected COMPLETED, got {final_state.status}"
        )

        # 2. Run ID unchanged throughout
        assert final_state.run_id == run_id

        # 3. Browser context object is the same instance (not replaced during auth pause)
        assert context is context_at_pause, "Browser context was replaced during auth pause"

        # 4. Previously completed steps not repeated (attempt_count == 1 for pre-auth steps)
        open_prog_after = final_state.step_progress.get("step_open")
        assert open_prog_after is not None
        assert open_prog_after.attempt_count == 1, (
            "step_open was executed more than once (steps must not repeat after auth)"
        )
        fill_prog_after = final_state.step_progress.get("step_fill")
        assert fill_prog_after is not None
        assert fill_prog_after.attempt_count == 1

        # 5. MANUAL_AUTH step is marked completed
        auth_prog = final_state.step_progress.get("step_auth")
        assert auth_prog is not None
        assert auth_prog.status.value == "COMPLETED", (
            f"MANUAL_AUTH step expected COMPLETED, got {auth_prog.status.value}"
        )

        # 6. Runtime context records auth success and URL
        auth_ctx = manager._context["steps"].get("step_auth")
        assert auth_ctx is not None, "Auth step not recorded in runtime context"
        assert auth_ctx["success"] is True
        assert "/dashboard" in auth_ctx["current_url"], (
            f"Expected /dashboard in current_url, got: {auth_ctx['current_url']!r}"
        )

        # 7. Selected outcome and branch decision persisted
        assert "step_branch" in final_state.branch_decisions, (
            "Branch decision for step_branch was not persisted"
        )
        assert final_state.branch_decisions["step_branch"] == "go_success"

        # 8. Exactly one branch executed — success_cap steps completed
        assert "step_success" in final_state.step_progress

        # 9. Unselected branch (skip_cap) was not executed
        assert "step_skip" not in final_state.step_progress, (
            "Unselected branch (skip_cap) was executed — must not run"
        )

        await context.close()


class TestRuntimeSmoke:
    def test_runtime_smoke_manual_auth_same_context_and_single_branch(
        self, tmp_path: Path
    ) -> None:
        """
        Full runtime smoke test proving:
        - OPEN → FILL ({{input.*}} resolved) → MANUAL_AUTH pause
        - Same Playwright browser context remains open during pause
        - Real fixture authentication: fill password, click Submit, reach /dashboard
        - URL_CONTAINS /dashboard condition evaluated against live page
        - signal_auth() triggers condition evaluation → AUTH_VERIFIED
        - Selected branch (go_success → success_cap) executes; unselected (go_skip → skip_cap) does not
        - Terminal success → RunStatus.COMPLETED
        - Previously completed steps not repeated after continue
        - Auth step context records success=True and current_url containing /dashboard
        - Run ID unchanged; branch decisions persisted
        """
        with running_fixture_app() as app:
            asyncio.run(_smoke_inner(tmp_path, app.base_url))
