"""Service: prepare and validate task intents."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sop_automation.errors import StorageError
from sop_automation.errors import ValidationError as SopValidationError
from sop_automation.models.task import TaskIntent
from sop_automation.models.validation import ValidationIssue, ValidationReport, ValidationSeverity
from sop_automation.storage.json_store import new_id, read_json, utc_now, write_json_atomic
from sop_automation.storage.paths import resolve_path

ERROR = ValidationSeverity.ERROR
WARNING = ValidationSeverity.WARNING

_KV_RE = re.compile(r'^([a-zA-Z_]\w*)\s*=\s*(.+)$')


@dataclass
class TaskIntentPrepareResult:
    intent: TaskIntent
    intent_path: Path


@dataclass
class TaskIntentValidateResult:
    report: ValidationReport
    passed: bool


class TaskIntentService:
    """Prepare and validate TaskIntent objects."""

    def prepare_intent(
        self,
        request_text: str,
        workspace_root: Path,
        sop_id: str | None = None,
    ) -> TaskIntentPrepareResult:
        inputs: dict[str, str] = {}
        application_hints: list[str] = []
        constraints: list[str] = []
        requested_goal = ""

        for line in request_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = _KV_RE.match(line)
            if m:
                key, value = m.group(1), m.group(2).strip()
                if key == "goal":
                    requested_goal = value
                elif key == "sop_id":
                    sop_id = value
                elif key == "application":
                    application_hints.append(value)
                elif key == "constraint":
                    constraints.append(value)
                else:
                    inputs[key] = value
            elif not requested_goal:
                requested_goal = line

        if not requested_goal:
            raise SopValidationError("request_text must specify a goal.")

        intent = TaskIntent(
            intent_id=new_id(),
            schema_version="1.0",
            requested_goal=requested_goal,
            preferred_sop_id=sop_id,
            application_hints=application_hints,
            inputs=inputs,
            constraints=constraints,
            created_at=utc_now(),
        )

        generated_dir = resolve_path(workspace_root, "generated")
        generated_dir.mkdir(parents=True, exist_ok=True)
        intent_path = resolve_path(workspace_root, f"generated/{intent.intent_id}_task_intent.json")
        write_json_atomic(intent_path, intent.model_dump(mode="json"))

        return TaskIntentPrepareResult(intent=intent, intent_path=intent_path)

    def validate_intent(
        self,
        intent: TaskIntent,
        workspace_root: Path,
    ) -> TaskIntentValidateResult:
        issues: list[ValidationIssue] = []

        if intent.schema_version != "1.0":
            issues.append(ValidationIssue(
                severity=ERROR,
                rule_id="INTENT_SCHEMA_VERSION",
                message=f"schema_version must be '1.0', got {intent.schema_version!r}",
            ))

        if not intent.requested_goal.strip():
            issues.append(ValidationIssue(
                severity=ERROR,
                rule_id="INTENT_GOAL_REQUIRED",
                message="requested_goal must not be empty",
            ))

        if intent.preferred_sop_id:
            compiled_path = resolve_path(
                workspace_root, f"compiled/{intent.preferred_sop_id}/compiled_sop.json"
            )
            if not compiled_path.exists():
                issues.append(ValidationIssue(
                    severity=ERROR,
                    rule_id="INTENT_SOP_EXISTS",
                    message=f"preferred_sop_id {intent.preferred_sop_id!r} not found in compiled SOPs",
                ))

        passed = not any(i.severity == ERROR for i in issues)
        report = ValidationReport(
            report_id=new_id(),
            result_id=intent.intent_id,
            request_id=intent.intent_id,
            schema_version="1.0",
            passed=passed,
            issues=issues,
            validated_at=utc_now(),
            request_sha256="",
            result_sha256="",
        )

        return TaskIntentValidateResult(report=report, passed=passed)
