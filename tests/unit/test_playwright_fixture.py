"""Playwright E2E fixture tests. Requires: pip install -e . && playwright install chromium"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
from tests.fixtures.local_fixture_app import running_fixture_app

pytestmark = pytest.mark.playwright


class TestPlaywrightFixtureApp:
    """E2E tests against the local fixture app using Playwright.

    Run with: pytest -m playwright
    Requires: playwright install chromium
    """

    @pytest.fixture()
    def fixture_url(self) -> str:
        with running_fixture_app() as app:
            yield app.base_url

    def test_login_form_present(self, fixture_url: str) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(f"{fixture_url}/login")
                assert page.locator("input[name='username']").is_visible()
                assert page.locator("input[name='password']").is_visible()
                assert page.get_by_role("button", name="Submit").is_visible()
            finally:
                browser.close()

    def test_login_redirects_to_dashboard(self, fixture_url: str) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(f"{fixture_url}/login")
                page.fill("input[name='username']", "testuser")
                page.fill("input[name='password']", "testpass")
                page.click("button[type='submit']")
                assert "/dashboard" in page.url
            finally:
                browser.close()

    def test_dashboard_shows_welcome(self, fixture_url: str) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(f"{fixture_url}/dashboard")
                assert page.locator("text=Welcome to Dashboard").is_visible()
            finally:
                browser.close()

    def test_download_endpoint_triggers_download(self, fixture_url: str) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                with page.expect_download() as download_info:
                    page.goto(f"{fixture_url}/download")
                download = download_info.value
                assert download.suggested_filename == "sample.txt"
            finally:
                browser.close()

    def test_form_fields_interactable(self, fixture_url: str) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(f"{fixture_url}/form")
                page.fill("input[name='name']", "John Doe")
                page.fill("input[name='email']", "john@example.com")
                assert page.input_value("input[name='name']") == "John Doe"
            finally:
                browser.close()

    def test_missing_element_page_has_no_button(self, fixture_url: str) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(f"{fixture_url}/missing-element")
                assert page.locator("button").count() == 0
            finally:
                browser.close()
