"""Locator strategy chain for resolving UI elements without iframes."""
from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING

from sop_automation.models.common import ElementType
from sop_automation.runtime.diagnostics import CandidateAttempt

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

_ELEMENT_TYPE_TO_ROLE = {
    ElementType.BUTTON: "button",
    ElementType.LINK: "link",
    ElementType.CHECKBOX: "checkbox",
    ElementType.RADIO: "radio",
    ElementType.DROPDOWN: "combobox",
    ElementType.TEXTBOX: "textbox",
}


class LocatorError(Exception):
    """Raised when no locator strategy succeeds."""

    def __init__(
        self,
        element_name: str,
        tried: list[str],
        candidates: list[str],
        attempts: list[CandidateAttempt] | None = None,
    ) -> None:
        self.element_name = element_name
        self.tried = tried
        self.candidates = candidates
        self.attempts: list[CandidateAttempt] = attempts or []
        super().__init__(
            f"Could not locate element {element_name!r}. "
            f"Tried: {tried}. "
            f"Visible candidates: {candidates}"
        )


class LocatorAmbiguityError(LocatorError):
    """Raised when a locator strategy finds more than one plausible element."""

    def __init__(self, element_name: str, strategy: str, count: int, candidates: list[str]) -> None:
        self.strategy = strategy
        self.count = count
        super().__init__(element_name, [strategy], candidates)
        self.args = (
            f"Ambiguous locator for element {element_name!r}. "
            f"Strategy {strategy} matched {count} elements. "
            f"Visible candidates: {candidates}",
        )


_TEXTBOX_SUFFIX_RE = re.compile(
    r"\s+(?:text\s+box|textbox|input\s+field|input|field)\s*$",
    re.IGNORECASE,
)
_DEFAULT_LOCATOR_TIMEOUT_SECONDS = 2.0
_DEFAULT_LOCATOR_POLL_SECONDS = 0.05


def normalize_element_name(element_name: str, element_type: ElementType) -> str:
    """Remove generic descriptive suffixes from semantic textbox names."""
    original = " ".join(element_name.split())
    normalized = original
    if element_type == ElementType.TEXTBOX:
        previous = None
        while previous != normalized:
            previous = normalized
            normalized = _TEXTBOX_SUFFIX_RE.sub("", normalized).strip()
    return normalized or original


def _contains_words_pattern(text: str) -> re.Pattern[str]:
    escaped = re.escape(text).replace(r"\ ", r"\s+")
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


