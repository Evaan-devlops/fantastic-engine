"""Clarification request, resolution, and remembered resolution models."""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from sop_automation.models.common import ClarificationType, ElementType, FrozenModel


class ClarificationRequest(FrozenModel):
    """A request for human input raised when execution is blocked."""

    request_id: str
    run_id: str
    capability_id: str
    step_id: str
    type: ClarificationType
    page_name: str
    current_url: str
    expected_element: str
    visible_candidates: list[str] = Field(default_factory=list)
    screenshot_path: str | None = None
    failure_reason: str
    suggested_options: list[str] = Field(default_factory=list)
    created_at: datetime


class Resolution(FrozenModel):
    """A human-provided resolution to a clarification request."""

    resolution_id: str
    request_id: str
    action: str
    selected_element: str | None = None
    selected_element_type: ElementType | None = None
    value: str | None = None
    notes: str | None = None
    reusable: bool = False
    created_at: datetime


class RememberedResolution(FrozenModel):
    """A verified resolution stored for automatic reuse in future runs."""

    application_id: str
    capability_id: str
    page_signature: str
    expected_element: str
    working_element: str
    working_element_type: ElementType
    action: str
    success_count: int = 1
    last_verified_at: datetime
