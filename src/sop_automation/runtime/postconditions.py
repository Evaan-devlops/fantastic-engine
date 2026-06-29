"""Generic post-action browser state evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field
import asyncio
import time
from typing import TYPE_CHECKING

from sop_automation.models.common import ElementType
from sop_automation.models.sop import WaitConditionSpec, WaitConditionType
from sop_automation.runtime.diagnostics import is_secret_field, redact_mapping, redact_text
from sop_automation.runtime.locator_service import LocatorService

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page


@dataclass(frozen=True)
class PostconditionResult:
    satisfied: bool
    signals: dict[str, object] = field(default_factory=dict)
    error: str | None = None


class PostconditionEvaluator:
    """Evaluate explicit postconditions without treating preconditions as completion."""

    def __init__(self, locator_service: LocatorService | None = None) -> None:
        self._locator_service = locator_service or LocatorService()

    async def evaluate(
        self,
        page: "Page",
        spec: WaitConditionSpec,
        fallback_locator: "Locator | None" = None,
    ) -> PostconditionResult:
        deadline = time.monotonic() + spec.timeout_seconds
        last = PostconditionResult(False, {"type": spec.type.value})
        while True:
            last = await self._evaluate_once(page, spec, fallback_locator)
            if last.satisfied or time.monotonic() >= deadline:
                return last
            await asyncio.sleep(spec.poll_interval_seconds)

    async def probe(
        self,
        page: "Page",
        spec: WaitConditionSpec,
        fallback_locator: "Locator | None" = None,
    ) -> PostconditionResult:
        """Evaluate once for reconciliation without consuming the full postcondition timeout."""
        try:
            result = await self._probe_once(page, spec, fallback_locator)
            return PostconditionResult(
                satisfied=result.satisfied,
                signals=redact_mapping(result.signals),
                error=result.error,
            )
        except Exception as exc:
            return PostconditionResult(
                satisfied=False,
                signals={"type": spec.type.value},
                error=str(exc),
            )

    async def _probe_once(
        self,
        page: "Page",
        spec: WaitConditionSpec,
        fallback_locator: "Locator | None" = None,
    ) -> PostconditionResult:
        signals: dict[str, object] = {
            "type": spec.type.value,
            "element_name": spec.element_name,
            "probe": True,
        }
        if spec.type == WaitConditionType.URL_EQUALS:
            return PostconditionResult(
                page.url == (spec.expected_value or ""),
                {**signals, "current_url": page.url},
            )
        if spec.type == WaitConditionType.URL_CONTAINS:
            expected = spec.expected_value or ""
            return PostconditionResult(expected in page.url, {**signals, "current_url": page.url})

        if spec.type == WaitConditionType.ELEMENT_HIDDEN and spec.element_name:
            hidden = await self._evaluate_hidden_across_strategies(page, spec)
            return PostconditionResult(hidden.satisfied, {**signals, **hidden.signals}, hidden.error)

        if fallback_locator is not None:
            return await self._evaluate_resolved(page, spec, fallback_locator)

        if not spec.element_name:
            return PostconditionResult(False, signals, "Postcondition requires a locator")

        element_type = ElementType(spec.element_type) if spec.element_type else ElementType.UNKNOWN
        attempts: list[dict[str, object]] = []
        for strategy, locator in self._locator_service.candidate_locators(
            page, spec.element_name, element_type
        ):
            count = await locator.count()
            visible_indexes: list[int] = []
            for index in range(count):
                try:
                    if await locator.nth(index).is_visible():
                        visible_indexes.append(index)
                except Exception:
                    pass
            attempts.append(
                {
                    "strategy": strategy,
                    "match_count": count,
                    "visible_count": len(visible_indexes),
                }
            )
            if len(visible_indexes) == 1:
                result = await self._evaluate_resolved(
                    page, spec, locator.nth(visible_indexes[0])
                )
                return PostconditionResult(
                    result.satisfied,
                    {**signals, **result.signals, "locator_attempts": attempts},
                    result.error,
                )
            if len(visible_indexes) > 1:
                return PostconditionResult(
                    False,
                    {**signals, "locator_attempts": attempts},
                    f"Ambiguous postcondition locator for {spec.element_name!r}",
                )

        return PostconditionResult(False, {**signals, "locator_attempts": attempts})

    async def _evaluate_once(
        self,
        page: "Page",
        spec: WaitConditionSpec,
        fallback_locator: "Locator | None" = None,
    ) -> PostconditionResult:
        """Single non-blocking check used in the polling loop. Uses candidate_locators (no waiting)."""
        try:
            result = await self._probe_once(page, spec, fallback_locator)
            return PostconditionResult(
                satisfied=result.satisfied,
                signals=redact_mapping(result.signals),
                error=result.error,
            )
        except Exception as exc:
            return PostconditionResult(
                satisfied=False,
                signals={"type": spec.type.value},
                error=str(exc),
            )

    async def _resolve_locator(
        self,
        page: "Page",
        spec: WaitConditionSpec,
        fallback_locator: "Locator | None",
    ) -> "Locator | None":
        if spec.type in (WaitConditionType.URL_EQUALS, WaitConditionType.URL_CONTAINS):
            return None
        if spec.element_name:
            element_type = (
                ElementType(spec.element_type)
                if spec.element_type
                else ElementType.UNKNOWN
            )
            if spec.type == WaitConditionType.ELEMENT_HIDDEN:
                return None
            return await self._locator_service.locate(page, spec.element_name, element_type)
        return fallback_locator

    async def _evaluate_resolved(
        self,
        page: "Page",
        spec: WaitConditionSpec,
        locator: "Locator | None",
    ) -> PostconditionResult:
        timeout_ms = int(spec.timeout_seconds * 1000)
        signals: dict[str, object] = {
            "type": spec.type.value,
            "element_name": spec.element_name,
        }

        if spec.type == WaitConditionType.URL_EQUALS:
            try:
                await page.wait_for_url(spec.expected_value or "", timeout=timeout_ms)
            except Exception as exc:
                return PostconditionResult(False, {**signals, "current_url": page.url}, str(exc))
            return PostconditionResult(True, {**signals, "current_url": page.url})

        if spec.type == WaitConditionType.URL_CONTAINS:
            if spec.expected_value and spec.expected_value in page.url:
                return PostconditionResult(True, {**signals, "current_url": page.url})
            return PostconditionResult(False, {**signals, "current_url": page.url})

        if locator is None:
            if spec.type == WaitConditionType.ELEMENT_HIDDEN and spec.element_name:
                hidden = await self._evaluate_hidden_across_strategies(page, spec)
                return PostconditionResult(hidden.satisfied, {**signals, **hidden.signals}, hidden.error)
            return PostconditionResult(False, signals, "Postcondition requires a locator")

        count = await locator.count()
        visible = 0
        enabled = 0
        editable = 0
        for index in range(count):
            candidate = locator.nth(index)
            try:
                if await candidate.is_visible():
                    visible += 1
            except Exception:
                pass
            try:
                if await candidate.is_enabled():
                    enabled += 1
            except Exception:
                pass
            try:
                if await candidate.is_editable():
                    editable += 1
            except Exception:
                pass

        signals = {
            **signals,
            "match_count": count,
            "visible_count": visible,
            "enabled_count": enabled,
            "editable_count": editable,
        }

        if spec.type == WaitConditionType.ELEMENT_VISIBLE:
            return PostconditionResult(visible == 1, signals)
        if spec.type == WaitConditionType.ELEMENT_HIDDEN:
            return PostconditionResult(visible == 0, signals)
        if spec.type == WaitConditionType.ELEMENT_ENABLED:
            return PostconditionResult(enabled == 1, signals)
        if spec.type == WaitConditionType.ELEMENT_TEXT_EQUALS:
            text = await locator.inner_text()
            return self._value_result(text == (spec.expected_value or ""), signals, spec, text)
        if spec.type == WaitConditionType.ELEMENT_TEXT_CONTAINS:
            text = await locator.inner_text()
            expected = spec.expected_value or ""
            return self._value_result(expected in text, signals, spec, text)
        if spec.type == WaitConditionType.ELEMENT_VALUE_EQUALS:
            value = await locator.input_value()
            return self._value_result(value == (spec.expected_value or ""), signals, spec, value)

        return PostconditionResult(False, signals, f"Unsupported postcondition type: {spec.type.value}")

    async def _evaluate_hidden_across_strategies(
        self,
        page: "Page",
        spec: WaitConditionSpec,
    ) -> PostconditionResult:
        element_type = ElementType(spec.element_type) if spec.element_type else ElementType.UNKNOWN
        visible_total = 0
        attempts: list[dict[str, object]] = []
        for strategy, locator in self._locator_service.candidate_locators(
            page, spec.element_name or "", element_type
        ):
            count = await locator.count()
            visible = 0
            for index in range(count):
                try:
                    if await locator.nth(index).is_visible():
                        visible += 1
                except Exception:
                    pass
            visible_total += visible
            attempts.append({"strategy": strategy, "match_count": count, "visible_count": visible})
        return PostconditionResult(
            visible_total == 0,
            {"visible_count": visible_total, "locator_attempts": attempts},
        )

    def _value_result(
        self,
        matched: bool,
        signals: dict[str, object],
        spec: WaitConditionSpec,
        observed: str,
    ) -> PostconditionResult:
        secret_context = is_secret_field(spec.element_name or "") or is_secret_field(str(spec.expected_value or ""))
        value_signals: dict[str, object]
        if secret_context:
            value_signals = {"comparison_performed": True, "value_match": matched}
        else:
            value_signals = {
                "comparison_performed": True,
                "value_match": matched,
                "expected_value": redact_text(spec.expected_value or ""),
                "observed_value": redact_text(observed),
            }
        return PostconditionResult(matched, {**signals, **value_signals})
