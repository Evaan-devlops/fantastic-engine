"""Tests for SOP validation service — written but not run (Phase 1)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from sop_automation.models.sop import (
    InterpretationResult,
    InterpretationRequest,
    ApplicationProposal,
    GoalProposal,
    CapabilityProposal,
    StepProposal,
    OutcomeProposal,
    InputDefinition,
    OutputDefinition,
    SourceReference,
    InferenceSource,
)
from sop_automation.models.common import SourceFormat, ActionType, ElementType
from sop_automation.models.validation import ValidationSeverity
from sop_automation.services.sop_validate import SopValidateService
from sop_automation.storage.json_store import write_json_atomic, new_id, utc_now


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_valid_result(sop_id: str = "test-sop") -> InterpretationResult:
    """Return a minimal valid InterpretationResult with 1 app, 1 goal, 2 non-deferred caps."""
    step_login = StepProposal(
        step_id="step_001",
        sequence=1,
        action=ActionType.OPEN,
        element_name="home_page",
        element_type=ElementType.PAGE,
        value="https://example.com",
        expected_outcomes=[
            OutcomeProposal(
                outcome_id="login_done",
                description="Login succeeded",
                is_terminal=True,
                is_success=True,
            )
        ],
    )
    step_fill = StepProposal(
        step_id="step_002",
        sequence=1,
        action=ActionType.FILL,
        element_name="email_field",
        element_type=ElementType.TEXTBOX,
        value="{{input.email_address}}",
        expected_outcomes=[
            OutcomeProposal(
                outcome_id="contact_created",
                description="Contact created",
                is_terminal=True,
                is_success=True,
            )
        ],
    )
    cap_login = CapabilityProposal(
        capability_id="login_cap",
        name="Login",
        application_id="crm_app",
        description="Logs in.",
        steps=[step_login],
    )
    cap_create = CapabilityProposal(
        capability_id="create_cap",
        name="Create Contact",
        application_id="crm_app",
        description="Creates the contact.",
        steps=[step_fill],
    )
    return InterpretationResult(
        schema_version="1.0",
        result_id=new_id(),
        request_id="req-001",
        source_reference=SourceReference(
            source_path="/tmp/sop.txt",
            source_sha256="a" * 64,
            request_id="req-001",
        ),
        applications=[
            ApplicationProposal(application_id="crm_app", name="CRM App")
        ],
        goals=[
            GoalProposal(
                goal_id="create_contact",
                name="Create Contact Record",
                description="Creates a CRM contact.",
                entry_capability_id="login_cap",
                capability_ids=["login_cap", "create_cap"],
                required_inputs=["email_address"],
            )
        ],
        capabilities=[cap_login, cap_create],
        inputs=[
            InputDefinition(
                name="email_address",
                description="Email of the new contact",
                required=True,
            )
        ],
        assumptions=["User has CRM account"],
        unresolved_items=[],
        created_at=utc_now(),
    )


def make_valid_request(sop_id: str = "test-sop") -> InterpretationRequest:
    return InterpretationRequest(
        request_id="req-001",
        schema_version="1.0",
        sop_id=sop_id,
        source_path="/tmp/sop.txt",
        source_format=SourceFormat.NATURAL_LANGUAGE,
        source_sha256="a" * 64,
        created_at=utc_now(),
        normalized_text="some text",
    )


def _write_pair(
    tmp_path: Path,
    result: InterpretationResult,
    request: InterpretationRequest,
) -> Path:
    """Write request + result to tmp_path, return result path."""
    result_path = tmp_path / "interpretation_result.json"
    request_path = tmp_path / "interpretation_request.json"
    write_json_atomic(result_path, result.model_dump(mode="json"))
    write_json_atomic(request_path, request.model_dump(mode="json"))
    return result_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestValidationPassesOnValidResult:
    def test_valid_result_passes(self, tmp_path: Path) -> None:
        result = make_valid_result()
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        assert report.passed is True


class TestPydanticExtraFields:
    def test_unknown_field_rejected_by_pydantic(self) -> None:
        """Extra fields on InterpretationResult raise Pydantic ValidationError."""
        valid = make_valid_result()
        data = valid.model_dump(mode="json")
        data["unknown_field"] = 1
        with pytest.raises(PydanticValidationError):
            InterpretationResult.model_validate(data)


class TestUniqueIds:
    def test_duplicate_step_id_across_capabilities_rejected(self, tmp_path: Path) -> None:
        base = make_valid_result()
        # Give both capabilities the same step_id
        dup_step = StepProposal(
            step_id="step_001",  # same as login_cap's step
            sequence=1,
            action=ActionType.FILL,
            element_name="email_field",
            element_type=ElementType.TEXTBOX,
            value="{{input.email_address}}",
            expected_outcomes=[
                OutcomeProposal(
                    outcome_id="done", description="done",
                    is_terminal=True, is_success=True,
                )
            ],
        )
        new_caps = list(base.capabilities)
        # Replace create_cap's step with a duplicate step_id
        bad_cap = CapabilityProposal(
            capability_id="create_cap",
            name="Create Contact",
            application_id="crm_app",
            description="Creates the contact.",
            steps=[dup_step],
        )
        result = base.model_copy(update={"capabilities": [new_caps[0], bad_cap]})
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "UNIQUE_STEP_IDS" in rule_ids

    def test_duplicate_capability_id_rejected(self, tmp_path: Path) -> None:
        base = make_valid_result()
        cap_dup = CapabilityProposal(
            capability_id="login_cap",  # duplicate
            name="Login Copy",
            application_id="crm_app",
            description="Duplicate cap.",
            steps=[
                StepProposal(
                    step_id="step_999",
                    sequence=1,
                    action=ActionType.CLICK,
                    element_name="btn",
                    element_type=ElementType.BUTTON,
                    expected_outcomes=[
                        OutcomeProposal(
                            outcome_id="done", description="done",
                            is_terminal=True, is_success=True,
                        )
                    ],
                )
            ],
        )
        result = base.model_copy(
            update={"capabilities": list(base.capabilities) + [cap_dup]}
        )
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "UNIQUE_CAPABILITY_IDS" in rule_ids


class TestDependencyCycle:
    def test_dependency_cycle_rejected(self, tmp_path: Path) -> None:
        fixture = FIXTURES_DIR / "invalid_dependency_cycle.json"
        data = json.loads(fixture.read_text(encoding="utf-8"))
        result = InterpretationResult.model_validate(data)
        request = InterpretationRequest(
            request_id=data["request_id"],
            schema_version="1.0",
            sop_id="cycle-sop",
            source_path="/tmp/sop.txt",
            source_format=SourceFormat.NATURAL_LANGUAGE,
            source_sha256=data["source_reference"]["source_sha256"],
            created_at=utc_now(),
            normalized_text="cycle sop",
        )
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "NO_DEPENDENCY_CYCLES" in rule_ids


class TestBranchDestinations:
    def test_invalid_branch_destination_rejected(self, tmp_path: Path) -> None:
        base = make_valid_result()
        bad_step = StepProposal(
            step_id="step_001",
            sequence=1,
            action=ActionType.OPEN,
            element_name="home_page",
            element_type=ElementType.PAGE,
            value="https://example.com",
            expected_outcomes=[
                OutcomeProposal(
                    outcome_id="bad_branch",
                    description="Branch to nonexistent",
                    is_terminal=False,
                    is_success=True,
                    next_capability_id="nonexistent_cap",  # does not exist
                )
            ],
        )
        bad_cap = CapabilityProposal(
            capability_id="login_cap",
            name="Login",
            application_id="crm_app",
            description="Logs in.",
            steps=[bad_step],
        )
        result = base.model_copy(
            update={"capabilities": [bad_cap, base.capabilities[1]]}
        )
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "BRANCH_DESTINATIONS_RESOLVE" in rule_ids

    def test_valid_deferred_branch_passes(self, tmp_path: Path) -> None:
        fixture = FIXTURES_DIR / "deferred_branch.json"
        data = json.loads(fixture.read_text(encoding="utf-8"))
        result = InterpretationResult.model_validate(data)
        request = InterpretationRequest(
            request_id=data["request_id"],
            schema_version="1.0",
            sop_id="deferred-sop",
            source_path="/tmp/sop.txt",
            source_format=SourceFormat.NATURAL_LANGUAGE,
            source_sha256=data["source_reference"]["source_sha256"],
            created_at=utc_now(),
            normalized_text="deferred sop",
        )
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        # Branch to deferred cap is allowed — no BRANCH_DESTINATIONS_RESOLVE error
        branch_errors = [
            i for i in report.issues
            if i.rule_id == "BRANCH_DESTINATIONS_RESOLVE"
        ]
        assert branch_errors == []


class TestManualAuth:
    def test_manual_auth_with_password_rejected(self, tmp_path: Path) -> None:
        base = make_valid_result()
        auth_step = StepProposal(
            step_id="step_001",
            sequence=1,
            action=ActionType.MANUAL_AUTH,
            element_name="auth_page",
            element_type=ElementType.PAGE,
            value="Enter password: mysecret123",
            expected_outcomes=[
                OutcomeProposal(
                    outcome_id="auth_done", description="Authenticated",
                    is_terminal=True, is_success=True,
                )
            ],
        )
        bad_cap = CapabilityProposal(
            capability_id="login_cap",
            name="Login",
            application_id="crm_app",
            description="Logs in with auth.",
            steps=[auth_step],
        )
        result = base.model_copy(
            update={"capabilities": [bad_cap, base.capabilities[1]]}
        )
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "MANUAL_AUTH_NO_CREDS" in rule_ids

    def test_manual_auth_without_creds_passes(self, tmp_path: Path) -> None:
        base = make_valid_result()
        auth_step = StepProposal(
            step_id="step_001",
            sequence=1,
            action=ActionType.MANUAL_AUTH,
            element_name="auth_page",
            element_type=ElementType.PAGE,
            value="Please complete MFA in browser",
            expected_outcomes=[
                OutcomeProposal(
                    outcome_id="auth_done", description="Authenticated",
                    is_terminal=True, is_success=True,
                )
            ],
        )
        ok_cap = CapabilityProposal(
            capability_id="login_cap",
            name="Login",
            application_id="crm_app",
            description="Logs in with MFA prompt.",
            steps=[auth_step],
        )
        result = base.model_copy(
            update={"capabilities": [ok_cap, base.capabilities[1]]}
        )
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        cred_errors = [i for i in report.issues if i.rule_id == "MANUAL_AUTH_NO_CREDS"]
        assert cred_errors == []


class TestPlaceholderValidation:
    def test_missing_input_placeholder_rejected(self, tmp_path: Path) -> None:
        base = make_valid_result()
        bad_step = StepProposal(
            step_id="step_002",
            sequence=1,
            action=ActionType.FILL,
            element_name="email_field",
            element_type=ElementType.TEXTBOX,
            value="{{input.missing_name}}",  # not in inputs
            expected_outcomes=[
                OutcomeProposal(
                    outcome_id="done", description="done",
                    is_terminal=True, is_success=True,
                )
            ],
        )
        bad_cap = CapabilityProposal(
            capability_id="create_cap",
            name="Create Contact",
            application_id="crm_app",
            description="Creates contact.",
            steps=[bad_step],
        )
        result = base.model_copy(
            update={"capabilities": [base.capabilities[0], bad_cap]}
        )
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "VALID_PLACEHOLDERS" in rule_ids


class TestSourceHash:
    def test_source_hash_mismatch_rejected(self, tmp_path: Path) -> None:
        result = make_valid_result()
        # Request has different sha256
        request = InterpretationRequest(
            request_id="req-001",
            schema_version="1.0",
            sop_id="test-sop",
            source_path="/tmp/sop.txt",
            source_format=SourceFormat.NATURAL_LANGUAGE,
            source_sha256="b" * 64,  # different from result's "a"*64
            created_at=utc_now(),
            normalized_text="some text",
        )
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "SOURCE_HASH_PRESERVED" in rule_ids


class TestCapabilitySteps:
    def test_empty_non_deferred_capability_rejected(self, tmp_path: Path) -> None:
        base = make_valid_result()
        empty_cap = CapabilityProposal(
            capability_id="create_cap",
            name="Create Contact",
            application_id="crm_app",
            description="Creates contact.",
            steps=[],  # empty, non-deferred → error
            is_deferred=False,
        )
        result = base.model_copy(
            update={"capabilities": [base.capabilities[0], empty_cap]}
        )
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "CAPABILITY_HAS_STEPS" in rule_ids


class TestGoalTerminal:
    def test_goal_no_terminal_rejected(self, tmp_path: Path) -> None:
        # Cap with no terminal outcomes → GOAL_SAFE_TERMINAL error
        step_no_terminal = StepProposal(
            step_id="step_001",
            sequence=1,
            action=ActionType.OPEN,
            element_name="home_page",
            element_type=ElementType.PAGE,
            value="https://example.com",
            expected_outcomes=[
                OutcomeProposal(
                    outcome_id="page_open",
                    description="Page opened",
                    is_terminal=False,  # not terminal
                    is_success=True,
                )
            ],
        )
        cap = CapabilityProposal(
            capability_id="login_cap",
            name="Login",
            application_id="crm_app",
            description="Logs in.",
            steps=[step_no_terminal],
        )
        step_fill_no_terminal = StepProposal(
            step_id="step_002",
            sequence=1,
            action=ActionType.FILL,
            element_name="email_field",
            element_type=ElementType.TEXTBOX,
            value="{{input.email_address}}",
            expected_outcomes=[
                OutcomeProposal(
                    outcome_id="filled",
                    description="Filled",
                    is_terminal=False,  # not terminal
                    is_success=True,
                )
            ],
        )
        cap2 = CapabilityProposal(
            capability_id="create_cap",
            name="Create Contact",
            application_id="crm_app",
            description="Creates contact.",
            steps=[step_fill_no_terminal],
        )
        result = InterpretationResult(
            schema_version="1.0",
            result_id=new_id(),
            request_id="req-001",
            source_reference=SourceReference(
                source_path="/tmp/sop.txt",
                source_sha256="a" * 64,
                request_id="req-001",
            ),
            applications=[ApplicationProposal(application_id="crm_app", name="CRM App")],
            goals=[
                GoalProposal(
                    goal_id="create_contact",
                    name="Create Contact Record",
                    description="Creates contact.",
                    entry_capability_id="login_cap",
                    capability_ids=["login_cap", "create_cap"],
                    required_inputs=["email_address"],
                )
            ],
            capabilities=[cap, cap2],
            inputs=[InputDefinition(name="email_address", description="Email", required=True)],
            assumptions=[],
            unresolved_items=[],
            created_at=utc_now(),
        )
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "GOAL_SAFE_TERMINAL" in rule_ids


class TestSchemaVersion:
    def test_schema_version_mismatch_rejected(self, tmp_path: Path) -> None:
        base = make_valid_result()
        result = base.model_copy(update={"schema_version": "2.0"})
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "SCHEMA_VERSION" in rule_ids


class TestReportFile:
    def test_report_written_to_correct_path(self, tmp_path: Path) -> None:
        result = make_valid_result()
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        SopValidateService().validate(result_path, tmp_path)
        assert (tmp_path / "validation_report.json").exists()


# ---------------------------------------------------------------------------
# New manual-auth tests (correction pass)
# ---------------------------------------------------------------------------

def _make_valid_result_with_manual_auth(
    tmp_path: Path,
    step_value: str,
    sop_id: str = "test-sop",
) -> Path:
    """Write request + result with a MANUAL_AUTH step using the given value. Return result_path."""
    base = make_valid_result(sop_id)
    auth_step = StepProposal(
        step_id="step_001",
        sequence=1,
        action=ActionType.MANUAL_AUTH,
        element_name="auth_page",
        element_type=ElementType.PAGE,
        value=step_value,
        expected_outcomes=[
            OutcomeProposal(
                outcome_id="auth_done",
                description="Authenticated",
                is_terminal=True,
                is_success=True,
            )
        ],
    )
    auth_cap = CapabilityProposal(
        capability_id="login_cap",
        name="Login",
        application_id="crm_app",
        description="Logs in with manual auth.",
        steps=[auth_step],
    )
    result = base.model_copy(
        update={"capabilities": [auth_cap, base.capabilities[1]]}
    )
    sop_dir = tmp_path / "compiled" / sop_id
    sop_dir.mkdir(parents=True, exist_ok=True)
    result_path = sop_dir / "interpretation_result.json"
    request_path = sop_dir / "interpretation_request.json"
    request = make_valid_request(sop_id)
    write_json_atomic(result_path, result.model_dump(mode="json"))
    write_json_atomic(request_path, request.model_dump(mode="json"))
    return result_path


class TestManualAuthNewRules:
    def test_manual_auth_instruction_mentioning_otp_passes(self, tmp_path: Path) -> None:
        """An instruction mentioning OTP as a word is allowed."""
        result_path = _make_valid_result_with_manual_auth(
            tmp_path,
            step_value="Please complete MFA and enter the OTP shown in your authenticator app",
        )
        report = SopValidateService().validate(
            result_path=result_path,
            workspace_root=tmp_path,
        ).report
        manual_auth_errors = [i for i in report.issues if i.rule_id == "MANUAL_AUTH_NO_CREDS"]
        assert not manual_auth_errors

    def test_manual_auth_credential_assignment_rejected(self, tmp_path: Path) -> None:
        """A literal credential assignment is rejected."""
        result_path = _make_valid_result_with_manual_auth(
            tmp_path,
            step_value="password=mySecretPass1",
        )
        report = SopValidateService().validate(
            result_path=result_path,
            workspace_root=tmp_path,
        ).report
        assert any(i.rule_id == "MANUAL_AUTH_NO_CREDS" for i in report.issues)

    def test_manual_auth_bearer_token_rejected(self, tmp_path: Path) -> None:
        """A bearer token literal is rejected."""
        result_path = _make_valid_result_with_manual_auth(
            tmp_path,
            step_value="token: Bearer abc123xyz789",
        )
        report = SopValidateService().validate(
            result_path=result_path,
            workspace_root=tmp_path,
        ).report
        assert any(i.rule_id == "MANUAL_AUTH_NO_CREDS" for i in report.issues)


# ---------------------------------------------------------------------------
# New rule tests (correction pass)
# ---------------------------------------------------------------------------

class TestNewValidationRules:
    def test_request_id_mismatch_rejected(self, tmp_path: Path) -> None:
        """result.request_id must match request.request_id."""
        result = make_valid_result()
        # result has request_id="req-001"; create request with different id
        request = InterpretationRequest(
            request_id="req-DIFFERENT",
            schema_version="1.0",
            sop_id="test-sop",
            source_path="/tmp/sop.txt",
            source_format=SourceFormat.NATURAL_LANGUAGE,
            source_sha256="a" * 64,
            created_at=utc_now(),
            normalized_text="some text",
        )
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "REQUEST_ID_MATCH" in rule_ids

    def test_goal_capability_missing_rejected(self, tmp_path: Path) -> None:
        """Goal referencing non-existent capability is rejected."""
        base = make_valid_result()
        bad_goal = GoalProposal(
            goal_id="create_contact",
            name="Create Contact Record",
            description="Creates a CRM contact.",
            entry_capability_id="login_cap",
            capability_ids=["login_cap", "nonexistent_cap"],
            required_inputs=["email_address"],
        )
        result = base.model_copy(update={"goals": [bad_goal]})
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "GOAL_CAPABILITY_EXISTS" in rule_ids

    def test_capability_application_missing_rejected(self, tmp_path: Path) -> None:
        """Capability referencing non-existent application is rejected."""
        base = make_valid_result()
        bad_cap = CapabilityProposal(
            capability_id="login_cap",
            name="Login",
            application_id="nonexistent_app",  # not in result.applications
            description="Logs in.",
            steps=list(base.capabilities[0].steps),
        )
        result = base.model_copy(
            update={"capabilities": [bad_cap, base.capabilities[1]]}
        )
        request = make_valid_request()
        result_path = _write_pair(tmp_path, result, request)
        report = SopValidateService().validate(result_path, tmp_path).report
        rule_ids = [i.rule_id for i in report.issues]
        assert "CAPABILITY_APPLICATION_EXISTS" in rule_ids
