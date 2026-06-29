"""Task intent and task plan models."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import Field

from sop_automation.models.common import ActionType, ElementType, FrozenModel
from sop_automation.models.sop import ConditionSpec, RetryPolicy, WaitConditionSpec


class TaskIntent(FrozenModel):
    """A validated user request to execute a goal using a SOP."""

    intent_id: str
    request_id: str = ""
    raw_request_sha256: str = ""
    schema_version: str = "1.0"
    requested_goal: str
    preferred_sop_id: str | None = None
    application_hints: list[str] = Field(default_factory=list)
    inputs: dict[str, str] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    created_at: datetime


class TaskIntentInterpretationRequest(FrozenModel):
    request_id: str
    schema_version: str = "1.0"
    raw_request: str
    raw_request_sha256: str
    available_sop_goal_summaries: list[dict[str, Any]]
    required_output_schema: dict[str, Any]
    created_at: datetime


class PlannedOutcome(FrozenModel):
    """A typed outcome within a planned step."""

    outcome_id: str
    description: str
    is_terminal: bool
    is_success: bool
    condition: ConditionSpec | None = None
    is_default: bool = False
    next_capability_id: str | None = None


class PlannedStep(FrozenModel):
    """A typed planned step."""

    capability_id: str
    capability_name: str
    application_id: str
    step_id: str
    sequence: int
    action: ActionType
    element_name: str
    element_type: ElementType
    value: str | None = None
    wait_condition: WaitConditionSpec | None = None
    postcondition: WaitConditionSpec | None = None
    wait_condition_notes: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    outcomes: list[PlannedOutcome] = Field(default_factory=list)
    source_line: int | None = None
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class PlannedCapability(FrozenModel):
    """A planned capability grouping its steps."""

    capability_id: str
    name: str
    application_id: str
    steps: list[PlannedStep] = Field(default_factory=list)
    is_deferred: bool = False
    is_tool_candidate: bool = False


class BranchPoint(FrozenModel):
    """A step identified as a branch point with all its possible outcomes."""

    step_id: str
    capability_id: str
    outcomes: list[PlannedOutcome]


class CapabilityEdge(FrozenModel):
    """A directed edge between capabilities in the execution graph."""

    from_capability_id: str | None
    to_capability_id: str
    is_conditional: bool = False
    condition: ConditionSpec | None = None


class TaskPlan(FrozenModel):
    """An execution plan derived from a compiled SOP and a selected goal."""

    plan_id: str
    sop_id: str
    goal_id: str
    entry_capability_id: str
    capabilities: list[PlannedCapability] = Field(default_factory=list)
    capability_edges: list[CapabilityEdge] = Field(default_factory=list)
    branch_points: list[BranchPoint] = Field(default_factory=list)
    inputs: dict[str, str] = Field(default_factory=dict)
    deferred_destinations: list[str] = Field(default_factory=list)
    created_at: datetime


@dataclass
class RunSession:
    """Mutable container for an active browser run — owned by RuntimeHost."""

    run_id: str
    plan: "TaskPlan"
    manager: Any
    context: Any
    page: Any
    execution_task: Any
    created_at: datetime