class LocatorService:
    """Resolves Playwright locators using a 4-strategy chain."""

    def __init__(
        self,
        timeout_seconds: float = _DEFAULT_LOCATOR_TIMEOUT_SECONDS,
        poll_seconds: float = _DEFAULT_LOCATOR_POLL_SECONDS,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._poll_seconds = poll_seconds

    async def locate(
        self,
        page: "Page",
        element_name: str,
        element_type: ElementType,
    ) -> "Locator":
        lookup_name = normalize_element_name(element_name, element_type)
        accessible_name: str | re.Pattern[str] = (
            re.compile(f"^{re.escape(lookup_name)}$", re.IGNORECASE)
            if element_type == ElementType.TEXTBOX
            else element_name
        )
        placeholder_contains_name = _contains_words_pattern(lookup_name)

        tried = self._strategy_names(element_name, element_type, lookup_name)
        deadline = time.monotonic() + self._timeout_seconds
        last_candidates: list[str] = []

        while True:
            for strategy, locator in self._locators(
                page, element_name, element_type, lookup_name, accessible_name,
                placeholder_contains_name,
            ):
                found = await self._unique_visible_match(locator, element_name, strategy, page)
                if found is not None:
                    return found

            last_candidates = await self._visible_candidates(page)
            if time.monotonic() >= deadline:
                break

            await asyncio.sleep(self._poll_seconds)

        attempts = await self._collect_attempts(page, element_name, element_type)
        raise LocatorError(element_name, tried, last_candidates, attempts)

    def build_locator(
        self,
        page: "Page",
        element_name: str,
        element_type: ElementType,
    ) -> "Locator":
        return self.candidate_locators(page, element_name, element_type)[0][1]

    def candidate_locators(
        self,
        page: "Page",
        element_name: str,
        element_type: ElementType,
    ) -> list[tuple[str, "Locator"]]:
        lookup_name = normalize_element_name(element_name, element_type)
        accessible_name: str | re.Pattern[str] = (
            re.compile(f"^{re.escape(lookup_name)}$", re.IGNORECASE)
            if element_type == ElementType.TEXTBOX
            else element_name
        )
        placeholder_contains_name = _contains_words_pattern(lookup_name)
        return self._locators(
            page, element_name, element_type, lookup_name, accessible_name,
            placeholder_contains_name,
        )

    def _strategy_names(
        self,
        element_name: str,
        element_type: ElementType,
        lookup_name: str,
    ) -> list[str]:
        names: list[str] = []
        role = _ELEMENT_TYPE_TO_ROLE.get(element_type)
        if role:
            names.append(f"role={role}[name={lookup_name!r}]")
        names.append(f"label={lookup_name!r}")
        names.append(f"placeholder={lookup_name!r}")
        if element_type == ElementType.TEXTBOX:
            names.append(f"placeholder~={lookup_name!r}")
        names.append(f"text={element_name!r}")
        return names

    def _locators(
        self,
        page: "Page",
        element_name: str,
        element_type: ElementType,
        lookup_name: str,
        accessible_name: str | re.Pattern[str],
        placeholder_contains_name: re.Pattern[str],
    ) -> list[tuple[str, "Locator"]]:
        locators: list[tuple[str, "Locator"]] = []

        # Strategy 1: accessible role + name
        role = _ELEMENT_TYPE_TO_ROLE.get(element_type)
        if role:
            locator = page.get_by_role(role, name=accessible_name)  # type: ignore[arg-type]
            strategy = f"role={role}[name={lookup_name!r}]"
            locators.append((strategy, locator))

        # Strategy 2: label
        locator = page.get_by_label(accessible_name)
        strategy = f"label={lookup_name!r}"
        locators.append((strategy, locator))

        # Strategy 3: placeholder
        locator = page.get_by_placeholder(accessible_name)
        strategy = f"placeholder={lookup_name!r}"
        locators.append((strategy, locator))

        if element_type == ElementType.TEXTBOX:
            locator = page.get_by_placeholder(placeholder_contains_name)
            strategy = f"placeholder~={lookup_name!r}"
            locators.append((strategy, locator))

        # Strategy 4: exact visible text
        locator = page.get_by_text(element_name, exact=True)
        strategy = f"text={element_name!r}"
        locators.append((strategy, locator))
        return locators

    async def _unique_visible_match(
        self,
        locator: "Locator",
        element_name: str,
        strategy: str,
        page: "Page",
    ) -> "Locator | None":
        count = await locator.count()
        if count == 0:
            return None

        visible_indexes: list[int] = []
        for index in range(count):
            candidate = locator.nth(index)
            try:
                if await candidate.is_visible():
                    visible_indexes.append(index)
            except Exception:
                continue

        if not visible_indexes:
            return None
        if len(visible_indexes) == 1:
            return locator.nth(visible_indexes[0])

        candidates = await self._visible_candidates(page)
        raise LocatorAmbiguityError(element_name, strategy, len(visible_indexes), candidates)

    async def _collect_attempts(
        self,
        page: "Page",
        element_name: str,
        element_type: ElementType,
    ) -> list[CandidateAttempt]:
        """Probe each locator strategy once (non-waiting) and record the diagnostic state."""
        attempts: list[CandidateAttempt] = []
        for strategy, locator in self._locators(
            page,
            element_name,
            element_type,
            normalize_element_name(element_name, element_type),
            (
                re.compile(
                    f"^{re.escape(normalize_element_name(element_name, element_type))}$",
                    re.IGNORECASE,
                )
                if element_type == ElementType.TEXTBOX
                else element_name
            ),
            _contains_words_pattern(normalize_element_name(element_name, element_type)),
        ):
            try:
                count = await locator.count()
            except Exception:
                attempts.append(CandidateAttempt(strategy=strategy, match_count=0, rejection_reason="PROBE_ERROR"))
                continue

            if count == 0:
                attempts.append(CandidateAttempt(strategy=strategy, match_count=0, rejection_reason="NO_MATCH"))
                continue

            visible: bool | None = None
            enabled: bool | None = None
            editable: bool | None = None
            rejection: str | None = None
            try:
                candidate = locator.nth(0)
                visible = await candidate.is_visible()
                if visible:
                    try:
                        enabled = await candidate.is_enabled()
                    except Exception:
                        pass
                    try:
                        editable = await candidate.is_editable()
                    except Exception:
                        pass
                else:
                    rejection = "NOT_VISIBLE"
            except Exception:
                rejection = "PROBE_ERROR"

            attempts.append(CandidateAttempt(
                strategy=strategy,
                match_count=count,
                visible=visible,
                enabled=enabled,
                editable=editable,
                rejection_reason=rejection,
            ))
        return attempts

    async def _visible_candidates(self, page: "Page") -> list[str]:
        try:
            elements = await page.query_selector_all(
                "button, a, input, select, textarea, [role]"
            )
            candidates = []
            for el in elements[:5]:
                text = (await el.inner_text()).strip()[:60]
                if text:
                    candidates.append(text)
            return candidates
        except Exception:
            return []
