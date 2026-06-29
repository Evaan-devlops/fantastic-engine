"""Runtime command queue and step result models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from sop_automation.models.common import FrozenModel


class RuntimeCommandType(str, Enum):
    START_RUN = "START_RUN"
    CONTINUE_RUN = "CONTINUE_RUN"
    CANCEL_RUN = "CANCEL_RUN"


class StartRunPayload(FrozenModel):
    intent_path: str
    plan_id: str | None = None


class ContinueRunPayload(FrozenModel):
    run_id: str


class CancelRunPayload(FrozenModel):
    run_id: str


class RuntimeCommand(FrozenModel):
    command_id: str
    command_type: RuntimeCommandType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AckStatus(str, Enum):
    RECEIVED = "RECEIVED"
    STARTED = "STARTED"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class CommandAcknowledgement(FrozenModel):
    command_id: str
    run_id: str | None = None
    status: AckStatus
    message: str | None = None
    created_at: datetime


class StepResult(FrozenModel):
    step_id: str
    success: bool
    value: str | None = None
    current_url: str | None = None
    error_message: str | None = None
    screenshot_path: str | None = None
    locator_candidates: list[str] = Field(default_factory=list)
    locator_attempts: list[dict[str, Any]] = Field(default_factory=list)
