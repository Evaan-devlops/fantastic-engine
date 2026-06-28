"""Unit tests for domain model validation, serialization, and immutability."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from sop_automation.models.common import ActionType, RunStatus, StepStatus, SourceFormat, ElementType
from sop_automation.models.clarification import ClarificationRequest, ClarificationType
from sop_automation.models.execution import RunState, StepProgress
from sop_automation.models.sop import (
    CompiledSop,
    InterpretationResult,
    InterpretationRequest,
    ApplicationProposal,
    GoalProposal,
    GoalDefinition,
    CapabilityProposal,
    StepProposal,
    OutcomeProposal,
    InputDefinition,
    SourceReference,
    ConditionSpec,
    ConditionOperator,
    WaitConditionSpec,
    WaitConditionType,
)
from sop_automation.models.task import TaskPlan, PlannedStep, PlannedOutcome, PlannedCapability, TaskIntent
from sop_automation.models.tools import ToolDefinition, ToolHealth
from sop_automation.storage.json_store import utc_now

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(UTC).isoformat()


@pytest.fixture()
def compiled_sop_data() -> dict:
    return {
        "sop_id": "sop-001",
        "schema_version": "1.0",
        "title": "Login SOP",
        "source": {
            "sop_id": "sop-001",
            "source_path": "/tmp/sop.txt",
            "source_format": "NATURAL_LANGUAGE",
            "preserved_path": "/tmp/sources/sop-001/sop.txt",
            "source_sha256": "a" * 64,
            "created_at": _now(),
        },
        "applications": ["app-001"],
        "goals": {},
        "capabilities": [],
        "inputs": {},
        "assumptions": [],
        "unresolved_items": [],
        "compiled_at": _now(),
        "compiled_content_sha256": "",
    }


@pytest.fixture()
def task_plan_data() -> dict:
    return {
        "sop_id": "sop-001",
        "created_at": _now(),
        "plan_id": "plan-001",
        "goal_id": "goal-001",
        "entry_capability_id": "cap-001",
        "inputs": {},
        "capabilities": [],
        "capability_edges": [],
        "branch_points": [],
        "deferred_destinations": [],
    }


@pytest.fixture()
def run_state_data() -> dict:
    return {
        "run_id": "run-001",
        "task_id": "task-001",
        "status": "CREATED",
        "current_capability_id": None,
        "current_step_id": None,
        "step_progress": {},
        "branch_decisions": {},
        "inputs": {},
        "produced_outputs": {},
        "clarification_request_id": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


@pytest.fixture()
def clarification_request_data() -> dict:
    return {
        "request_id": "req-001",
        "run_id": "run-001",
        "capability_id": "cap-001",
        "step_id": "step-001",
        "type": "ELEMENT_NOT_FOUND",
        "page_name": "Login Page",
        "current_url": "https://example.com/login",
        "expected_element": "Submit button",
        "visible_candidates": ["Login button", "Sign In button"],
        "screenshot_path": None,
        "failure_reason": "Element with label 'Submit' not found",
        "suggested_options": ["Click 'Login button'"],
        "created_at": _now(),
    }


@pytest.fixture()
def tool_definition_data() -> dict:
    return {
        "tool_id": "tool-001",
        "application_id": "app-001",
        "capability_id": "cap-001",
        "name": "login_tool",
        "entrypoint": "tools.login_tool:run",
        "version": "1.0.0",
        "enabled": True,
        "health": "UNKNOWN",
        "input_schema": {},
        "output_schema": {},
        "source_route_id": None,
    }


# ---------------------------------------------------------------------------
# 1. Serialization round-trip
# ---------------------------------------------------------------------------

class TestSerializationRoundTrip:
    def test_compiled_sop_round_trip(self, compiled_sop_data: dict) -> None:
        sop = CompiledSop.model_validate(compiled_sop_data)
        dumped = sop.model_dump()
        sop2 = CompiledSop.model_validate(dumped)
        assert sop == sop2

    def test_task_plan_round_trip(self, task_plan_data: dict) -> None:
        plan = TaskPlan.model_validate(task_plan_data)
        dumped = plan.model_dump()
        plan2 = TaskPlan.model_validate(dumped)
        assert plan == plan2

    def test_run_state_round_trip(self, run_state_data: dict) -> None:
        state = RunState.model_validate(run_state_data)
        dumped = state.model_dump()
        state2 = RunState.model_validate(dumped)
        assert state == state2

    def test_clarification_request_round_trip(self, clarification_request_data: dict) -> None:
        req = ClarificationRequest.model_validate(clarification_request_data)
        dumped = req.model_dump()
        req2 = ClarificationRequest.model_validate(dumped)
        assert req == req2

    def test_tool_definition_round_trip(self, tool_definition_data: dict) -> None:
        tool = ToolDefinition.model_validate(tool_definition_data)
        dumped = tool.model_dump()
        tool2 = ToolDefinition.model_validate(dumped)
        assert tool == tool2


# ---------------------------------------------------------------------------
# 2. Enum validation
# ---------------------------------------------------------------------------

class TestEnumValidation:
    @pytest.mark.parametrize("value", ["CLICK", "FILL", "OPEN", "VERIFY", "BRANCH"])
    def test_action_type_valid(self, value: str) -> None:
        assert ActionType(value) == ActionType(value)

    def test_action_type_invalid(self) -> None:
        with pytest.raises(ValueError):
            ActionType("INVALID")

    @pytest.mark.parametrize("value", ["CREATED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"])
    def test_run_status_valid(self, value: str) -> None:
        assert RunStatus(value) == RunStatus(value)

    def test_run_status_invalid(self) -> None:
        with pytest.raises(ValueError):
            RunStatus("INVALID")

    @pytest.mark.parametrize("value", ["PENDING", "RUNNING", "COMPLETED", "SKIPPED", "FAILED"])
    def test_step_status_valid(self, value: str) -> None:
        assert StepStatus(value) == StepStatus(value)

    def test_step_status_invalid(self) -> None:
        with pytest.raises(ValueError):
            StepStatus("INVALID")

    def test_clarification_type_invalid(self) -> None:
        with pytest.raises(ValueError):
            ClarificationType("INVALID")

    def test_tool_health_invalid(self) -> None:
        with pytest.raises(ValueError):
            ToolHealth("INVALID")


# ---------------------------------------------------------------------------
# 3. Invalid model rejection
# ---------------------------------------------------------------------------

class TestInvalidModelRejection:
    def test_extra_field_frozen_model(self, compiled_sop_data: dict) -> None:
        data = {**compiled_sop_data, "unknown_extra_field": "oops"}
        with pytest.raises(ValidationError):
            CompiledSop.model_validate(data)

    def test_wrong_type_step_id(self) -> None:
        data = {
            "step_id": 123,  # should be str
            "status": "PENDING",
        }
        with pytest.raises(ValidationError):
            # StepProgress expects step_id: str
            StepProgress.model_validate(data)

    def test_missing_required_field(self) -> None:
        # CompiledSop requires sop_id
        with pytest.raises(ValidationError):
            CompiledSop.model_validate({})

    def test_invalid_enum_value_in_model(self, run_state_data: dict) -> None:
        data = {**run_state_data, "status": "NOT_A_STATUS"}
        with pytest.raises(ValidationError):
            RunState.model_validate(data)


# ---------------------------------------------------------------------------
# 4. Frozen model mutation rejected
# ---------------------------------------------------------------------------

class TestFrozenModelMutation:
    def test_compiled_sop_is_immutable(self, compiled_sop_data: dict) -> None:
        sop = CompiledSop.model_validate(compiled_sop_data)
        with pytest.raises((ValidationError, TypeError)):
            sop.sop_id = "new-id"  # type: ignore[misc]

    def test_task_plan_is_immutable(self, task_plan_data: dict) -> None:
        plan = TaskPlan.model_validate(task_plan_data)
        with pytest.raises((ValidationError, TypeError)):
            plan.plan_id = "new-id"  # type: ignore[misc]

    def test_tool_definition_is_immutable(self, tool_definition_data: dict) -> None:
        tool = ToolDefinition.model_validate(tool_definition_data)
        with pytest.raises((ValidationError, TypeError)):
            tool.tool_id = "new-id"  # type: ignore[misc]

    def test_clarification_request_is_immutable(
        self, clarification_request_data: dict
    ) -> None:
        req = ClarificationRequest.model_validate(clarification_request_data)
        with pytest.raises((ValidationError, TypeError)):
            req.request_id = "new-id"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 5. Mutable model allows update
# ---------------------------------------------------------------------------

class TestMutableModelAllowsUpdate:
    def test_run_state_status_update(self, run_state_data: dict) -> None:
        state = RunState.model_validate(run_state_data)
        state.status = RunStatus.RUNNING
        assert state.status == RunStatus.RUNNING

    def test_run_state_step_id_update(self, run_state_data: dict) -> None:
        state = RunState.model_validate(run_state_data)
        state.current_step_id = "step-001"
        assert state.current_step_id == "step-001"

    def test_step_progress_status_update(self) -> None:
        progress = StepProgress(step_id="step-001")
        progress.status = StepStatus.RUNNING
        assert progress.status == StepStatus.RUNNING

    def test_step_progress_attempt_count_update(self) -> None:
        progress = StepProgress(step_id="step-001")
        progress.attempt_count = 2
        assert progress.attempt_count == 2


# ---------------------------------------------------------------------------
# 6. Phase 1 InterpretationResult model tests
# ---------------------------------------------------------------------------

class TestInterpretationResultModel:
    def test_interpretation_result_model_validate_from_fixture(self) -> None:
        """InterpretationResult.model_validate succeeds on the valid fixture."""
        fixture_path = FIXTURES_DIR / "valid_interpretation_result.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        result = InterpretationResult.model_validate(data)
        assert result.schema_version == "1.0"
        assert result.result_id == "result-001"
        assert len(result.capabilities) == 2
        assert len(result.inputs) == 2

    def test_interpretation_result_extra_field_rejected(self) -> None:
        """Extra fields on InterpretationResult are rejected (extra='forbid')."""
        fixture_path = FIXTURES_DIR / "valid_interpretation_result.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        data["unexpected_extra_field"] = "should_fail"
        with pytest.raises(ValidationError):
            InterpretationResult.model_validate(data)

    def test_interpretation_result_missing_required_field_rejected(self) -> None:
        """InterpretationResult rejects missing required fields."""
        with pytest.raises(ValidationError):
            InterpretationResult.model_validate({"schema_version": "1.0"})

    def test_interpretation_result_round_trip(self) -> None:
        """InterpretationResult serialises and deserialises without data loss."""
        fixture_path = FIXTURES_DIR / "valid_interpretation_result.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        result1 = InterpretationResult.model_validate(data)
        result2 = InterpretationResult.model_validate(result1.model_dump(mode="json"))
        assert result1 == result2

    def test_interpretation_result_dependency_cycle_fixture_loads(self) -> None:
        """The dependency cycle fixture loads into the model (structural check only)."""
        fixture_path = FIXTURES_DIR / "invalid_dependency_cycle.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        result = InterpretationResult.model_validate(data)
        # Model loads OK — the cycle is a semantic error caught by the validator
        assert result.schema_version == "1.0"
        assert len(result.capabilities) == 1
        cap = result.capabilities[0]
        # Both steps depend on each other — confirm the deps are there
        step_ids = {s.step_id for s in cap.steps}
        assert "step_A" in step_ids
        assert "step_B" in step_ids

    def test_interpretation_result_deferred_branch_fixture_loads(self) -> None:
        """The deferred branch fixture loads; deferred cap has steps=[]."""
        fixture_path = FIXTURES_DIR / "deferred_branch.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        result = InterpretationResult.model_validate(data)
        deferred = [c for c in result.capabilities if c.is_deferred]
        assert len(deferred) == 1
        assert deferred[0].steps == []


# ---------------------------------------------------------------------------
# 7. New type tests — ConditionSpec, PlannedStep (correction pass)
# ---------------------------------------------------------------------------

class TestConditionSpec:
    def test_condition_spec_valid_equals(self) -> None:
        spec = ConditionSpec(
            source_key="login_status",
            operator=ConditionOperator.EQUALS,
            expected_value="success",
        )
        assert spec.operator == ConditionOperator.EQUALS
        assert spec.expected_value == "success"
        assert spec.source_key == "login_status"

    def test_condition_spec_true_no_expected_value(self) -> None:
        spec = ConditionSpec(source_key="is_logged_in", operator=ConditionOperator.TRUE)
        assert spec.expected_value is None

    def test_condition_spec_round_trip(self) -> None:
        spec = ConditionSpec(
            source_key="status",
            operator=ConditionOperator.CONTAINS,
            expected_value="ok",
        )
        data = spec.model_dump(mode="json")
        spec2 = ConditionSpec.model_validate(data)
        assert spec == spec2

    def test_condition_operator_all_values_valid(self) -> None:
        for val in ("EQUALS", "NOT_EQUALS", "TRUE", "FALSE", "EXISTS", "NOT_EXISTS", "CONTAINS"):
            op = ConditionOperator(val)
            assert op.value == val

    def test_condition_spec_is_immutable(self) -> None:
        spec = ConditionSpec(source_key="k", operator=ConditionOperator.EXISTS)
        with pytest.raises((ValidationError, TypeError)):
            spec.source_key = "other"  # type: ignore[misc]


class TestPlannedStep:
    def test_planned_step_serializes(self) -> None:
        step = PlannedStep(
            capability_id="cap1",
            capability_name="Login",
            application_id="crm",
            step_id="s1",
            sequence=1,
            action=ActionType.CLICK,
            element_name="btn",
            element_type=ElementType.BUTTON,
        )
        data = step.model_dump(mode="json")
        assert data["step_id"] == "s1"
        assert data["capability_id"] == "cap1"
        assert data["action"] == "CLICK"

    def test_planned_step_round_trip(self) -> None:
        step = PlannedStep(
            capability_id="cap1",
            capability_name="Login",
            application_id="crm",
            step_id="s1",
            sequence=1,
            action=ActionType.OPEN,
            element_name="page",
            element_type=ElementType.PAGE,
            value="https://example.com",
        )
        data = step.model_dump(mode="json")
        step2 = PlannedStep.model_validate(data)
        assert step == step2

    def test_planned_step_with_outcome(self) -> None:
        outcome = PlannedOutcome(
            outcome_id="out1",
            description="Done",
            is_terminal=True,
            is_success=True,
        )
        step = PlannedStep(
            capability_id="cap1",
            capability_name="Login",
            application_id="crm",
            step_id="s1",
            sequence=1,
            action=ActionType.CLICK,
            element_name="btn",
            element_type=ElementType.BUTTON,
            outcomes=[outcome],
        )
        assert len(step.outcomes) == 1
        assert step.outcomes[0].outcome_id == "out1"


# ---------------------------------------------------------------------------
# 8. GoalDefinition model tests (new in Phase 2)
# ---------------------------------------------------------------------------

class TestGoalDefinition:
    def test_goal_definition_round_trip(self) -> None:
        goal = GoalDefinition(
            goal_id="create_contact",
            name="Create Contact",
            description="Creates a contact record.",
            entry_capability_id="login_cap",
            capability_ids=["login_cap", "create_cap"],
            aliases=["create-contact", "new-contact"],
            required_inputs=["email_address"],
            expected_outputs=["contact_id"],
            assumptions=["User is logged in"],
        )
        data = goal.model_dump(mode="json")
        goal2 = GoalDefinition.model_validate(data)
        assert goal == goal2

    def test_goal_definition_no_inference_field(self) -> None:
        goal = GoalDefinition(
            goal_id="g1",
            name="G1",
            description="test",
            entry_capability_id="cap1",
            capability_ids=["cap1"],
        )
        data = goal.model_dump(mode="json")
        assert "inference" not in data

    def test_goal_definition_is_immutable(self) -> None:
        goal = GoalDefinition(
            goal_id="g1",
            name="G1",
            description="test",
            entry_capability_id="cap1",
            capability_ids=["cap1"],
        )
        with pytest.raises((ValidationError, TypeError)):
            goal.goal_id = "other"  # type: ignore[misc]

    def test_goal_definition_aliases_default_empty(self) -> None:
        goal = GoalDefinition(
            goal_id="g1",
            name="G1",
            description="test",
            entry_capability_id="cap1",
            capability_ids=["cap1"],
        )
        assert goal.aliases == []


# ---------------------------------------------------------------------------
# 9. WaitConditionSpec model tests (new in Phase 2)
# ---------------------------------------------------------------------------

class TestWaitConditionSpec:
    def test_wait_condition_spec_page_dom_ready(self) -> None:
        spec = WaitConditionSpec(type=WaitConditionType.PAGE_DOM_READY)
        assert spec.type == WaitConditionType.PAGE_DOM_READY
        assert spec.element_name is None
        assert spec.timeout_seconds == 30.0

    def test_wait_condition_spec_element_visible(self) -> None:
        spec = WaitConditionSpec(
            type=WaitConditionType.ELEMENT_VISIBLE,
            element_name="submit_button",
            timeout_seconds=10.0,
        )
        assert spec.type == WaitConditionType.ELEMENT_VISIBLE
        assert spec.element_name == "submit_button"
        assert spec.timeout_seconds == 10.0

    def test_wait_condition_spec_round_trip(self) -> None:
        spec = WaitConditionSpec(
            type=WaitConditionType.URL_CONTAINS,
            expected_value="/dashboard",
            timeout_seconds=15.0,
        )
        data = spec.model_dump(mode="json")
        spec2 = WaitConditionSpec.model_validate(data)
        assert spec == spec2

    def test_wait_condition_type_all_values(self) -> None:
        for val in (
            "PAGE_DOM_READY", "URL_EQUALS", "URL_CONTAINS", "ELEMENT_VISIBLE",
            "ELEMENT_HIDDEN", "ELEMENT_ENABLED", "ELEMENT_TEXT_EQUALS",
            "ELEMENT_TEXT_CONTAINS", "ELEMENT_VALUE_EQUALS", "DOWNLOAD_COMPLETED",
            "FIXED_DELAY",
        ):
            wct = WaitConditionType(val)
            assert wct.value == val

    def test_wait_condition_spec_is_immutable(self) -> None:
        spec = WaitConditionSpec(type=WaitConditionType.FIXED_DELAY)
        with pytest.raises((ValidationError, TypeError)):
            spec.timeout_seconds = 999.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 10. PlannedCapability model tests (new in Phase 2)
# ---------------------------------------------------------------------------

class TestPlannedCapabilityModel:
    def test_planned_capability_round_trip(self) -> None:
        cap = PlannedCapability(
            capability_id="login_cap",
            name="Login",
            application_id="crm",
        )
        data = cap.model_dump(mode="json")
        cap2 = PlannedCapability.model_validate(data)
        assert cap == cap2

    def test_planned_capability_is_deferred_default_false(self) -> None:
        cap = PlannedCapability(
            capability_id="c1",
            name="C1",
            application_id="app1",
        )
        assert cap.is_deferred is False
        assert cap.is_tool_candidate is False

    def test_planned_capability_with_steps(self) -> None:
        step = PlannedStep(
            capability_id="c1",
            capability_name="C1",
            application_id="app1",
            step_id="s1",
            sequence=1,
            action=ActionType.CLICK,
            element_name="btn",
            element_type=ElementType.BUTTON,
        )
        cap = PlannedCapability(
            capability_id="c1",
            name="C1",
            application_id="app1",
            steps=[step],
        )
        assert len(cap.steps) == 1
        assert cap.steps[0].step_id == "s1"

    def test_planned_capability_is_immutable(self) -> None:
        cap = PlannedCapability(
            capability_id="c1",
            name="C1",
            application_id="app1",
        )
        with pytest.raises((ValidationError, TypeError)):
            cap.capability_id = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 11. is_default field and scalar expected_value (new in Phase 2)
# ---------------------------------------------------------------------------

class TestIsDefaultField:
    def test_planned_outcome_is_default_false_by_default(self) -> None:
        outcome = PlannedOutcome(
            outcome_id="o1",
            description="Success",
            is_terminal=True,
            is_success=True,
        )
        assert outcome.is_default is False

    def test_planned_outcome_is_default_true(self) -> None:
        outcome = PlannedOutcome(
            outcome_id="o1",
            description="Default fallback",
            is_terminal=False,
            is_success=False,
            is_default=True,
        )
        assert outcome.is_default is True

    def test_condition_spec_int_expected_value(self) -> None:
        spec = ConditionSpec(
            source_key="count",
            operator=ConditionOperator.EQUALS,
            expected_value=42,
        )
        assert spec.expected_value == 42
        data = spec.model_dump(mode="json")
        spec2 = ConditionSpec.model_validate(data)
        assert spec2.expected_value == 42

    def test_condition_spec_float_expected_value(self) -> None:
        spec = ConditionSpec(
            source_key="ratio",
            operator=ConditionOperator.EQUALS,
            expected_value=0.95,
        )
        assert spec.expected_value == 0.95

    def test_condition_spec_bool_expected_value(self) -> None:
        spec = ConditionSpec(
            source_key="flag",
            operator=ConditionOperator.EQUALS,
            expected_value=True,
        )
        assert spec.expected_value is True


# ---------------------------------------------------------------------------
# 12. TaskIntent model tests (new in Phase 2)
# ---------------------------------------------------------------------------

class TestTaskIntentModel:
    def test_task_intent_round_trip(self) -> None:
        intent = TaskIntent(
            intent_id="intent-001",
            schema_version="1.0",
            requested_goal="create_contact",
            preferred_sop_id="crm-sop",
            inputs={"email_address": "user@example.com"},
            constraints=["headless=false"],
            created_at=datetime.now(UTC),
        )
        data = intent.model_dump(mode="json")
        intent2 = TaskIntent.model_validate(data)
        assert intent == intent2

    def test_task_intent_defaults(self) -> None:
        intent = TaskIntent(
            intent_id="intent-002",
            requested_goal="login",
            created_at=datetime.now(UTC),
        )
        assert intent.schema_version == "1.0"
        assert intent.preferred_sop_id is None
        assert intent.application_hints == []
        assert intent.inputs == {}
        assert intent.constraints == []

    def test_task_intent_is_immutable(self) -> None:
        intent = TaskIntent(
            intent_id="intent-003",
            requested_goal="login",
            created_at=datetime.now(UTC),
        )
        with pytest.raises((ValidationError, TypeError)):
            intent.intent_id = "other"  # type: ignore[misc]
