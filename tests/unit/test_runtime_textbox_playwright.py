"""Synthetic runtime textbox reproducer for Playwright."""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
from tests.fixtures.local_fixture_app import running_fixture_app

from sop_automation.models.common import ActionType, ElementType, RunStatus
from sop_automation.models.task import PlannedCapability, PlannedStep, TaskPlan
from sop_automation.runtime.run_manager import RunManager

pytestmark = pytest.mark.playwright


FILL_VALUE = "test-user@example.invalid"


def _plan(base_url: str, path: str = "/email-login") -> TaskPlan:
    return TaskPlan(
        plan_id="textbox-runtime-plan",
        sop_id="textbox-runtime-sop",
        goal_id="textbox-runtime-goal",
        entry_capability_id="login_cap",
        capabilities=[
            PlannedCapability(
                capability_id="login_cap",
                name="Login",
                application_id="fixture_app",
                steps=[
                    PlannedStep(
                        capability_id="login_cap",
                        capability_name="Login",
                        application_id="fixture_app",
                        step_id="open_login",
                        sequence=1,
                        action=ActionType.OPEN,
                        element_name="Login page",
                        element_type=ElementType.PAGE,
                        value=f"{base_url}{path}",
                    ),
                    PlannedStep(
                        capability_id="login_cap",
                        capability_name="Login",
                        application_id="fixture_app",
                        step_id="fill_email",
                        sequence=2,
                        action=ActionType.FILL,
                        element_name="Email Address textbox",
                        element_type=ElementType.TEXTBOX,
                        value=FILL_VALUE,
                    ),
                ],
            )
        ],
        inputs={},
        created_at=datetime.now(UTC),
    )


async def _run_textbox_fill(tmp_path: Path, base_url: str, path: str = "/email-login") -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            run_dir = tmp_path / "runs" / "textbox-runtime-run"
            manager = RunManager(run_dir)
            state = await manager.start_run("textbox-runtime-run", _plan(base_url, path), page)

            assert state.status == RunStatus.COMPLETED
            assert await page.locator("#email").input_value() == FILL_VALUE
        finally:
            await browser.close()


def test_runtime_fill_resolves_semantic_textbox_name(tmp_path: Path) -> None:
    with running_fixture_app() as app:
        asyncio.run(_run_textbox_fill(tmp_path, app.base_url))


def test_runtime_fill_waits_for_delayed_textbox(tmp_path: Path) -> None:
    with running_fixture_app() as app:
        asyncio.run(_run_textbox_fill(tmp_path, app.base_url, "/email-login-delayed"))


def test_runtime_fill_uses_placeholder_from_semantic_name(tmp_path: Path) -> None:
    with running_fixture_app() as app:
        asyncio.run(_run_textbox_fill(tmp_path, app.base_url, "/email-login-placeholder"))


def test_runtime_fill_ignores_hidden_duplicate_match(tmp_path: Path) -> None:
    with running_fixture_app() as app:
        asyncio.run(_run_textbox_fill(tmp_path, app.base_url, "/email-login-hidden-duplicate"))


async def _run_ambiguous_textbox(tmp_path: Path, base_url: str) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            run_dir = tmp_path / "runs" / "textbox-ambiguous-run"
            manager = RunManager(run_dir)
            state = await manager.start_run(
                "textbox-ambiguous-run",
                _plan(base_url, "/email-login-ambiguous"),
                page,
            )

            assert state.status == RunStatus.WAITING_FOR_CLARIFICATION
            progress = state.step_progress["fill_email"]
            assert progress.error_message is not None
            assert "Ambiguous locator" in progress.error_message
            assert FILL_VALUE not in progress.error_message
        finally:
            await browser.close()


def test_runtime_fill_reports_visible_ambiguity(tmp_path: Path) -> None:
    with running_fixture_app() as app:
        asyncio.run(_run_ambiguous_textbox(tmp_path, app.base_url))
