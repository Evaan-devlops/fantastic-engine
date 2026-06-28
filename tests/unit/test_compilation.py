"""Tests for SOP compilation service — written but not run (Phase 1)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sop_automation.services.sop_compile import SopCompileService
from sop_automation.models.sop import (
    InterpretationResult,
    InterpretationRequest,
    ApplicationProposal,
    GoalProposal,
    CapabilityProposal,
    StepProposal,
    OutcomeProposal,
    InputDefinition,
    SourceReference,
    CompiledSop,
)
from sop_automation.models.common import SourceFormat, ActionType, ElementType
from sop_automation.models.validation import (
    ValidationReport,
    ValidationSeverity,
    ValidationIssue,
)
from sop_automation.storage.json_store import write_json_atomic, new_id, utc_now


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(sop_id: str = "test-sop") -> InterpretationResult:
    step = StepProposal(
        step_id="step_001",
        sequence=1,
        action=ActionType.OPEN,
        element_name="home_page",
        element_type=ElementType.PAGE,
        value="https://example.com",
        expected_outcomes=[
            OutcomeProposal(
                outcome_id="done",
                description="Page opened",
                is_terminal=True,
                is_success=True,
            )
        ],
    )
    step2 = StepProposal(
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
    deferred_step: list[StepProposal] = []

    cap1 = CapabilityProposal(
        capability_id="login_cap",
        name="Login",
        application_id="crm_app",
        description="Authenticates the user.",
        steps=[step],
    )
    cap2 = CapabilityProposal(
        capability_id="create_cap",
        name="Create Contact",
        application_id="crm_app",
        description="Creates the contact record.",
        steps=[step2],
    )
    cap_deferred = CapabilityProposal(
        capability_id="deferred_cap",
        name="Deferred Integration",
        application_id="crm_app",
        description="Will be implemented later.",
        steps=deferred_step,
        is_deferred=True,
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
        applications=[ApplicationProposal(application_id="crm_app", name="CRM App")],
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
        capabilities=[cap1, cap2, cap_deferred],
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


def _make_request(sop_id: str = "test-sop") -> InterpretationRequest:
    return InterpretationRequest(
        request_id="req-001",
        schema_version="1.0",
        sop_id=sop_id,
        source_path="/tmp/sop.txt",
        source_format=SourceFormat.NATURAL_LANGUAGE,
        source_sha256="a" * 64,
        created_at=utc_now(),
        normalized_text="some source text",
    )


def _make_passing_report(
    result: InterpretationResult,
    request_sha256: str = "",
    result_sha256: str = "",
) -> ValidationReport:
    return ValidationReport(
        report_id=new_id(),
        result_id=result.result_id,
        request_id=result.request_id,
        schema_version="1.0",
        passed=True,
        issues=[],
        validated_at=utc_now(),
        request_sha256=request_sha256,
        result_sha256=result_sha256,
    )


def _make_failing_report(
    result: InterpretationResult,
    request_sha256: str = "",
    result_sha256: str = "",
) -> ValidationReport:
    return ValidationReport(
        report_id=new_id(),
        result_id=result.result_id,
        request_id=result.request_id,
        schema_version="1.0",
        passed=False,
        issues=[
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                rule_id="SCHEMA_VERSION",
                message="Forced failure",
            )
        ],
        validated_at=utc_now(),
        request_sha256=request_sha256,
        result_sha256=result_sha256,
    )


def _setup_compile_workspace(tmp_path: Path, sop_id: str = "test-sop") -> Path:
    """Write request, result, and passing report with content hashes; return result_path."""
    import json as _json
    from sop_automation.storage.json_store import sha256_of_str

    sop_dir = tmp_path / "compiled" / sop_id
    sop_dir.mkdir(parents=True, exist_ok=True)

    result = _make_result(sop_id)
    request = _make_request(sop_id)

    result_dict = result.model_dump(mode="json")
    request_dict = request.model_dump(mode="json")

    # Compute canonical hashes that match what sop_compile will verify
    result_sha256 = sha256_of_str(_json.dumps(result_dict, sort_keys=True, ensure_ascii=False))
    request_sha256 = sha256_of_str(_json.dumps(request_dict, sort_keys=True, ensure_ascii=False))

    report = _make_passing_report(result, request_sha256=request_sha256, result_sha256=result_sha256)

    result_path = sop_dir / "interpretation_result.json"
    write_json_atomic(result_path, result_dict)
    write_json_atomic(sop_dir / "interpretation_request.json", request_dict)
    write_json_atomic(sop_dir / "validation_report.json", report.model_dump(mode="json"))
    return result_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCompileOutput:
    def test_compile_produces_compiled_sop_json(self, tmp_path: Path) -> None:
        result_path = _setup_compile_workspace(tmp_path)
        SopCompileService().compile(result_path=result_path, workspace_root=tmp_path)
        assert (tmp_path / "compiled" / "test-sop" / "compiled_sop.json").exists()

    def test_compile_generates_manifest_fields(self, tmp_path: Path) -> None:
        result_path = _setup_compile_workspace(tmp_path)
        SopCompileService().compile(result_path=result_path, workspace_root=tmp_path)
        manifest_path = tmp_path / "manifests" / "test-sop.manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for key in ("sop_id", "title", "schema_version", "compiled_at",
                    "goals", "capabilities", "required_inputs", "source_sha256"):
            assert key in manifest, f"Manifest missing key: {key}"

    def test_compile_compiled_content_sha256_present(self, tmp_path: Path) -> None:
        result_path = _setup_compile_workspace(tmp_path)
        SopCompileService().compile(result_path=result_path, workspace_root=tmp_path)
        compiled_json_path = tmp_path / "compiled" / "test-sop" / "compiled_sop.json"
        data = json.loads(compiled_json_path.read_text(encoding="utf-8"))
        assert "compiled_content_sha256" in data
        assert data["compiled_content_sha256"] != ""

    def test_compile_generates_markdown_file(self, tmp_path: Path) -> None:
        result_path = _setup_compile_workspace(tmp_path)
        compile_result = SopCompileService().compile(
            result_path=result_path, workspace_root=tmp_path
        )
        assert compile_result.markdown_path.exists()
        md_text = compile_result.markdown_path.read_text(encoding="utf-8")
        assert "## Goals" in md_text


class TestCompileRejection:
    def test_compile_rejected_when_validation_failed(self, tmp_path: Path) -> None:
        from sop_automation.errors import ValidationError as SopValidationError
        sop_id = "test-sop"
        sop_dir = tmp_path / "compiled" / sop_id
        sop_dir.mkdir(parents=True, exist_ok=True)

        result = _make_result(sop_id)
        request = _make_request(sop_id)
        report = _make_failing_report(result)

        result_path = sop_dir / "interpretation_result.json"
        write_json_atomic(result_path, result.model_dump(mode="json"))
        write_json_atomic(sop_dir / "interpretation_request.json", request.model_dump(mode="json"))
        write_json_atomic(sop_dir / "validation_report.json", report.model_dump(mode="json"))

        with pytest.raises(Exception):  # StorageError or SopValidationError
            SopCompileService().compile(result_path=result_path, workspace_root=tmp_path)

    def test_compile_rejected_when_no_validation_report(self, tmp_path: Path) -> None:
        sop_id = "test-sop"
        sop_dir = tmp_path / "compiled" / sop_id
        sop_dir.mkdir(parents=True, exist_ok=True)

        result = _make_result(sop_id)
        request = _make_request(sop_id)

        result_path = sop_dir / "interpretation_result.json"
        write_json_atomic(result_path, result.model_dump(mode="json"))
        write_json_atomic(sop_dir / "interpretation_request.json", request.model_dump(mode="json"))
        # No validation_report.json written

        with pytest.raises(Exception):  # StorageError
            SopCompileService().compile(result_path=result_path, workspace_root=tmp_path)

    def test_compile_rejected_when_files_changed_since_validation(self, tmp_path: Path) -> None:
        """Compile must fail if result file was modified after validation (hash mismatch)."""
        import json as _json
        from sop_automation.storage.json_store import sha256_of_str

        sop_id = "test-sop"
        sop_dir = tmp_path / "compiled" / sop_id
        sop_dir.mkdir(parents=True, exist_ok=True)

        result = _make_result(sop_id)
        request = _make_request(sop_id)

        result_dict = result.model_dump(mode="json")
        request_dict = request.model_dump(mode="json")

        # Store ORIGINAL hashes in the report
        original_result_sha256 = sha256_of_str(
            _json.dumps(result_dict, sort_keys=True, ensure_ascii=False)
        )
        original_request_sha256 = sha256_of_str(
            _json.dumps(request_dict, sort_keys=True, ensure_ascii=False)
        )
        report = _make_passing_report(
            result,
            request_sha256=original_request_sha256,
            result_sha256=original_result_sha256,
        )

        result_path = sop_dir / "interpretation_result.json"
        write_json_atomic(result_path, result_dict)
        write_json_atomic(sop_dir / "interpretation_request.json", request_dict)
        write_json_atomic(sop_dir / "validation_report.json", report.model_dump(mode="json"))

        # Now modify the result file AFTER the report was written → hash mismatch
        modified = {**result_dict, "schema_version": "2.0"}
        result_path.write_text(_json.dumps(modified), encoding="utf-8")

        with pytest.raises(Exception):  # SopValidationError about hash mismatch
            SopCompileService().compile(result_path=result_path, workspace_root=tmp_path)


class TestManifestContents:
    def test_manifest_excludes_inference_metadata(self, tmp_path: Path) -> None:
        result_path = _setup_compile_workspace(tmp_path)
        SopCompileService().compile(result_path=result_path, workspace_root=tmp_path)
        manifest_path = tmp_path / "manifests" / "test-sop.manifest.json"
        manifest_text = manifest_path.read_text(encoding="utf-8")
        assert "inference" not in manifest_text


class TestMarkdownContents:
    def test_markdown_includes_deferred_capability_section(self, tmp_path: Path) -> None:
        result_path = _setup_compile_workspace(tmp_path)
        compile_result = SopCompileService().compile(
            result_path=result_path, workspace_root=tmp_path
        )
        md_text = compile_result.markdown_path.read_text(encoding="utf-8")
        # The result has a deferred cap — markdown should mark it
        assert "Deferred" in md_text or "deferred" in md_text

    def test_markdown_includes_assumptions_section(self, tmp_path: Path) -> None:
        result_path = _setup_compile_workspace(tmp_path)
        compile_result = SopCompileService().compile(
            result_path=result_path, workspace_root=tmp_path
        )
        md_text = compile_result.markdown_path.read_text(encoding="utf-8")
        assert "## Assumptions" in md_text


class TestCompiledSopRoundTrip:
    def test_compiled_sop_json_round_trips_pydantic(self, tmp_path: Path) -> None:
        result_path = _setup_compile_workspace(tmp_path)
        SopCompileService().compile(result_path=result_path, workspace_root=tmp_path)
        compiled_json_path = tmp_path / "compiled" / "test-sop" / "compiled_sop.json"
        data = json.loads(compiled_json_path.read_text(encoding="utf-8"))
        # Must not raise
        compiled = CompiledSop.model_validate(data)
        assert compiled.sop_id == "test-sop"
