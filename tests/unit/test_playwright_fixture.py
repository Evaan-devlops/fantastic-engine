"""Playwright E2E fixture tests — written but not run. Requires playwright installed."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
from tests.fixtures.local_fixture_app import running_fixture_app

pytestmark = pytest.mark.playwright


class TestPlaywrightFixtureApp:
    """E2E tests against the local fixture app using Playwright.

    Run with: pytest -m playwright --headed
    Requires: playwright install chromium
    """

    @pytest.fixture()
    def fixture_url(self) -> str:
        with running_fixture_app() as app:
            yield app.base_url

    def test_login_form_present(self, page, fixture_url: str) -> None:
        page.goto(f"{fixture_url}/login")
        assert page.locator("input[name='username']").is_visible()
        assert page.locator("input[name='password']").is_visible()
        assert page.get_by_role("button", name="Submit").is_visible()

    def test_login_redirects_to_dashboard(self, page, fixture_url: str) -> None:
        page.goto(f"{fixture_url}/login")
        page.fill("input[name='username']", "testuser")
        page.fill("input[name='password']", "testpass")
        page.click("button[type='submit']")
        assert "/dashboard" in page.url

    def test_dashboard_shows_welcome(self, page, fixture_url: str) -> None:
        page.goto(f"{fixture_url}/dashboard")
        assert page.locator("text=Welcome to Dashboard").is_visible()

    def test_download_endpoint_triggers_download(self, page, fixture_url: str) -> None:
        with page.expect_download() as download_info:
            page.goto(f"{fixture_url}/download")
        download = download_info.value
        assert download.suggested_filename == "sample.txt"

    def test_form_fields_interactable(self, page, fixture_url: str) -> None:
        page.goto(f"{fixture_url}/form")
        page.fill("input[name='name']", "John Doe")
        page.fill("input[name='email']", "john@example.com")
        assert page.input_value("input[name='name']") == "John Doe"

    def test_missing_element_page_has_no_button(self, page, fixture_url: str) -> None:
        page.goto(f"{fixture_url}/missing-element")
        assert page.locator("button").count() == 0
