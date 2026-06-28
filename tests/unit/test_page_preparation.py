"""Unit tests for PagePreparationService — written but not run."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from sop_automation.models.sop import WaitConditionSpec, WaitConditionType
from sop_automation.runtime.page_preparation import PagePreparationService


class TestPagePreparationImport:
    def test_can_be_instantiated(self) -> None:
        svc = PagePreparationService()
        assert svc is not None

    def test_prepare_method_exists(self) -> None:
        svc = PagePreparationService()
        assert hasattr(svc, "prepare")
        assert callable(svc.prepare)


class TestPagePreparationWaits:
    def _make_mock_page(self) -> AsyncMock:
        page = AsyncMock()
        page.wait_for_load_state = AsyncMock(return_value=None)
        page.url = "http://localhost/dashboard"
        locator_mock = AsyncMock()
        locator_mock.is_visible = AsyncMock(return_value=True)
        page.locator = MagicMock(return_value=locator_mock)
        return page

    def test_dom_ready_completes(self) -> None:
        svc = PagePreparationService()
        page = self._make_mock_page()
        spec = WaitConditionSpec(type=WaitConditionType.PAGE_DOM_READY)
        asyncio.run(svc.prepare(page, spec))
        page.wait_for_load_state.assert_called()

    def test_no_wait_spec_still_calls_load_state(self) -> None:
        svc = PagePreparationService()
        page = self._make_mock_page()
        asyncio.run(svc.prepare(page, None))
        page.wait_for_load_state.assert_called()
