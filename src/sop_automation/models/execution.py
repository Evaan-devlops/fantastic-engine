"""Runtime execution state models — mutable, updated through service methods."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from sop_automation.models.common import MutableModel, RunStatus, StepStatus


class StepProgress(MutableModel):
    """Mutable execution record for a single SOP step within a run."""

    step_id: str
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    attempt_count: int = 0
    current_url: str | None = None
    screenshot_paths: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    selected_outcome_id: str | None = None


class RunState(MutableModel):
    """Mutable state of a task run — persisted atomically after each transition."""

    run_id: str
    task_id: str
    status: RunStatus = RunStatus.CREATED
    current_capability_id: str | None = None
    current_step_id: str | None = None
    step_progress: dict[str, StepProgress] = Field(default_factory=dict)
    branch_decisions: dict[str, str] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    produced_outputs: dict[str, Any] = Field(default_factory=dict)
    clarification_request_id: str | None = None
    created_at: datetime
    updated_at: datetime
