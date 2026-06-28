"""Unit tests for SopSelectorService — written but not run."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sop_automation.errors import StorageError
from sop_automation.errors import ValidationError as SopValidationError
from sop_automation.models.task import TaskIntent
from sop_automation.services.sop_selector import SopSelectionResult, SopSelectorService
from sop_automation.storage.json_store import new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMPILED_AT = "2026-06-28T00:00:00+00:00"
_CREATED_AT = "2026-06-28T00:00:00+00:00"
_SHA256 = "a" * 64


def _compiled_sop_dict(
    sop_id: str = "test-sop",
    goals: dict | None = None,
) -> dict:
    """Return a minimal valid CompiledSop JSON dict."""
    if goals is None:
        goals = {
            "create_contact": {
                "goal_id": "create_contact",
                "name": "Create Contact",
                "description": "Creates a contact record.",
                "entry_capability_id": "login_cap",
                "capability_ids": ["login_cap"],
                "aliases": ["new-contact"],
                "required_inputs": [],
                "expected_outputs": [],
                "assumptions": [],
            }
        }
    return {
        "sop_id": sop_id,
        "schema_version": "1.0",
        "title": f"Test SOP — {sop_id}",
        "source": {
            "sop_id": sop_id,
            "source_format": "NATURAL_LANGUAGE",
            "source_path": "/tmp/sop.txt",
            "preserved_path": f"/tmp/sources/{sop_id}/sop.txt",
            "source_sha256": _SHA256,
            "created_at": _CREATED_AT,
        },
        "applications": ["crm_app"],
        "goals": goals,
        "capabilities": [],
        "inputs": {},
        "assumptions": [],
        "unresolved_items": [],
        "compiled_at": _COMPILED_AT,
        "compiled_content_sha256": "",
    }


def _write_compiled_sop(workspace_root: Path, sop_id: str, data: dict | None = None) -> Path:
    """Write a compiled SOP JSON file into the expected workspace location."""
    sop_dir = workspace_root / "compiled" / sop_id
    sop_dir.mkdir(parents=True, exist_ok=True)
    path = sop_dir / "compiled_sop.json"
    path.write_text(json.dumps(data or _compiled_sop_dict(sop_id)), encoding="utf-8")
    return path


def _make_intent(
    requested_goal: str,
    preferred_sop_id: str | None = None,
    application_hints: list[str] | None = None,
) -> TaskIntent:
    return TaskIntent(
        intent_id=new_id(),
        schema_version="1.0",
        requested_goal=requested_goal,
        preferred_sop_id=preferred_sop_id,
        application_hints=application_hints or [],
        inputs={},
        constraints=[],
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# TestPreferredSopPath
# ---------------------------------------------------------------------------

class TestPreferredSopPath:
    def setup_method(self) -> None:
        self.service = SopSelectorService()

    def test_preferred_sop_found_exact_goal_id(self, tmp_path: Path) -> None:
        _write_compiled_sop(tmp_path, "test-sop")
        intent = _make_intent("create_contact", preferred_sop_id="test-sop")
        result = self.service.select(intent, tmp_path)
        assert isinstance(result, SopSelectionResult)
        assert result.sop_id == "test-sop"
        assert result.goal_id == "create_contact"
        assert result.confidence == 1.0

    def test_preferred_sop_found_via_alias(self, tmp_path: Path) -> None:
        _write_compiled_sop(tmp_path, "test-sop")
        intent = _make_intent("new-contact", preferred_sop_id="test-sop")
        result = self.service.select(intent, tmp_path)
        assert result.goal_id == "create_contact"
        assert result.confidence == 1.0

    def test_preferred_sop_not_found_raises_storage_error(self, tmp_path: Path) -> None:
        # No SOP file written — directory doesn't exist
        intent = _make_intent("create_contact", preferred_sop_id="missing-sop")
        with pytest.raises(StorageError):
            self.service.select(intent, tmp_path)

    def test_preferred_sop_goal_not_found_raises_validation_error(
        self, tmp_path: Path
    ) -> None:
        _write_compiled_sop(tmp_path, "test-sop")
        intent = _make_intent("nonexistent_goal", preferred_sop_id="test-sop")
        with pytest.raises(SopValidationError):
            self.service.select(intent, tmp_path)


# ---------------------------------------------------------------------------
# TestScoringPath
# ---------------------------------------------------------------------------

class TestScoringPath:
    def setup_method(self) -> None:
        self.service = SopSelectorService()

    def test_scoring_exact_goal_id_match(self, tmp_path: Path) -> None:
        _write_compiled_sop(tmp_path, "test-sop")
        # No preferred_sop_id → scoring path; exact goal_id scores highest
        intent = _make_intent("create_contact")
        result = self.service.select(intent, tmp_path)
        assert result.sop_id == "test-sop"
        assert result.goal_id == "create_contact"

    def test_scoring_no_candidates_raises(self, tmp_path: Path) -> None:
        # Write a SOP whose goal doesn't match the requested goal at all
        data = _compiled_sop_dict("test-sop", goals={
            "delete_record": {
                "goal_id": "delete_record",
                "name": "Delete Record",
                "description": "Removes a record.",
                "entry_capability_id": "cap-1",
                "capability_ids": ["cap-1"],
                "aliases": [],
                "required_inputs": [],
                "expected_outputs": [],
                "assumptions": [],
            }
        })
        _write_compiled_sop(tmp_path, "test-sop", data)
        # Completely unrelated goal → no score > 0
        intent = _make_intent("zzz_completely_unrelated_xyzxyz")
        with pytest.raises(SopValidationError):
            self.service.select(intent, tmp_path)

    def test_scoring_no_compiled_dir_raises_storage_error(self, tmp_path: Path) -> None:
        # No compiled directory at all
        intent = _make_intent("create_contact")
        with pytest.raises(StorageError):
            self.service.select(intent, tmp_path)

    def test_selection_result_has_expected_fields(self, tmp_path: Path) -> None:
        _write_compiled_sop(tmp_path, "test-sop")
        intent = _make_intent("create_contact")
        result = self.service.select(intent, tmp_path)
        assert hasattr(result, "sop_id")
        assert hasattr(result, "goal_id")
        assert hasattr(result, "confidence")
        assert hasattr(result, "alternatives")
        assert isinstance(result.confidence, float)
        assert isinstance(result.alternatives, list)
