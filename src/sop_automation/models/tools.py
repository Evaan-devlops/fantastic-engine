"""Tool definition and tool build request models."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from sop_automation.models.common import FrozenModel, ToolHealth


class ToolDefinition(FrozenModel):
    """A registered deterministic capability tool in the catalogue."""

    tool_id: str
    application_id: str
    capability_id: str
    name: str
    entrypoint: str
    version: str
    enabled: bool = True
    health: ToolHealth = ToolHealth.UNKNOWN
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    source_route_id: str | None = None


class ToolBuildRequest(FrozenModel):
    """A validated request for Copilot to generate a capability tool."""

    request_id: str
    run_id: str
    sop_id: str
    application_id: str
    capability_id: str
    completed_step_ids: list[str] = Field(default_factory=list)
    route_id: str
    route_sha256: str
    required_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    postcondition_evidence: list[str] = Field(default_factory=list)
    target_package_path: str
    created_at: datetime
