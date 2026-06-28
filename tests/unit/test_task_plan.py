"""Tests for dry-run task planning — written but not run (Phase 1)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sop_automation.services.task_plan import TaskPlanService
from sop_automation.errors import ValidationError
from sop_automation.storage.json_store import write_json_atomic, new_id, utc_now


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_compiled_sop_data(
    sop_id: str = "test-sop",
    goal_id: str = "create_contact",
    required_inputs: list[str] | None = None,
    include_deferred: bool = False,
    include_branch: bool = False,
) -> dict:
    """Build a minimal compiled_sop.json dict matching clean CompiledSop schema."""
    if required_inputs is None:
        required_inputs = ["email_address"]

    steps = [
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
            "retry_policy": {"max_attempts": 2, "retryable_error_codes": [], "delay_seconds": 1.0},
        }
    ]
    if include_branch:
        # Add a second outcome that branches — this makes a branch point
        steps[0]["expected_outcomes"].append(
            {
                "outcome_id": "branch_out",
                "description": "Branch",
                "is_terminal": False,
                "is_success": True,
                "condition": {
                    "source_key": "login_status",
                    "operator": "EQUALS",
                    "expected_value": "failed",
                },
                "next_capability_id": "other_cap",
            }
        )

    capabilities = [
        {
            "capability_id": "login_cap",
            "name": "Login",
            "application_id": "crm_app",
            "description": "Authenticates.",
            "steps": steps,
            "inputs": ["email_address"],
            "outputs": [],
            "is_deferred": False,
            "is_tool_candidate": False,
        }
    ]

    if include_deferred:
        capabilities.append(
            {
                "capability_id": "deferred_cap",
                "name": "Deferred Integration",
                "application_id": "crm_app",
                "description": "Not yet implemented.",
                "steps": [],
                "inputs": [],
                "outputs": [],
                "is_deferred": True,
                "is_tool_candidate": False,
            }
        )

    if include_branch:
        capabilities.append(
            {
                "capability_id": "other_cap",
                "name": "Other Cap",
                "application_id": "crm_app",
                "description": "Branch target.",
                "steps": [
                    {
                        "step_id": "step_other",
                        "sequence": 1,
                        "action": "CLICK",
                        "element_name": "btn",
                        "element_type": "BUTTON",
                        "application_id": "crm_app",
                        "capability_id": "other_cap",
                        "value": None,
                        "wait_condition": None,
                        "expected_outcomes": [
                            {
                                "outcome_id": "other_done",
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
                        "retry_policy": {"max_attempts": 2, "retryable_error_codes": [], "delay_seconds": 1.0},
                    }
                ],
                "inputs": [],
                "outputs": [],
                "is_deferred": False,
                "is_tool_candidate": False,
            }
        )

    cap_seq = ["login_cap"]
    if include_deferred:
        cap_seq.append("deferred_cap")
    if include_branch:
        cap_seq.append("other_cap")

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
            goal_id: {
                "goal_id": goal_id,
                "name": "Create Contact Record",
                "description": "Creates a CRM contact.",
                "entry_capability_id": cap_seq[0] if cap_seq else "",
                "capability_ids": cap_seq,
                "aliases": [],
                "required_inputs": required_inputs,
                "expected_outputs": [],
                "assumptions": [],
            }
        },
        "capabilities": capabilities,
        "inputs": {
            "email_address": {
                "name": "email_address",
                "description": "Email of the new contact",
                "required": True,
                "default_value": None,
            }
        },
        "assumptions": [],
        "unresolved_items": [],
        "compiled_at": utc_now().isoformat(),
        "compiled_content_sha256": "",
    }


def _write_compiled_sop(tmp_path: Path, data: dict, sop_id: str = "test-sop") -> None:
    sop_dir = tmp_path / "compiled" / sop_id
    sop_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(sop_dir / "compiled_sop.json", data)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTaskPlanValid:
    def test_plan_valid_inputs_returns_result(self, tmp_path: Path) -> None:
        data = _make_compiled_sop_data()
        _write_compiled_sop(tmp_path, data)
        result = TaskPlanService().plan(
            workspace_root=tmp_path,
            sop_id="test-sop",
            goal_id="create_contact",
            inputs={"email_address": "user@example.com"},
        )
        assert result.plan is not None
        assert result.plan_path.exists()

    def test_plan_planned_steps_present(self, tmp_path: Path) -> None:
        data = _make_compiled_sop_data()
        _write_compiled_sop(tmp_path, data)
        result = TaskPlanService().plan(
            workspace_root=tmp_path,
            sop_id="test-sop",
            goal_id="create_contact",
            inputs={"email_address": "user@example.com"},
        )
        assert len(result.plan.capabilities) > 0

    def test_plan_planned_steps_are_typed(self, tmp_path: Path) -> None:
        """capabilities must be PlannedCapability instances with PlannedStep members."""
        from sop_automation.models.task import PlannedCapability, PlannedStep
        data = _make_compiled_sop_data()
        _write_compiled_sop(tmp_path, data)
        result = TaskPlanService().plan(
            workspace_root=tmp_path,
            sop_id="test-sop",
            goal_id="create_contact",
            inputs={"email_address": "user@example.com"},
        )
        for cap in result.plan.capabilities:
            assert isinstance(cap, PlannedCapability)
            for step in cap.steps:
                assert isinstance(step, PlannedStep)


class TestTaskPlanRejection:
    def test_plan_missing_required_input_raises(self, tmp_path: Path) -> None:
        data = _make_compiled_sop_data(required_inputs=["email_address"])
        _write_compiled_sop(tmp_path, data)
        with pytest.raises(Exception) as exc_info:
            TaskPlanService().plan(
                workspace_root=tmp_path,
                sop_id="test-sop",
                goal_id="create_contact",
                inputs={},  # missing email_address
            )
        assert "email_address" in str(exc_info.value).lower() or "missing" in str(exc_info.value).lower()

    def test_plan_invalid_goal_id_raises(self, tmp_path: Path) -> None:
        data = _make_compiled_sop_data()
        _write_compiled_sop(tmp_path, data)
        with pytest.raises(Exception):
            TaskPlanService().plan(
                workspace_root=tmp_path,
                sop_id="test-sop",
                goal_id="nonexistent_goal",
                inputs={"email_address": "user@example.com"},
            )


class TestTaskPlanDeferred:
    def test_plan_marks_deferred_capability_as_destination(self, tmp_path: Path) -> None:
        data = _make_compiled_sop_data(include_deferred=True)
        _write_compiled_sop(tmp_path, data)
        result = TaskPlanService().plan(
            workspace_root=tmp_path,
            sop_id="test-sop",
            goal_id="create_contact",
            inputs={"email_address": "user@example.com"},
        )
        assert "deferred_cap" in result.plan.deferred_destinations


class TestTaskPlanStorage:
    def test_plan_saved_to_runs_dir(self, tmp_path: Path) -> None:
        data = _make_compiled_sop_data()
        _write_compiled_sop(tmp_path, data)
        TaskPlanService().plan(
            workspace_root=tmp_path,
            sop_id="test-sop",
            goal_id="create_contact",
            inputs={"email_address": "user@example.com"},
        )
        runs_dir = tmp_path / "runs"
        assert runs_dir.exists()
        dry_run_files = list(runs_dir.glob("dry_run_*.json"))
        assert len(dry_run_files) > 0


class TestTaskPlanBranch:
    def test_plan_branch_points_identified(self, tmp_path: Path) -> None:
        data = _make_compiled_sop_data(include_branch=True)
        _write_compiled_sop(tmp_path, data)
        result = TaskPlanService().plan(
            workspace_root=tmp_path,
            sop_id="test-sop",
            goal_id="create_contact",
            inputs={"email_address": "user@example.com"},
        )
        # step_001 has 2 outcomes (one branching) → branch point
        assert len(result.plan.branch_points) > 0

    def test_plan_branch_points_are_typed(self, tmp_path: Path) -> None:
        """branch_points must be list[BranchPoint], not list[str]."""
        from sop_automation.models.task import BranchPoint
        data = _make_compiled_sop_data(include_branch=True)
        _write_compiled_sop(tmp_path, data)
        result = TaskPlanService().plan(
            workspace_root=tmp_path,
            sop_id="test-sop",
            goal_id="create_contact",
            inputs={"email_address": "user@example.com"},
        )
        for bp in result.plan.branch_points:
            assert isinstance(bp, BranchPoint)
            assert isinstance(bp.step_id, str)

    def test_plan_capability_edges_present_for_branch(self, tmp_path: Path) -> None:
        """capability_edges must include conditional edges when branching."""
        data = _make_compiled_sop_data(include_branch=True)
        _write_compiled_sop(tmp_path, data)
        result = TaskPlanService().plan(
            workspace_root=tmp_path,
            sop_id="test-sop",
            goal_id="create_contact",
            inputs={"email_address": "user@example.com"},
        )
        assert len(result.plan.capability_edges) > 0
        conditional_edges = [e for e in result.plan.capability_edges if e.is_conditional]
        assert len(conditional_edges) > 0
