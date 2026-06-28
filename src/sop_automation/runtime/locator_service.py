"""Locator strategy chain for resolving UI elements without iframes."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sop_automation.models.common import ElementType

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

    def __init__(self, element_name: str, tried: list[str], candidates: list[str]) -> None:
        self.element_name = element_name
        self.tried = tried
        self.candidates = candidates
        super().__init__(
            f"Could not locate element {element_name!r}. "
            f"Tried: {tried}. "
            f"Visible candidates: {candidates}"
        )


class LocatorService:
    """Resolves Playwright locators using a 4-strategy chain."""

    async def locate(
        self,
        page: "Page",
        element_name: str,
        element_type: ElementType,
    ) -> "Locator":
        tried: list[str] = []

        # Strategy 1: accessible role + name
        role = _ELEMENT_TYPE_TO_ROLE.get(element_type)
        if role:
            locator = page.get_by_role(role, name=element_name)  # type: ignore[arg-type]
            tried.append(f"role={role}[name={element_name!r}]")
            if await locator.count() > 0:
                return locator

        # Strategy 2: label
        locator = page.get_by_label(element_name)
        tried.append(f"label={element_name!r}")
        if await locator.count() > 0:
            return locator

        # Strategy 3: placeholder
        locator = page.get_by_placeholder(element_name)
        tried.append(f"placeholder={element_name!r}")
        if await locator.count() > 0:
            return locator

        # Strategy 4: exact visible text
        locator = page.get_by_text(element_name, exact=True)
        tried.append(f"text={element_name!r}")
        if await locator.count() > 0:
            return locator

        # Collect visible candidates for diagnostics
        candidates = await self._visible_candidates(page)
        raise LocatorError(element_name, tried, candidates)

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
