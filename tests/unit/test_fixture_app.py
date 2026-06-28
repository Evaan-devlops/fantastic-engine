"""Unit tests for local_fixture_app — written but not run."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
from tests.fixtures.local_fixture_app import FixtureApp, running_fixture_app


class TestFixtureAppRoutes:
    def test_root_returns_200(self) -> None:
        with running_fixture_app() as app:
            with urllib.request.urlopen(f"{app.base_url}/") as resp:
                assert resp.status == 200

    def test_dashboard_returns_200_with_text(self) -> None:
        with running_fixture_app() as app:
            with urllib.request.urlopen(f"{app.base_url}/dashboard") as resp:
                assert resp.status == 200
                body = resp.read().decode("utf-8")
                assert "Dashboard" in body

    def test_success_returns_json(self) -> None:
        with running_fixture_app() as app:
            with urllib.request.urlopen(f"{app.base_url}/success") as resp:
                assert resp.status == 200
                data = json.loads(resp.read().decode("utf-8"))
                assert data["status"] == "ok"

    def test_not_found_returns_404(self) -> None:
        with running_fixture_app() as app:
            try:
                urllib.request.urlopen(f"{app.base_url}/not-found")
                assert False, "Expected HTTPError"
            except urllib.error.HTTPError as e:
                assert e.code == 404

    def test_download_has_content_disposition(self) -> None:
        with running_fixture_app() as app:
            with urllib.request.urlopen(f"{app.base_url}/download") as resp:
                assert resp.status == 200
                cd = resp.headers.get("Content-Disposition", "")
                assert "attachment" in cd

    def test_start_stop_clean(self) -> None:
        app = FixtureApp()
        app.start()
        port = app.port
        assert port > 0
        app.stop()

    def test_base_url_format(self) -> None:
        with running_fixture_app() as app:
            assert app.base_url.startswith("http://127.0.0.1:")
