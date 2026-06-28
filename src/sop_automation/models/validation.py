"""Validation report models for SOP interpretation results."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field

from sop_automation.models.common import FrozenModel


class ValidationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class ValidationIssue(FrozenModel):
    severity: ValidationSeverity
    rule_id: str
    message: str
    location: str | None = None    # dot-path, e.g. "capability.auth.step.step_001"


class ValidationReport(FrozenModel):
    report_id: str
    result_id: str
    request_id: str
    schema_version: str
    passed: bool                   # True only when no ERROR-severity issues
    issues: list[ValidationIssue] = Field(default_factory=list)
    validated_at: datetime
    request_sha256: str     # SHA256 of interpretation_request.json file content at validation time
    result_sha256: str      # SHA256 of interpretation_result.json file content at validation time
