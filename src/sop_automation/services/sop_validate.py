"""Service: validate an InterpretationResult against rules."""
from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from sop_automation.errors import ValidationError as SopValidationError
from sop_automation.models.common import ActionType, ElementType
from sop_automation.models.sop import InterpretationRequest, InterpretationResult
from sop_automation.models.validation import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from sop_automation.storage.json_store import (
    new_id,
    read_json,
    sha256_of_str,
    utc_now,
    write_json_atomic,
)

ERROR = ValidationSeverity.ERROR
WARNING = ValidationSeverity.WARNING

_CRED_ASSIGNMENT_RE = re.compile(
    r'\b(password|passwd|token|otp|secret|cookie|bearer|api[_-]?key)\s*[:=]\s*(?!\{\{)[^\s\{\}]{4,}',
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(r'\{\{input\.(\w+)\}\}')
_BLOCKING_KEYWORDS = re.compile(r'\b(blocking|must)\b', re.IGNORECASE)


@dataclass
class SopValidateResult:
    report: ValidationReport
    report_path: Path


class SopValidateService:
    def validate(self, result_path: Path, workspace_root: Path) -> SopValidateResult:
        result_dir = result_path.parent

        # REQUEST_REQUIRED — interpretation_request.json must exist
        request_path = result_dir / "interpretation_request.json"
        if not request_path.exists():
            raise SopValidationError(
                f"interpretation_request.json not found at {request_path}. "
                "Run 'sop prepare' first."
            )
        try:
            request = InterpretationRequest.model_validate(read_json(request_path))
        except Exception as exc:
            raise SopValidationError(f"Could not parse interpretation_request.json: {exc}") from exc

        # Load result
        try:
            raw_result = read_json(result_path)
            result = InterpretationResult.model_validate(raw_result)
        except Exception as exc:
            raise SopValidationError(f"Could not parse interpretation result: {exc}") from exc

        issues: list[ValidationIssue] = []
        cap_map = {c.capability_id: c for c in result.capabilities}
        step_ids_global: set[str] = set()
        input_names = {inp.name for inp in result.inputs}
        app_ids = {a.application_id for a in result.applications}

        # R01 SCHEMA_VERSION
        if result.schema_version != "1.0":
            issues.append(ValidationIssue(
                severity=ERROR,
                rule_id="SCHEMA_VERSION",
                message=f"schema_version must be '1.0', got {result.schema_version!r}",
            ))

        # R02 UNIQUE_CAPABILITY_IDS
        seen_caps: set[str] = set()
        for cap in result.capabilities:
            if cap.capability_id in seen_caps:
                issues.append(ValidationIssue(
                    severity=ERROR,
                    rule_id="UNIQUE_CAPABILITY_IDS",
                    message=f"Duplicate capability_id: {cap.capability_id!r}",
                ))
            seen_caps.add(cap.capability_id)

        # R03 UNIQUE_STEP_IDS (global across all capabilities)
        for cap in result.capabilities:
            for step in cap.steps:
                if step.step_id in step_ids_global:
                    issues.append(ValidationIssue(
                        severity=ERROR,
                        rule_id="UNIQUE_STEP_IDS",
                        message=f"Duplicate step_id: {step.step_id!r}",
                        location=f"capability.{cap.capability_id}",
                    ))
                step_ids_global.add(step.step_id)

        for cap in result.capabilities:
            cap_loc = f"capability.{cap.capability_id}"
            step_ids_in_cap = {s.step_id for s in cap.steps}

            # R04 CAPABILITY_HAS_STEPS
            if not cap.is_deferred and not cap.steps:
                issues.append(ValidationIssue(
                    severity=ERROR,
                    rule_id="CAPABILITY_HAS_STEPS",
                    message="Non-deferred capability has no steps",
                    location=cap_loc,
                ))

            # CAPABILITY_APPLICATION_EXISTS
            if cap.application_id not in app_ids:
                issues.append(ValidationIssue(
                    severity=ERROR,
                    rule_id="CAPABILITY_APPLICATION_EXISTS",
                    message=f"Capability {cap.capability_id!r} references unknown application {cap.application_id!r}",
                    location=cap_loc,
                ))

            # CAPABILITY_INPUTS_RESOLVE
            for inp_name in cap.inputs:
                if inp_name not in input_names:
                    issues.append(ValidationIssue(
                        severity=ERROR,
                        rule_id="CAPABILITY_INPUTS_RESOLVE",
                        message=f"Capability {cap.capability_id!r} references undeclared input {inp_name!r}",
                        location=cap_loc,
                    ))

            for step in cap.steps:
                step_loc = f"{cap_loc}.step.{step.step_id}"

                # R05 VALID_ACTIONS
                try:
                    ActionType(step.action)
                except ValueError:
                    issues.append(ValidationIssue(
                        severity=ERROR,
                        rule_id="VALID_ACTIONS",
                        message=f"Unknown action: {step.action!r}",
                        location=step_loc,
                    ))

                # R06 VALID_ELEMENT_TYPES
                try:
                    ElementType(step.element_type)
                except ValueError:
                    issues.append(ValidationIssue(
                        severity=ERROR,
                        rule_id="VALID_ELEMENT_TYPES",
                        message=f"Unknown element_type: {step.element_type!r}",
                        location=step_loc,
                    ))

                # R07 REQUIRED_FIELDS: FILL needs value
                if step.action == ActionType.FILL and not step.value:
                    issues.append(ValidationIssue(
                        severity=ERROR,
                        rule_id="REQUIRED_FIELDS",
                        message="FILL action requires a value",
                        location=step_loc,
                    ))

                # R08 REQUIRED_FIELDS: CLICK/PRESS needs element_name
                if step.action in (ActionType.CLICK, ActionType.PRESS) and not step.element_name:
                    issues.append(ValidationIssue(
                        severity=ERROR,
                        rule_id="REQUIRED_FIELDS",
                        message=f"{step.action} action requires element_name",
                        location=step_loc,
                    ))

                # R09 VALID_PLACEHOLDERS
                for field_text in [step.value or ""]:
                    for ph_name in _PLACEHOLDER_RE.findall(field_text):
                        if ph_name not in input_names:
                            issues.append(ValidationIssue(
                                severity=ERROR,
                                rule_id="VALID_PLACEHOLDERS",
                                message=(
                                    f"Placeholder {{{{input.{ph_name}}}}} not declared "
                                    "in result.inputs"
                                ),
                                location=step_loc,
                            ))

                # R10 SEQUENCE_VALID (per step)
                if step.sequence <= 0:
                    issues.append(ValidationIssue(
                        severity=ERROR,
                        rule_id="SEQUENCE_VALID",
                        message=f"step sequence must be positive, got {step.sequence}",
                        location=step_loc,
                    ))

                # R11 DEPENDENCIES_RESOLVE
                for dep in step.dependencies:
                    if dep not in step_ids_in_cap:
                        issues.append(ValidationIssue(
                            severity=ERROR,
                            rule_id="DEPENDENCIES_RESOLVE",
                            message=f"Step dependency {dep!r} not found in same capability",
                            location=step_loc,
                        ))

                # R12 MANUAL_AUTH_NO_CREDS
                if step.action == ActionType.MANUAL_AUTH:
                    val = step.value or ""
                    if _CRED_ASSIGNMENT_RE.search(val):
                        issues.append(ValidationIssue(
                            severity=ERROR,
                            rule_id="MANUAL_AUTH_NO_CREDS",
                            message="MANUAL_AUTH step value contains a credential assignment",
                            location=step_loc,
                        ))

                # R12b MANUAL_AUTH_POSTCONDITION_REQUIRED
                _ALLOWED_AUTH_WAIT_TYPES = frozenset({
                    "URL_CONTAINS", "URL_EQUALS", "ELEMENT_VISIBLE",
                    "ELEMENT_TEXT_CONTAINS", "ELEMENT_TEXT_EQUALS",
                })
                if step.action == ActionType.MANUAL_AUTH:
                    if step.wait_condition is None:
                        issues.append(ValidationIssue(
                            severity=ERROR,
                            rule_id="MANUAL_AUTH_POSTCONDITION_REQUIRED",
                            message=(
                                "MANUAL_AUTH step must have a wait_condition. "
                                "Allowed types: URL_CONTAINS, URL_EQUALS, ELEMENT_VISIBLE, "
                                "ELEMENT_TEXT_CONTAINS, ELEMENT_TEXT_EQUALS"
                            ),
                            location=step_loc,
                        ))
                    elif step.wait_condition.type.value not in _ALLOWED_AUTH_WAIT_TYPES:
                        issues.append(ValidationIssue(
                            severity=ERROR,
                            rule_id="MANUAL_AUTH_POSTCONDITION_REQUIRED",
                            message=(
                                f"MANUAL_AUTH wait_condition type "
                                f"{step.wait_condition.type.value!r} is not allowed. "
                                f"Use: {', '.join(sorted(_ALLOWED_AUTH_WAIT_TYPES))}"
                            ),
                            location=step_loc,
                        ))

                # R13 BRANCH_DESTINATIONS_RESOLVE
                for outcome in step.expected_outcomes:
                    if outcome.next_capability_id is not None:
                        if outcome.next_capability_id not in cap_map:
                            issues.append(ValidationIssue(
                                severity=ERROR,
                                rule_id="BRANCH_DESTINATIONS_RESOLVE",
                                message=(
                                    f"Branch target capability "
                                    f"{outcome.next_capability_id!r} does not exist"
                                ),
                                location=step_loc,
                            ))

                # BRANCH_CONDITION_REQUIRED
                branching_outcomes = [
                    o for o in step.expected_outcomes
                    if o.next_capability_id is not None and not o.is_terminal
                ]
                if len(branching_outcomes) > 1:
                    for outcome in branching_outcomes:
                        if outcome.condition is None and not outcome.is_default:
                            issues.append(ValidationIssue(
                                severity=ERROR,
                                rule_id="BRANCH_CONDITION_REQUIRED",
                                message=f"Outcome {outcome.outcome_id!r} is a non-terminal branch but has no condition",
                                location=step_loc,
                            ))

            # R10b SEQUENCE_VALID: no duplicates within capability
            seq_vals = [s.sequence for s in cap.steps]
            if len(seq_vals) != len(set(seq_vals)):
                issues.append(ValidationIssue(
                    severity=ERROR,
                    rule_id="SEQUENCE_VALID",
                    message="Duplicate sequence values within capability",
                    location=cap_loc,
                ))

            # R14 NO_DEPENDENCY_CYCLES (Kahn's algorithm within capability)
            if cap.steps:
                step_set = {s.step_id for s in cap.steps}
                in_degree: dict[str, int] = {s.step_id: 0 for s in cap.steps}
                adj: dict[str, list[str]] = defaultdict(list)
                for s in cap.steps:
                    for dep in s.dependencies:
                        if dep in step_set:
                            adj[dep].append(s.step_id)
                            in_degree[s.step_id] += 1
                queue: deque[str] = deque(
                    sid for sid, deg in in_degree.items() if deg == 0
                )
                visited = 0
                while queue:
                    node = queue.popleft()
                    visited += 1
                    for neighbor in adj[node]:
                        in_degree[neighbor] -= 1
                        if in_degree[neighbor] == 0:
                            queue.append(neighbor)
                if visited != len(cap.steps):
                    issues.append(ValidationIssue(
                        severity=ERROR,
                        rule_id="NO_DEPENDENCY_CYCLES",
                        message="Dependency cycle detected",
                        location=cap_loc,
                    ))

        # R15 DEFERRED_NON_EXECUTABLE
        for cap in result.capabilities:
            if cap.is_deferred and cap.steps:
                issues.append(ValidationIssue(
                    severity=WARNING,
                    rule_id="DEFERRED_NON_EXECUTABLE",
                    message="Deferred capability has steps; they will not be executed",
                    location=f"capability.{cap.capability_id}",
                ))

        # R16 GOAL_SAFE_TERMINAL
        for goal in result.goals:
            has_safe_terminal = False
            for cap_id in goal.capability_ids:
                cap = cap_map.get(cap_id)
                if cap is None:
                    continue
                if cap.is_deferred:
                    has_safe_terminal = True
                    break
                for step in cap.steps:
                    if any(o.is_terminal for o in step.expected_outcomes):
                        has_safe_terminal = True
                        break
                if has_safe_terminal:
                    break
            if not has_safe_terminal and goal.capability_ids:
                issues.append(ValidationIssue(
                    severity=ERROR,
                    rule_id="GOAL_SAFE_TERMINAL",
                    message="Goal has no safe terminal path",
                    location=f"goal.{goal.goal_id}",
                ))

        # R17 SOURCE_HASH_PRESERVED
        if result.source_reference.source_sha256 != request.source_sha256:
            issues.append(ValidationIssue(
                severity=ERROR,
                rule_id="SOURCE_HASH_PRESERVED",
                message=(
                    "source_reference.source_sha256 does not match "
                    "interpretation_request.source_sha256"
                ),
            ))
        if result.source_reference.request_id != request.request_id:
            issues.append(ValidationIssue(
                severity=ERROR,
                rule_id="SOURCE_HASH_PRESERVED",
                message=(
                    "source_reference.request_id does not match "
                    "interpretation_request.request_id"
                ),
            ))

        # REQUEST_ID_MATCH
        if result.request_id != request.request_id:
            issues.append(ValidationIssue(
                severity=ERROR,
                rule_id="REQUEST_ID_MATCH",
                message=f"result.request_id ({result.request_id!r}) does not match request.request_id ({request.request_id!r})",
            ))

        # GOAL_CAPABILITY_EXISTS
        for goal in result.goals:
            for cap_id in goal.capability_ids:
                if cap_id not in seen_caps:
                    issues.append(ValidationIssue(
                        severity=ERROR,
                        rule_id="GOAL_CAPABILITY_EXISTS",
                        message=f"Goal {goal.goal_id!r} references unknown capability {cap_id!r}",
                        location=f"goal.{goal.goal_id}",
                    ))

        # OUTCOME_DEFAULT_SINGLE — at most one default outcome per step
        for cap in result.capabilities:
            for step in cap.steps:
                defaults = [o for o in step.expected_outcomes if getattr(o, 'is_default', False)]
                if len(defaults) > 1:
                    issues.append(ValidationIssue(
                        severity=ERROR,
                        rule_id="OUTCOME_DEFAULT_SINGLE",
                        message=f"Step {step.step_id!r} has {len(defaults)} default outcomes; at most one allowed",
                        location=f"capability.{cap.capability_id}.step.{step.step_id}",
                    ))

        # OUTCOME_CONDITION_REQUIRED — non-default outcomes in multi-outcome steps need condition
        for cap in result.capabilities:
            for step in cap.steps:
                if len(step.expected_outcomes) > 1:
                    for outcome in step.expected_outcomes:
                        if not getattr(outcome, 'is_default', False) and outcome.condition is None and outcome.next_capability_id is not None:
                            issues.append(ValidationIssue(
                                severity=ERROR,
                                rule_id="OUTCOME_CONDITION_REQUIRED",
                                message=f"Outcome {outcome.outcome_id!r} in multi-outcome step {step.step_id!r} has no condition and is not default",
                                location=f"capability.{cap.capability_id}.step.{step.step_id}",
                            ))

        # OUTCOME_TERMINAL_NO_NEXT — terminal outcomes must not have next_capability_id
        for cap in result.capabilities:
            for step in cap.steps:
                for outcome in step.expected_outcomes:
                    if outcome.is_terminal and outcome.next_capability_id is not None:
                        issues.append(ValidationIssue(
                            severity=ERROR,
                            rule_id="OUTCOME_TERMINAL_NO_NEXT",
                            message=f"Terminal outcome {outcome.outcome_id!r} must not have next_capability_id",
                            location=f"capability.{cap.capability_id}.step.{step.step_id}",
                        ))

        # OUTCOME_NONTERMINAL_HAS_NEXT — non-terminal outcomes with branch must have next_capability_id
        # (only for BRANCH action steps)
        for cap in result.capabilities:
            for step in cap.steps:
                if step.action == ActionType.BRANCH:
                    for outcome in step.expected_outcomes:
                        if not outcome.is_terminal and outcome.next_capability_id is None:
                            issues.append(ValidationIssue(
                                severity=WARNING,
                                rule_id="OUTCOME_NONTERMINAL_HAS_NEXT",
                                message=f"Non-terminal outcome {outcome.outcome_id!r} in BRANCH step {step.step_id!r} has no next_capability_id",
                                location=f"capability.{cap.capability_id}.step.{step.step_id}",
                            ))

        # GOAL_REACHABILITY — every non-deferred capability in goal.capability_ids reachable from entry
        for goal in result.goals:
            if not goal.entry_capability_id:
                continue
            reachable: set[str] = set()
            queue_g: list[str] = [goal.entry_capability_id]
            while queue_g:
                c_id = queue_g.pop()
                if c_id in reachable:
                    continue
                reachable.add(c_id)
                cap_g = cap_map.get(c_id)
                if cap_g is None:
                    continue
                for step_g in cap_g.steps:
                    for outcome_g in step_g.expected_outcomes:
                        if outcome_g.next_capability_id and outcome_g.next_capability_id not in reachable:
                            queue_g.append(outcome_g.next_capability_id)
            for cap_id_g in goal.capability_ids:
                cap_g = cap_map.get(cap_id_g)
                if cap_g and not cap_g.is_deferred and cap_id_g not in reachable:
                    issues.append(ValidationIssue(
                        severity=ERROR,
                        rule_id="GOAL_REACHABILITY",
                        message=f"Capability {cap_id_g!r} in goal {goal.goal_id!r} is not reachable from entry {goal.entry_capability_id!r}",
                        location=f"goal.{goal.goal_id}",
                    ))

        # GOAL_CYCLE_DETECTION — no directed cycles in capability graph
        for goal in result.goals:
            adjacency: dict[str, list[str]] = {c_id: [] for c_id in goal.capability_ids}
            for c_id in goal.capability_ids:
                cap_c = cap_map.get(c_id)
                if cap_c is None:
                    continue
                for step_c in cap_c.steps:
                    for outcome_c in step_c.expected_outcomes:
                        if outcome_c.next_capability_id and outcome_c.next_capability_id in adjacency:
                            adjacency[c_id].append(outcome_c.next_capability_id)
            # DFS cycle detection
            visited_c: set[str] = set()
            in_stack: set[str] = set()
            cycle_found = False

            def _dfs(node: str) -> bool:
                nonlocal cycle_found
                visited_c.add(node)
                in_stack.add(node)
                for neighbor in adjacency.get(node, []):
                    if neighbor not in visited_c:
                        if _dfs(neighbor):
                            return True
                    elif neighbor in in_stack:
                        return True
                in_stack.discard(node)
                return False

            for start_cap in goal.capability_ids:
                if start_cap not in visited_c:
                    if _dfs(start_cap):
                        cycle_found = True
                        break
            if cycle_found:
                issues.append(ValidationIssue(
                    severity=ERROR,
                    rule_id="GOAL_CYCLE_DETECTION",
                    message=f"Directed cycle detected in capability graph for goal {goal.goal_id!r}",
                    location=f"goal.{goal.goal_id}",
                ))

        # BLOCKING_UNRESOLVED_ITEMS
        for item in result.unresolved_items:
            severity = ERROR if _BLOCKING_KEYWORDS.search(item) else WARNING
            issues.append(ValidationIssue(
                severity=severity,
                rule_id="BLOCKING_UNRESOLVED_ITEMS",
                message=f"Unresolved item: {item!r}",
            ))

        # Compute content hashes
        request_sha256 = sha256_of_str(
            json.dumps(read_json(request_path), sort_keys=True, ensure_ascii=False)
        )
        result_sha256 = sha256_of_str(
            json.dumps(read_json(result_path), sort_keys=True, ensure_ascii=False)
        )

        passed = not any(i.severity == ERROR for i in issues)
        report = ValidationReport(
            report_id=new_id(),
            result_id=result.result_id,
            request_id=result.request_id,
            schema_version=result.schema_version,
            passed=passed,
            issues=issues,
            validated_at=utc_now(),
            request_sha256=request_sha256,
            result_sha256=result_sha256,
        )

        report_path = result_dir / "validation_report.json"
        write_json_atomic(report_path, report.model_dump(mode="json"))

        return SopValidateResult(report=report, report_path=report_path)
