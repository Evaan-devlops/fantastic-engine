"""Canonical pre-action page preparation service."""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from sop_automation.errors import PagePreparationError
from sop_automation.models.sop import WaitConditionSpec, WaitConditionType

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page


class PagePreparationService:
    """Applies structured wait conditions before executing a browser action."""

    async def prepare(
        self,
        page: "Page",
        wait_spec: WaitConditionSpec | None,
        locator: "Locator | None" = None,
    ) -> None:
        await self._ensure_page_ready(page)
        if wait_spec:
            await self._apply_wait(page, wait_spec, locator)

    async def ensure_actionable(
        self,
        locator: "Locator",
        timeout_ms: int = 10000,
    ) -> None:
        """Ensure element is visible and enabled before interaction."""
        try:
            await locator.wait_for(state="attached", timeout=timeout_ms)
        except Exception as exc:
            raise PagePreparationError(f"Element was not attached within timeout: {exc}") from exc

        await locator.wait_for(state="visible", timeout=timeout_ms)
        try:
            await locator.scroll_into_view_if_needed(timeout=timeout_ms)
        except Exception:
            pass

        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if await locator.is_enabled():
                return
            await asyncio.sleep(0.1)
        raise PagePreparationError("Element did not become enabled within timeout")

    async def ensure_editable(
        self,
        locator: "Locator",
        timeout_ms: int = 10000,
    ) -> None:
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            try:
                if await locator.is_editable():
                    return
            except Exception:
                pass
            await asyncio.sleep(0.1)
        raise PagePreparationError("Element did not become editable within timeout")

    async def _ensure_page_ready(self, page: "Page") -> None:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception as exc:
            raise PagePreparationError(f"Page DOM load timed out: {exc}") from exc

    async def _apply_wait(
        self,
        page: "Page",
        spec: WaitConditionSpec,
        locator: "Locator | None",
    ) -> None:
        timeout_ms = int(spec.timeout_seconds * 1000)
        poll_s = spec.poll_interval_seconds
        t = spec.type

        if t == WaitConditionType.PAGE_DOM_READY:
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
            except Exception as exc:
                raise PagePreparationError(f"PAGE_DOM_READY timed out: {exc}") from exc

        elif t == WaitConditionType.URL_EQUALS:
            await self._poll(
                lambda: page.url == spec.expected_value,
                timeout_ms, poll_s, "URL_EQUALS",
            )

        elif t == WaitConditionType.URL_CONTAINS:
            await self._poll(
                lambda: bool(spec.expected_value) and spec.expected_value in page.url,
                timeout_ms, poll_s, "URL_CONTAINS",
            )

        elif t == WaitConditionType.ELEMENT_VISIBLE:
            if locator:
                try:
                    await locator.wait_for(state="visible", timeout=timeout_ms)
                except Exception as exc:
                    raise PagePreparationError(f"ELEMENT_VISIBLE timed out: {exc}") from exc

        elif t == WaitConditionType.ELEMENT_HIDDEN:
            if locator:
                try:
                    await locator.wait_for(state="hidden", timeout=timeout_ms)
                except Exception as exc:
                    raise PagePreparationError(f"ELEMENT_HIDDEN timed out: {exc}") from exc

        elif t == WaitConditionType.ELEMENT_ENABLED:
            if locator:
                deadline = time.monotonic() + spec.timeout_seconds
                while time.monotonic() < deadline:
                    if await locator.is_enabled():
                        return
                    await asyncio.sleep(poll_s)
                raise PagePreparationError("ELEMENT_ENABLED timed out")

        elif t == WaitConditionType.ELEMENT_TEXT_EQUALS:
            if locator:
                async def _check_text_eq() -> bool:
                    try:
                        return await locator.inner_text() == spec.expected_value
                    except Exception:
                        return False
                await self._poll_async(_check_text_eq, timeout_ms, poll_s, "ELEMENT_TEXT_EQUALS")

        elif t == WaitConditionType.ELEMENT_TEXT_CONTAINS:
            if locator:
                async def _check_text_contains() -> bool:
                    try:
                        text = await locator.inner_text()
                        return bool(spec.expected_value) and spec.expected_value in text
                    except Exception:
                        return False
                await self._poll_async(_check_text_contains, timeout_ms, poll_s, "ELEMENT_TEXT_CONTAINS")

        elif t == WaitConditionType.ELEMENT_VALUE_EQUALS:
            if locator:
                async def _check_val_eq() -> bool:
                    try:
                        return await locator.input_value() == spec.expected_value
                    except Exception:
                        return False
                await self._poll_async(_check_val_eq, timeout_ms, poll_s, "ELEMENT_VALUE_EQUALS")

        elif t == WaitConditionType.FIXED_DELAY:
            delay = float(spec.expected_value) if spec.expected_value else spec.timeout_seconds
            await asyncio.sleep(delay)

        elif t == WaitConditionType.DOWNLOAD_COMPLETED:
            raise PagePreparationError(
                "DOWNLOAD_COMPLETED wait is not supported in POC; "
                "use DOWNLOAD action instead."
            )

    async def _poll(
        self,
        condition: object,
        timeout_ms: int,
        poll_s: float,
        label: str,
    ) -> None:
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            try:
                if condition():  # type: ignore[operator]
                    return
            except Exception:
                pass
            await asyncio.sleep(poll_s)
        raise PagePreparationError(f"{label} condition not met within {timeout_ms}ms")

    async def _poll_async(
        self,
        condition: object,
        timeout_ms: int,
        poll_s: float,
        label: str,
    ) -> None:
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            try:
                if await condition():  # type: ignore[operator]
                    return
            except Exception:
                pass
            await asyncio.sleep(poll_s)
        raise PagePreparationError(f"{label} condition not met within {timeout_ms}ms")


async def wait_for_url_stable(page: "Page", poll_s: float = 0.5, stable_polls: int = 2) -> None:
    """After navigation, wait until page.url is stable for `stable_polls` consecutive checks."""
    last_url = page.url
    consecutive = 0
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        await asyncio.sleep(poll_s)
        current = page.url
        if current == last_url:
            consecutive += 1
            if consecutive >= stable_polls:
                return
        else:
            last_url = current
            consecutive = 0
