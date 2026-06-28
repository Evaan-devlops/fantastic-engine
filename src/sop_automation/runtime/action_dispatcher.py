"""Playwright action dispatcher — one handler per ActionType."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from sop_automation.models.common import ActionType, ElementType
from sop_automation.models.runtime import StepResult
from sop_automation.models.sop import WaitConditionSpec
from sop_automation.models.task import PlannedStep
from sop_automation.runtime.condition_evaluator import ConditionEvaluator
from sop_automation.runtime.locator_service import LocatorError, LocatorService
from sop_automation.runtime.page_preparation import PagePreparationService

if TYPE_CHECKING:
    from playwright.async_api import Page


_EVALUATOR = ConditionEvaluator()


async def _get_visible_candidates(page: "Page") -> list[str]:
    """Return text labels of visible interactive elements for clarification."""
    try:
        elements = await page.query_selector_all(
            "button, a, input, select, textarea, [role='button'], [role='link']"
        )
        labels: list[str] = []
        for el in elements[:20]:
            try:
                if not await el.is_visible():
                    continue
                text = (await el.inner_text()).strip()
                if not text:
                    text = await el.get_attribute("aria-label") or await el.get_attribute("placeholder") or ""
                    text = text.strip()
                if text:
                    labels.append(text)
            except Exception:
                continue
        return labels
    except Exception:
        return []


class ActionDispatcher:
    """Dispatches a PlannedStep to the correct Playwright handler."""

    def __init__(self) -> None:
        self._locator_svc = LocatorService()
        self._page_prep = PagePreparationService()

    async def execute(
        self,
        page: "Page",
        step: PlannedStep,
        context: dict[str, Any],
        run_dir: object = None,
        resolved_value: str | None = None,
    ) -> StepResult:
        action = step.action
        value = resolved_value if resolved_value is not None else step.value
        try:
            if action == ActionType.OPEN:
                return await self._open(page, step, value)
            if action == ActionType.CLICK:
                return await self._click(page, step)
            if action == ActionType.FILL:
                return await self._fill(page, step, value)
            if action == ActionType.PRESS:
                return await self._press(page, step, value)
            if action == ActionType.SELECT:
                return await self._select(page, step, value)
            if action == ActionType.CHECK:
                return await self._check(page, step)
            if action == ActionType.UNCHECK:
                return await self._uncheck(page, step)
            if action == ActionType.UPLOAD:
                return await self._upload(page, step, value)
            if action == ActionType.DOWNLOAD:
                return await self._download(page, step, run_dir)
            if action == ActionType.COPY:
                return await self._copy(page, step, context)
            if action == ActionType.WAIT:
                return await self._wait(page, step)
            if action == ActionType.VERIFY:
                return await self._verify(page, step, context)
            if action == ActionType.HANDLE_POPUP:
                return await self._handle_popup(page, step)
            if action == ActionType.MANUAL_AUTH:
                return StepResult(
                    step_id=step.step_id,
                    success=False,
                    error_message="MANUAL_AUTH_REQUIRED",
                    current_url=page.url,
                )
            if action == ActionType.BRANCH:
                return StepResult(step_id=step.step_id, success=True, current_url=page.url)
            if action == ActionType.END_SUCCESS:
                return StepResult(
                    step_id=step.step_id,
                    success=True,
                    value="terminal_success",
                    current_url=page.url,
                )
            if action == ActionType.END_FAILURE:
                return StepResult(
                    step_id=step.step_id,
                    success=False,
                    error_message="END_FAILURE",
                    current_url=page.url,
                )
            if action == ActionType.DEFERRED:
                return StepResult(
                    step_id=step.step_id,
                    success=False,
                    error_message="DEFERRED_CAPABILITY",
                    current_url=page.url,
                )
            return StepResult(
                step_id=step.step_id,
                success=False,
                error_message=f"Unknown action: {action}",
            )
        except LocatorError as exc:
            candidates = await _get_visible_candidates(page)
            return StepResult(
                step_id=step.step_id,
                success=False,
                error_message=str(exc),
                current_url=page.url,
                locator_candidates=candidates,
            )
        except Exception as exc:
            return StepResult(
                step_id=step.step_id,
                success=False,
                error_message=str(exc),
                current_url=page.url,
            )

    async def _open(self, page: "Page", step: PlannedStep, value: str | None) -> StepResult:
        url = value or step.value or ""
        await page.goto(url)
        from sop_automation.runtime.page_preparation import wait_for_url_stable
        await wait_for_url_stable(page)
        await self._page_prep.prepare(page, step.wait_condition)
        return StepResult(step_id=step.step_id, success=True, current_url=page.url)

    async def _click(self, page: "Page", step: PlannedStep) -> StepResult:
        locator = await self._locator_svc.locate(page, step.element_name, step.element_type)
        await self._page_prep.ensure_actionable(locator)
        await self._page_prep.prepare(page, step.wait_condition, locator)
        await locator.click()
        return StepResult(step_id=step.step_id, success=True, current_url=page.url)

    async def _fill(self, page: "Page", step: PlannedStep, value: str | None) -> StepResult:
        locator = await self._locator_svc.locate(page, step.element_name, step.element_type)
        await self._page_prep.ensure_actionable(locator)
        await self._page_prep.prepare(page, step.wait_condition, locator)
        await locator.fill(value or "")
        return StepResult(step_id=step.step_id, success=True, current_url=page.url)

    async def _press(self, page: "Page", step: PlannedStep, value: str | None) -> StepResult:
        locator = await self._locator_svc.locate(page, step.element_name, step.element_type)
        await self._page_prep.ensure_actionable(locator)
        await self._page_prep.prepare(page, step.wait_condition, locator)
        await locator.press(value or "Enter")
        return StepResult(step_id=step.step_id, success=True, current_url=page.url)

    async def _select(self, page: "Page", step: PlannedStep, value: str | None) -> StepResult:
        locator = await self._locator_svc.locate(page, step.element_name, step.element_type)
        await self._page_prep.ensure_actionable(locator)
        await self._page_prep.prepare(page, step.wait_condition, locator)
        await locator.select_option(value or "")
        return StepResult(step_id=step.step_id, success=True, current_url=page.url)

    async def _check(self, page: "Page", step: PlannedStep) -> StepResult:
        locator = await self._locator_svc.locate(page, step.element_name, step.element_type)
        await self._page_prep.ensure_actionable(locator)
        await self._page_prep.prepare(page, step.wait_condition, locator)
        await locator.check()
        return StepResult(step_id=step.step_id, success=True, current_url=page.url)

    async def _uncheck(self, page: "Page", step: PlannedStep) -> StepResult:
        locator = await self._locator_svc.locate(page, step.element_name, step.element_type)
        await self._page_prep.ensure_actionable(locator)
        await self._page_prep.prepare(page, step.wait_condition, locator)
        await locator.uncheck()
        return StepResult(step_id=step.step_id, success=True, current_url=page.url)

    async def _upload(self, page: "Page", step: PlannedStep, value: str | None) -> StepResult:
        locator = await self._locator_svc.locate(page, step.element_name, step.element_type)
        await self._page_prep.prepare(page, step.wait_condition, locator)
        await locator.set_input_files(value or "")
        return StepResult(step_id=step.step_id, success=True, current_url=page.url)

    async def _download(self, page: "Page", step: PlannedStep, run_dir: object) -> StepResult:
        locator = await self._locator_svc.locate(page, step.element_name, step.element_type)
        async with page.expect_download() as dl_info:
            await locator.click()
        download = await dl_info.value
        save_path = None
        if run_dir is not None:
            from pathlib import Path
            downloads_dir = Path(str(run_dir)) / "downloads"
            downloads_dir.mkdir(parents=True, exist_ok=True)
            save_path = str(downloads_dir / download.suggested_filename)
            await download.save_as(save_path)
        return StepResult(step_id=step.step_id, success=True, value=save_path, current_url=page.url)

    async def _copy(
        self, page: "Page", step: PlannedStep, context: dict[str, Any]
    ) -> StepResult:
        locator = await self._locator_svc.locate(page, step.element_name, step.element_type)
        await self._page_prep.prepare(page, step.wait_condition, locator)
        text = await locator.inner_text()
        context.setdefault("steps", {}).setdefault(step.step_id, {})["value"] = text
        return StepResult(step_id=step.step_id, success=True, value=text, current_url=page.url)

    async def _wait(self, page: "Page", step: PlannedStep) -> StepResult:
        await self._page_prep.prepare(page, step.wait_condition)
        return StepResult(step_id=step.step_id, success=True, current_url=page.url)

    async def _verify(
        self, page: "Page", step: PlannedStep, context: dict[str, Any]
    ) -> StepResult:
        for outcome in step.outcomes:
            if outcome.condition is not None:
                if _EVALUATOR.evaluate(outcome.condition, context):
                    if outcome.is_success:
                        return StepResult(step_id=step.step_id, success=True, current_url=page.url)
                    else:
                        return StepResult(
                            step_id=step.step_id,
                            success=False,
                            error_message=f"VERIFY outcome {outcome.outcome_id!r} failed",
                            current_url=page.url,
                        )
            elif outcome.is_default:
                if outcome.is_success:
                    return StepResult(step_id=step.step_id, success=True, current_url=page.url)
                else:
                    return StepResult(
                        step_id=step.step_id,
                        success=False,
                        error_message=f"VERIFY default outcome {outcome.outcome_id!r} failed",
                        current_url=page.url,
                    )
        return StepResult(
            step_id=step.step_id,
            success=False,
            error_message="VERIFY: no matching outcome condition and no default",
            current_url=page.url,
        )

    async def _handle_popup(self, page: "Page", step: PlannedStep) -> StepResult:
        locator = await self._locator_svc.locate(page, step.element_name, step.element_type)
        async with page.expect_popup() as popup_info:
            await locator.click()
        popup = await popup_info.value
        await popup.wait_for_load_state("domcontentloaded")
        return StepResult(step_id=step.step_id, success=True, current_url=popup.url)
