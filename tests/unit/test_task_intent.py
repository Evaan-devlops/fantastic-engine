"""Unit tests for TaskIntentService — written but not run."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from sop_automation.errors import ValidationError as SopValidationError
from sop_automation.models.task import TaskIntent, TaskIntentInterpretationRequest
from sop_automation.services.task_intent import TaskIntentService
from sop_automation.storage.json_store import new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_intent(
    requested_goal: str = "create_contact",
    preferred_sop_id: str | None = None,
    schema_version: str = "1.0",
) -> TaskIntent:
    return TaskIntent(
        intent_id=new_id(),
        schema_version=schema_version,
        requested_goal=requested_goal,
        preferred_sop_id=preferred_sop_id,
        application_hints=[],
        inputs={},
        constraints=[],
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# TestPrepareIntent
# ---------------------------------------------------------------------------

class TestPrepareIntent:
    def setup_method(self) -> None:
        self.service = TaskIntentService()

    def test_goal_from_key_value_line(self, tmp_path: Path) -> None:
        request_text = "goal=create_contact"
        result = self.service.prepare_intent(request_text, tmp_path)
        assert result.intent.requested_goal == "create_contact"

    def test_goal_from_first_line(self, tmp_path: Path) -> None:
        request_text = "create_contact\nemail_address=user@example.com"
        result = self.service.prepare_intent(request_text, tmp_path)
        assert result.intent.requested_goal == "create_contact"

    def test_extra_inputs_parsed(self, tmp_path: Path) -> None:
        request_text = "goal=create_contact\nemail_address=user@example.com"
        result = self.service.prepare_intent(request_text, tmp_path)
        assert result.intent.inputs.get("email_address") == "user@example.com"

    def test_sop_id_key_sets_preferred(self, tmp_path: Path) -> None:
        request_text = "goal=create_contact\nsop_id=my-sop"
        result = self.service.prepare_intent(request_text, tmp_path)
        assert result.intent.preferred_sop_id == "my-sop"

    def test_application_hint_parsed(self, tmp_path: Path) -> None:
        request_text = "goal=create_contact\napplication=crm_app"
        result = self.service.prepare_intent(request_text, tmp_path)
        assert "crm_app" in result.intent.application_hints

    def test_constraint_parsed(self, tmp_path: Path) -> None:
        request_text = "goal=create_contact\nconstraint=headless=false"
        result = self.service.prepare_intent(request_text, tmp_path)
        assert "headless=false" in result.intent.constraints

    def test_no_goal_raises(self, tmp_path: Path) -> None:
        request_text = "# just a comment\n"
        with pytest.raises(SopValidationError):
            self.service.prepare_intent(request_text, tmp_path)

    def test_empty_string_raises(self, tmp_path: Path) -> None:
        with pytest.raises(SopValidationError):
            self.service.prepare_intent("", tmp_path)

    def test_intent_json_written_to_generated_dir(self, tmp_path: Path) -> None:
        request_text = "goal=create_contact"
        result = self.service.prepare_intent(request_text, tmp_path)
        assert result.intent_path.exists()
        assert result.intent_path.suffix == ".json"
        assert "generated" in str(result.intent_path)

    def test_intent_id_in_filename(self, tmp_path: Path) -> None:
        request_text = "goal=create_contact"
        result = self.service.prepare_intent(request_text, tmp_path)
        assert result.intent.intent_id in result.intent_path.name

    def test_sop_id_arg_overridden_by_request_text_sop_id(self, tmp_path: Path) -> None:
        request_text = "goal=create_contact\nsop_id=from-text"
        result = self.service.prepare_intent(request_text, tmp_path, sop_id="from-arg")
        # request_text sop_id= takes effect (last write wins in the loop)
        assert result.intent.preferred_sop_id == "from-text"

    def test_comment_lines_ignored(self, tmp_path: Path) -> None:
        request_text = "# this is a comment\ngoal=create_contact"
        result = self.service.prepare_intent(request_text, tmp_path)
        assert result.intent.requested_goal == "create_contact"

    def test_multiple_constraints_collected(self, tmp_path: Path) -> None:
        request_text = (
            "goal=create_contact\n"
            "constraint=headless=false\n"
            "constraint=slow_mo=100"
        )
        result = self.service.prepare_intent(request_text, tmp_path)
        assert len(result.intent.constraints) == 2
        assert "headless=false" in result.intent.constraints
        assert "slow_mo=100" in result.intent.constraints


# ---------------------------------------------------------------------------
# TestValidateIntent
# ---------------------------------------------------------------------------

class TestValidateIntent:
    def setup_method(self) -> None:
        self.service = TaskIntentService()

    def test_valid_intent_passes(self, tmp_path: Path) -> None:
        intent = _make_intent("create_contact")
        result = self.service.validate_intent(intent, tmp_path)
        assert result.passed is True
        assert result.report is not None

    def test_invalid_sop_id_fails(self, tmp_path: Path) -> None:
        # preferred_sop_id points to a compiled SOP that does not exist
        intent = _make_intent("create_contact", preferred_sop_id="ghost-sop")
        result = self.service.validate_intent(intent, tmp_path)
        assert result.passed is False
        rule_ids = [issue.rule_id for issue in result.report.issues]
        assert "INTENT_SOP_EXISTS" in rule_ids

    def test_empty_goal_fails(self, tmp_path: Path) -> None:
        # Construct intent directly to bypass prepare_intent guard
        intent = TaskIntent(
            intent_id=new_id(),
            schema_version="1.0",
            requested_goal="   ",  # blank / whitespace only
            preferred_sop_id=None,
            application_hints=[],
            inputs={},
            constraints=[],
            created_at=datetime.now(UTC),
        )
        result = self.service.validate_intent(intent, tmp_path)
        assert result.passed is False
        rule_ids = [issue.rule_id for issue in result.report.issues]
        assert "INTENT_GOAL_REQUIRED" in rule_ids

    def test_valid_sop_id_passes_when_file_exists(self, tmp_path: Path) -> None:
        import json

        # Write a minimal compiled SOP so the path check passes
        sop_dir = tmp_path / "compiled" / "real-sop"
        sop_dir.mkdir(parents=True, exist_ok=True)
        (sop_dir / "compiled_sop.json").write_text(
            json.dumps({"sop_id": "real-sop"}), encoding="utf-8"
        )
        intent = _make_intent("create_contact", preferred_sop_id="real-sop")
        result = self.service.validate_intent(intent, tmp_path)
        assert result.passed is True

    def test_report_has_report_id(self, tmp_path: Path) -> None:
        intent = _make_intent("create_contact")
        result = self.service.validate_intent(intent, tmp_path)
        assert result.report.report_id
        assert len(result.report.report_id) > 0

    def test_no_issues_when_intent_fully_valid(self, tmp_path: Path) -> None:
        intent = _make_intent("create_contact")
        result = self.service.validate_intent(intent, tmp_path)
        assert result.report.issues == []


# ---------------------------------------------------------------------------
# TestTaskIntentInterpretationRequest
# ---------------------------------------------------------------------------

class TestTaskIntentInterpretationRequest:
    def _make_request(self) -> TaskIntentInterpretationRequest:
        return TaskIntentInterpretationRequest(
            request_id="req-123",
            raw_request="Create a new contact named John",
            raw_request_sha256="a" * 64,
            available_sop_goal_summaries=[{"goal_id": "g1", "name": "Create Contact"}],
            required_output_schema={"type": "object"},
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    def test_model_validates_correctly(self) -> None:
        req = self._make_request()
        assert req.request_id == "req-123"

    def test_schema_version_default(self) -> None:
        req = self._make_request()
        assert req.schema_version == "1.0"

    def test_request_id_stored(self) -> None:
        req = self._make_request()
        assert req.request_id == "req-123"

    def test_raw_request_stored(self) -> None:
        req = self._make_request()
        assert "John" in req.raw_request

    def test_sha256_stored(self) -> None:
        req = self._make_request()
        assert req.raw_request_sha256 == "a" * 64


class TestTaskIntentNewFields:
    def test_request_id_defaults_empty(self) -> None:
        intent = _make_intent("create_contact")
        assert intent.request_id == ""

    def test_raw_request_sha256_defaults_empty(self) -> None:
        intent = _make_intent("create_contact")
        assert intent.raw_request_sha256 == ""

    def test_request_id_can_be_set(self) -> None:
        intent = TaskIntent(
            intent_id=new_id(),
            request_id="req-xyz",
            raw_request_sha256="b" * 64,
            requested_goal="create_contact",
            created_at=datetime.now(UTC),
        )
        assert intent.request_id == "req-xyz"
        assert intent.raw_request_sha256 == "b" * 64
