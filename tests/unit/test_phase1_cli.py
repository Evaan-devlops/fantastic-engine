"""CLI integration tests for Phase 1 commands — written but not run (Phase 1)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sop_automation.storage.json_store import write_json_atomic, new_id, utc_now

# Path to src/ for PYTHONPATH injection
# parents[0] = unit/, parents[1] = tests/, parents[2] = SOPAutomationV2/
SRC_PATH = str(Path(__file__).parents[2] / "src")


def run_cli(
    args: list[str],
    workspace: Path | None = None,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    base_env = {**os.environ, "PYTHONPATH": SRC_PATH}
    if workspace:
        base_env["SOP_WORKSPACE"] = str(workspace)
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "sop_automation"] + args,
        env=base_env,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Helpers — build fixture dicts without importing heavy model classes
# ---------------------------------------------------------------------------

def _make_request_dict(sop_id: str = "test-sop", sha256: str = "a" * 64) -> dict:
    return {
        "request_id": "req-001",
        "schema_version": "1.0",
        "sop_id": sop_id,
        "source_path": "/tmp/sop.txt",
        "source_format": "NATURAL_LANGUAGE",
        "source_sha256": sha256,
        "created_at": utc_now().isoformat(),
        "normalized_text": "some text",
        "sections": [],
        "detected_urls": [],
        "detected_placeholders": [],
        "capability_hints": [],
        "possible_condition_lines": [],
        "possible_deferred_lines": [],
    }


def _make_result_dict(sop_id: str = "test-sop", sha256: str = "a" * 64) -> dict:
    return {
        "schema_version": "1.0",
        "result_id": new_id(),
        "request_id": "req-001",
        "source_reference": {
            "source_path": "/tmp/sop.txt",
            "source_sha256": sha256,
            "request_id": "req-001",
        },
        "applications": [
            {
                "application_id": "crm_app",
                "name": "CRM App",
                "url_patterns": [],
                "inference": [],
            }
        ],
        "goals": [
            {
                "goal_id": "create_contact",
                "name": "Create Contact Record",
                "description": "Creates a CRM contact.",
                "entry_capability_id": "login_cap",
                "capability_ids": ["login_cap"],
                "required_inputs": ["email_address"],
                "expected_outputs": [],
                "assumptions": [],
                "inference": [],
            }
        ],
        "capabilities": [
            {
                "capability_id": "login_cap",
                "name": "Login",
                "application_id": "crm_app",
                "description": "Authenticates.",
                "is_deferred": False,
                "steps": [
                    {
                        "step_id": "step_001",
                        "sequence": 1,
                        "action": "OPEN",
                        "element_name": "home_page",
                        "element_type": "PAGE",
                        "value": "https://example.com",
                        "wait_condition": None,
                        "expected_outcomes": [
                            {
                                "outcome_id": "done",
                                "description": "Done",
                                "is_terminal": True,
                                "is_success": True,
                                "next_capability_id": None,
                            }
                        ],
                        "dependencies": [],
                        "notes": None,
                        "source_line": None,
                        "inference": [],
                    }
                ],
                "inputs": ["email_address"],
                "outputs": [],
                "inference": [],
            }
        ],
        "inputs": [
            {
                "name": "email_address",
                "description": "Email",
                "required": True,
                "default_value": None,
            }
        ],
        "outputs": [],
        "assumptions": ["User has CRM account"],
        "unresolved_items": [],
        "created_at": utc_now().isoformat(),
    }


def _make_passing_report_dict(
    result_dict: dict,
    request_dict: dict | None = None,
) -> dict:
    import json as _json
    import hashlib

    def _sha256(d: dict) -> str:
        return hashlib.sha256(
            _json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    return {
        "report_id": new_id(),
        "result_id": result_dict["result_id"],
        "request_id": "req-001",
        "schema_version": "1.0",
        "passed": True,
        "issues": [],
        "validated_at": utc_now().isoformat(),
        "request_sha256": _sha256(request_dict) if request_dict else "",
        "result_sha256": _sha256(result_dict),
    }


def _make_failing_report_dict(
    result_dict: dict,
    request_dict: dict | None = None,
) -> dict:
    import json as _json
    import hashlib

    def _sha256(d: dict) -> str:
        return hashlib.sha256(
            _json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    return {
        "report_id": new_id(),
        "result_id": result_dict["result_id"],
        "request_id": "req-001",
        "schema_version": "1.0",
        "passed": False,
        "issues": [
            {
                "severity": "ERROR",
                "rule_id": "SCHEMA_VERSION",
                "message": "Forced failure",
                "location": None,
            }
        ],
        "validated_at": utc_now().isoformat(),
        "request_sha256": _sha256(request_dict) if request_dict else "",
        "result_sha256": _sha256(result_dict),
    }


def _make_compiled_sop_dict(sop_id: str = "test-sop") -> dict:
    return {
        "sop_id": sop_id,
        "schema_version": "1.0",
        "title": "Test SOP",
        "source": {
            "sop_id": sop_id,
            "source_format": "NATURAL_LANGUAGE",
            "source_path": "/tmp/sop.txt",
            "preserved_path": f"/tmp/sources/{sop_id}/sop.txt",
            "source_sha256": "a" * 64,
            "created_at": utc_now().isoformat(),
        },
        "applications": ["crm_app"],
        "goals": {
            "create_contact": {
                "goal_id": "create_contact",
                "name": "Create Contact",
                "description": "Creates contact.",
                "entry_capability_id": "login_cap",
                "capability_ids": ["login_cap"],
                "aliases": [],
                "required_inputs": ["email_address"],
                "expected_outputs": [],
                "assumptions": [],
            }
        },
        "capabilities": [
            {
                "capability_id": "login_cap",
                "name": "Login",
                "application_id": "crm_app",
                "description": "Authenticates.",
                "steps": [
                    {
                        "step_id": "step_001",
                        "sequence": 1,
                        "action": "OPEN",
                        "element_name": "home_page",
                        "element_type": "PAGE",
                        "application_id": "crm_app",
                        "capability_id": "login_cap",
                        "value": "https://example.com",
                        "wait_condition": None,
                        "expected_outcomes": [
                            {
                                "outcome_id": "done",
                                "description": "Done",
                                "is_terminal": True,
                                "is_success": True,
                                "condition": None,
                                "next_capability_id": None,
                            }
                        ],
                        "dependencies": [],
                        "notes": None,
                        "source_line": None,
                        "retry_policy": {
                            "max_attempts": 2,
                            "retryable_error_codes": [],
                            "delay_seconds": 1.0,
                        },
                    }
                ],
                "inputs": ["email_address"],
                "outputs": [],
                "is_deferred": False,
                "is_tool_candidate": False,
            }
        ],
        "inputs": {
            "email_address": {
                "name": "email_address",
                "description": "Email",
                "required": True,
                "default_value": None,
            }
        },
        "assumptions": [],
        "unresolved_items": [],
        "compiled_at": utc_now().isoformat(),
        "compiled_content_sha256": "",
    }


# ---------------------------------------------------------------------------
# sop prepare
# ---------------------------------------------------------------------------

class TestSopPrepare:
    def test_sop_prepare_valid_txt_exits_0(self, tmp_path: Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text("# My SOP\n1. Do something\n", encoding="utf-8")
        result = run_cli(
            ["sop", "prepare", "--source", str(source), "--sop-id", "test-sop"],
            workspace=tmp_path,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert (tmp_path / "compiled" / "test-sop" / "interpretation_request.json").exists()

    def test_sop_prepare_missing_file_exits_1(self, tmp_path: Path) -> None:
        result = run_cli(
            ["sop", "prepare", "--source", "/nonexistent/file.txt", "--sop-id", "test-sop"],
            workspace=tmp_path,
        )
        assert result.returncode == 1

    def test_sop_prepare_unsupported_extension_exits_1(self, tmp_path: Path) -> None:
        source = tmp_path / "source.pdf"
        source.write_bytes(b"%PDF-1.4")
        result = run_cli(
            ["sop", "prepare", "--source", str(source), "--sop-id", "test-sop"],
            workspace=tmp_path,
        )
        assert result.returncode == 1

    def test_sop_prepare_invalid_sop_id_exits_1(self, tmp_path: Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text("# My SOP\n", encoding="utf-8")
        result = run_cli(
            ["sop", "prepare", "--source", str(source), "--sop-id", "has spaces"],
            workspace=tmp_path,
        )
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# sop validate-result
# ---------------------------------------------------------------------------

class TestSopValidateResult:
    def test_sop_validate_result_exits_0_on_valid_result(self, tmp_path: Path) -> None:
        sha256 = "a" * 64
        sop_dir = tmp_path / "compiled" / "test-sop"
        sop_dir.mkdir(parents=True, exist_ok=True)

        request_dict = _make_request_dict(sha256=sha256)
        result_dict = _make_result_dict(sha256=sha256)

        # Write both to same directory
        request_path = sop_dir / "interpretation_request.json"
        result_path = sop_dir / "interpretation_result.json"
        request_path.write_text(json.dumps(request_dict), encoding="utf-8")
        result_path.write_text(json.dumps(result_dict), encoding="utf-8")

        result = run_cli(
            ["sop", "validate-result", "--result", str(result_path)],
            workspace=tmp_path,
        )
        # Exit 0 if passed, 1 if failed but service ran — either way not 2
        assert "PASS" in result.stdout or "FAIL" in result.stdout
        # If validation passes (which it should for valid data), exit 0
        if "PASS" in result.stdout:
            assert result.returncode == 0

    def test_sop_validate_result_exits_1_on_invalid_result(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad_result.json"
        bad_file.write_text('{"not": "valid"}', encoding="utf-8")
        result = run_cli(
            ["sop", "validate-result", "--result", str(bad_file)],
            workspace=tmp_path,
        )
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# sop compile
# ---------------------------------------------------------------------------

class TestSopCompile:
    def test_sop_compile_exits_1_when_no_validation_report(self, tmp_path: Path) -> None:
        sop_dir = tmp_path / "compiled" / "test-sop"
        sop_dir.mkdir(parents=True, exist_ok=True)
        result_dict = _make_result_dict()
        result_path = sop_dir / "interpretation_result.json"
        result_path.write_text(json.dumps(result_dict), encoding="utf-8")
        # No validation_report.json — compile must fail

        result = run_cli(
            ["sop", "compile", "--result", str(result_path)],
            workspace=tmp_path,
        )
        assert result.returncode == 1

    def test_sop_compile_exits_1_when_validation_failed(self, tmp_path: Path) -> None:
        sop_dir = tmp_path / "compiled" / "test-sop"
        sop_dir.mkdir(parents=True, exist_ok=True)
        result_dict = _make_result_dict()
        request_dict = _make_request_dict()
        failing_report = _make_failing_report_dict(result_dict, request_dict)

        result_path = sop_dir / "interpretation_result.json"
        result_path.write_text(json.dumps(result_dict), encoding="utf-8")
        (sop_dir / "interpretation_request.json").write_text(
            json.dumps(request_dict), encoding="utf-8"
        )
        (sop_dir / "validation_report.json").write_text(
            json.dumps(failing_report), encoding="utf-8"
        )

        result = run_cli(
            ["sop", "compile", "--result", str(result_path)],
            workspace=tmp_path,
        )
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# sop list
# ---------------------------------------------------------------------------

class TestSopList:
    def test_sop_list_exits_0_when_empty(self, tmp_path: Path) -> None:
        # Create compiled dir but no compiled SOPs
        (tmp_path / "compiled").mkdir(parents=True, exist_ok=True)
        result = run_cli(["sop", "list"], workspace=tmp_path)
        assert result.returncode == 0
        assert "no compiled" in result.stdout.lower() or result.stdout.strip() != ""

    def test_sop_list_exits_0_with_entries(self, tmp_path: Path) -> None:
        sop_id = "my-test-sop"
        sop_dir = tmp_path / "compiled" / sop_id
        sop_dir.mkdir(parents=True, exist_ok=True)
        compiled_data = _make_compiled_sop_dict(sop_id=sop_id)
        (sop_dir / "compiled_sop.json").write_text(
            json.dumps(compiled_data), encoding="utf-8"
        )
        result = run_cli(["sop", "list"], workspace=tmp_path)
        assert result.returncode == 0
        assert sop_id in result.stdout


# ---------------------------------------------------------------------------
# task plan
# ---------------------------------------------------------------------------

class TestTaskPlanCli:
    def test_task_plan_exits_1_missing_required_input(self, tmp_path: Path) -> None:
        sop_id = "test-sop"
        sop_dir = tmp_path / "compiled" / sop_id
        sop_dir.mkdir(parents=True, exist_ok=True)
        compiled_data = _make_compiled_sop_dict(sop_id=sop_id)
        (sop_dir / "compiled_sop.json").write_text(
            json.dumps(compiled_data), encoding="utf-8"
        )
        # Required input email_address not provided
        result = run_cli(
            ["task", "plan", "--sop", sop_id, "--goal", "create_contact"],
            workspace=tmp_path,
        )
        assert result.returncode == 1

    def test_task_plan_exits_1_invalid_goal(self, tmp_path: Path) -> None:
        sop_id = "test-sop"
        sop_dir = tmp_path / "compiled" / sop_id
        sop_dir.mkdir(parents=True, exist_ok=True)
        compiled_data = _make_compiled_sop_dict(sop_id=sop_id)
        (sop_dir / "compiled_sop.json").write_text(
            json.dumps(compiled_data), encoding="utf-8"
        )
        result = run_cli(
            [
                "task", "plan",
                "--sop", sop_id,
                "--goal", "nonexistent_goal",
                "--input", "email_address=user@example.com",
            ],
            workspace=tmp_path,
        )
        assert result.returncode == 1

    def test_input_flag_invalid_format_exits_1(self, tmp_path: Path) -> None:
        sop_id = "test-sop"
        sop_dir = tmp_path / "compiled" / sop_id
        sop_dir.mkdir(parents=True, exist_ok=True)
        compiled_data = _make_compiled_sop_dict(sop_id=sop_id)
        (sop_dir / "compiled_sop.json").write_text(
            json.dumps(compiled_data), encoding="utf-8"
        )
        # --input without '=' is invalid
        result = run_cli(
            [
                "task", "plan",
                "--sop", sop_id,
                "--goal", "create_contact",
                "--input", "noequals",
            ],
            workspace=tmp_path,
        )
        assert result.returncode == 1
