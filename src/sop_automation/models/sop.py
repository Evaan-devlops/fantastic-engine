"""SOP source, interpretation, step, capability, and compiled SOP models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Union

from pydantic import Field, field_validator

from sop_automation.models.common import (
    ActionType,
    ElementType,
    FrozenModel,
    SourceFormat,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DetectedSectionKind(str, Enum):
    HEADING = "HEADING"
    NUMBERED_LIST = "NUMBERED_LIST"
    BULLET_LIST = "BULLET_LIST"
    PARAGRAPH = "PARAGRAPH"
    URL_LINE = "URL_LINE"
    TOOL_MARKER = "TOOL_MARKER"
    DEFERRED_MARKER = "DEFERRED_MARKER"
    CONDITION_LINE = "CONDITION_LINE"
    BRANCH_DESTINATION = "BRANCH_DESTINATION"


class InferenceSource(str, Enum):
    USER_TEXT = "USER_TEXT"
    EXPLICIT_MARKER = "EXPLICIT_MARKER"
    HEURISTIC = "HEURISTIC"
    LLM_INFERENCE = "LLM_INFERENCE"


class ConditionOperator(str, Enum):
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    TRUE = "TRUE"
    FALSE = "FALSE"
    EXISTS = "EXISTS"
    NOT_EXISTS = "NOT_EXISTS"
    CONTAINS = "CONTAINS"


class WaitConditionType(str, Enum):
    PAGE_DOM_READY = "PAGE_DOM_READY"
    URL_EQUALS = "URL_EQUALS"
    URL_CONTAINS = "URL_CONTAINS"
    ELEMENT_VISIBLE = "ELEMENT_VISIBLE"
    ELEMENT_HIDDEN = "ELEMENT_HIDDEN"
    ELEMENT_ENABLED = "ELEMENT_ENABLED"
    ELEMENT_TEXT_EQUALS = "ELEMENT_TEXT_EQUALS"
    ELEMENT_TEXT_CONTAINS = "ELEMENT_TEXT_CONTAINS"
    ELEMENT_VALUE_EQUALS = "ELEMENT_VALUE_EQUALS"
    DOWNLOAD_COMPLETED = "DOWNLOAD_COMPLETED"
    FIXED_DELAY = "FIXED_DELAY"


# ---------------------------------------------------------------------------
# Supporting models
# ---------------------------------------------------------------------------

class ConditionSpec(FrozenModel):
    source_key: str
    operator: ConditionOperator
    expected_value: Union[str, int, float, bool, None] = None


class WaitConditionSpec(FrozenModel):
    type: WaitConditionType
    element_name: str | None = None
    element_type: str | None = None
    expected_value: str | None = None
    timeout_seconds: float = 30.0
    poll_interval_seconds: float = 0.5


class DetectedSection(FrozenModel):
    kind: DetectedSectionKind
    line_start: int
    line_end: int
    text: str


class InferenceMetadata(FrozenModel):
    field_name: str
    proposed_value: str
    confidence: float
    source: InferenceSource
    evidence_lines: list[int]

    @field_validator("confidence")
    @classmethod
    def _confidence_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v


class InputDefinition(FrozenModel):
    name: str
    description: str
    required: bool = True
    default_value: str | None = None


class OutputDefinition(FrozenModel):
    name: str
    description: str


class OutcomeProposal(FrozenModel):
    outcome_id: str
    description: str
    is_terminal: bool
    is_success: bool
    condition: ConditionSpec | None = None
    is_default: bool = False
    next_capability_id: str | None = None


class StepProposal(FrozenModel):
    step_id: str
    sequence: int
    action: ActionType
    element_name: str
    element_type: ElementType
    value: str | None = None
    wait_condition: WaitConditionSpec | None = None
    wait_condition_notes: str | None = None
    expected_outcomes: list[OutcomeProposal] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    notes: str | None = None
    source_line: int | None = None
    inference: list[InferenceMetadata] = Field(default_factory=list)


class CapabilityProposal(FrozenModel):
    capability_id: str
    name: str
    application_id: str
    description: str
    steps: list[StepProposal] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    is_deferred: bool = False
    is_tool_candidate: bool = False
    inference: list[InferenceMetadata] = Field(default_factory=list)


class GoalProposal(FrozenModel):
    goal_id: str
    name: str
    description: str
    entry_capability_id: str = ""
    capability_ids: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    inference: list[InferenceMetadata] = Field(default_factory=list)


class ApplicationProposal(FrozenModel):
    application_id: str
    name: str
    url_patterns: list[str] = Field(default_factory=list)
    inference: list[InferenceMetadata] = Field(default_factory=list)


class SourceReference(FrozenModel):
    source_path: str
    source_sha256: str
    request_id: str


# ---------------------------------------------------------------------------
# SopSource — clean schema
# ---------------------------------------------------------------------------

class SopSource(FrozenModel):
    sop_id: str
    source_format: SourceFormat
    source_path: str
    preserved_path: str
    source_sha256: str
    created_at: datetime


# ---------------------------------------------------------------------------
# InterpretationRequest
# ---------------------------------------------------------------------------

class InterpretationRequest(FrozenModel):
    request_id: str
    schema_version: str = "1.0"
    sop_id: str
    source_path: str
    source_format: SourceFormat
    source_sha256: str
    created_at: datetime
    normalized_text: str
    sections: list[DetectedSection] = Field(default_factory=list)
    detected_urls: list[str] = Field(default_factory=list)
    detected_placeholders: list[str] = Field(default_factory=list)
    capability_hints: list[str] = Field(default_factory=list)
    possible_condition_lines: list[int] = Field(default_factory=list)
    possible_deferred_lines: list[int] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# InterpretationResult
# ---------------------------------------------------------------------------

class InterpretationResult(FrozenModel):
    schema_version: str
    result_id: str
    request_id: str
    source_reference: SourceReference
    applications: list[ApplicationProposal] = Field(default_factory=list)
    goals: list[GoalProposal] = Field(default_factory=list)
    capabilities: list[CapabilityProposal] = Field(default_factory=list)
    inputs: list[InputDefinition] = Field(default_factory=list)
    outputs: list[OutputDefinition] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    created_at: datetime


# ---------------------------------------------------------------------------
# Compiled SOP models — clean schema
# ---------------------------------------------------------------------------

class OutcomeRule(FrozenModel):
    outcome_id: str
    description: str
    is_terminal: bool = False
    is_success: bool = True
    condition: ConditionSpec | None = None
    is_default: bool = False
    next_capability_id: str | None = None


class RetryPolicy(FrozenModel):
    max_attempts: int = 2
    retryable_error_codes: list[str] = Field(default_factory=list)
    delay_seconds: float = 1.0


class SopStep(FrozenModel):
    step_id: str
    sequence: int
    action: ActionType
    element_name: str
    element_type: ElementType
    application_id: str
    capability_id: str
    value: str | None = None
    wait_condition: WaitConditionSpec | None = None
    wait_condition_notes: str | None = None
    expected_outcomes: list[OutcomeRule] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    notes: str | None = None
    source_line: int | None = None
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class CapabilityDefinition(FrozenModel):
    capability_id: str
    name: str
    application_id: str
    description: str
    steps: list[SopStep] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    is_deferred: bool = False
    is_tool_candidate: bool = False


class GoalDefinition(FrozenModel):
    """Compiled goal — no inference metadata."""
    goal_id: str
    name: str
    description: str
    entry_capability_id: str
    capability_ids: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class CompiledSop(FrozenModel):
    sop_id: str
    schema_version: str = "1.0"
    title: str
    source: SopSource
    applications: list[str] = Field(default_factory=list)
    goals: dict[str, GoalDefinition] = Field(default_factory=dict)
    capabilities: list[CapabilityDefinition] = Field(default_factory=list)
    inputs: dict[str, InputDefinition] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    compiled_at: datetime
    compiled_content_sha256: str = ""
