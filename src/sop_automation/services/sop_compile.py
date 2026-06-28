"""Service: compile a validated InterpretationResult into a CompiledSop."""
from __future__ import annotations

import json as _json
from dataclasses import dataclass
from pathlib import Path

from sop_automation.errors import StorageError
from sop_automation.errors import ValidationError as SopValidationError
from sop_automation.models.sop import (
    CapabilityDefinition,
    CompiledSop,
    GoalDefinition,
    InterpretationRequest,
    InterpretationResult,
    OutcomeRule,
    SopSource,
    SopStep,
)
from sop_automation.models.validation import ValidationReport, ValidationSeverity
from sop_automation.storage.json_store import (
    read_json,
    sha256_of_str,
    utc_now,
    write_json_atomic,
    write_text_atomic,
)
from sop_automation.storage.paths import resolve_path


@dataclass
class SopCompileResult:
    compiled_sop: CompiledSop
    compiled_sop_path: Path
    manifest_path: Path
    markdown_path: Path


class SopCompileService:
    def compile(self, result_path: Path, workspace_root: Path) -> SopCompileResult:
        result_dir = result_path.parent

        # Load and validate ValidationReport
        report_path = result_dir / "validation_report.json"
        if not report_path.exists():
            raise StorageError(
                f"validation_report.json not found in {result_dir}. "
                "Run 'sop validate-result' first."
            )
        report = ValidationReport.model_validate(read_json(report_path))
        if not report.passed:
            error_count = sum(
                1 for i in report.issues if i.severity == ValidationSeverity.ERROR
            )
            raise SopValidationError(
                f"Compilation blocked: validation report has {error_count} error(s). "
                "Fix them with 'sop validate-result' first."
            )

        # Load InterpretationResult
        result = InterpretationResult.model_validate(read_json(result_path))

        # Load request to get sop_id
        request_path = result_dir / "interpretation_request.json"
        request = InterpretationRequest.model_validate(read_json(request_path))

        # Verify content hashes before compiling
        current_request_sha256 = sha256_of_str(
            _json.dumps(read_json(request_path), sort_keys=True, ensure_ascii=False)
        )
        current_result_sha256 = sha256_of_str(
            _json.dumps(read_json(result_path), sort_keys=True, ensure_ascii=False)
        )
        if current_request_sha256 != report.request_sha256:
            raise SopValidationError(
                "interpretation_request.json has changed since validation. "
                "Re-run 'sop validate-result'."
            )
        if current_result_sha256 != report.result_sha256:
            raise SopValidationError(
                "interpretation_result.json has changed since validation. "
                "Re-run 'sop validate-result'."
            )

        sop_id = request.sop_id

        # Build CompiledSop from InterpretationResult
        compiled = self._build_compiled_sop(result, request)

        # Write compiled_sop.json
        compiled_path = resolve_path(
            workspace_root, f"compiled/{sop_id}/compiled_sop.json"
        )
        write_json_atomic(compiled_path, compiled.model_dump(mode="json"))

        # Write manifest
        manifest_data = self._generate_manifest(compiled)
        manifest_path = resolve_path(workspace_root, f"manifests/{sop_id}.manifest.json")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(manifest_path, manifest_data)

        # Write Markdown
        md_text = self._generate_markdown(compiled, result)
        generated_dir = resolve_path(workspace_root, "generated")
        generated_dir.mkdir(parents=True, exist_ok=True)
        md_path = resolve_path(workspace_root, f"generated/{sop_id}.md")
        write_text_atomic(md_path, md_text)

        return SopCompileResult(
            compiled_sop=compiled,
            compiled_sop_path=compiled_path,
            manifest_path=manifest_path,
            markdown_path=md_path,
        )

    def _build_compiled_sop(
        self, result: InterpretationResult, request: InterpretationRequest
    ) -> CompiledSop:
        """Build CompiledSop from validated InterpretationResult deterministically."""
        capabilities = []
        for cap_proposal in result.capabilities:
            steps = []
            for sp in sorted(cap_proposal.steps, key=lambda s: s.sequence):
                steps.append(SopStep(
                    step_id=sp.step_id,
                    sequence=sp.sequence,
                    action=sp.action,
                    element_name=sp.element_name,
                    element_type=sp.element_type,
                    application_id=cap_proposal.application_id,   # required
                    capability_id=cap_proposal.capability_id,      # required
                    value=sp.value,
                    wait_condition=sp.wait_condition,
                    wait_condition_notes=sp.wait_condition_notes,
                    expected_outcomes=[
                        OutcomeRule(
                            outcome_id=o.outcome_id,
                            description=o.description,
                            is_terminal=o.is_terminal,
                            is_success=o.is_success,
                            condition=o.condition,                 # propagate ConditionSpec
                            is_default=o.is_default,
                            next_capability_id=o.next_capability_id,
                        )
                        for o in sp.expected_outcomes
                    ],
                    dependencies=sp.dependencies,
                    notes=sp.notes,
                    source_line=sp.source_line,
                ))
            capabilities.append(CapabilityDefinition(
                capability_id=cap_proposal.capability_id,
                name=cap_proposal.name,
                application_id=cap_proposal.application_id,
                description=cap_proposal.description,
                steps=steps,
                inputs=cap_proposal.inputs,
                outputs=cap_proposal.outputs,
                is_deferred=cap_proposal.is_deferred,
                is_tool_candidate=cap_proposal.is_tool_candidate,   # propagated
            ))

        source = SopSource(
            sop_id=request.sop_id,
            source_format=request.source_format,
            source_path=str(request.source_path),
            preserved_path=str(request.source_path),   # request.source_path IS the preserved path
            source_sha256=request.source_sha256,
            created_at=utc_now(),
        )

        compiled = CompiledSop(
            sop_id=request.sop_id,
            schema_version="1.0",
            title=result.goals[0].name if result.goals else request.sop_id,
            source=source,
            applications=[a.application_id for a in result.applications],
            goals={g.goal_id: GoalDefinition(
                goal_id=g.goal_id,
                name=g.name,
                description=g.description,
                entry_capability_id=g.entry_capability_id,
                capability_ids=g.capability_ids,
                required_inputs=g.required_inputs,
                expected_outputs=g.expected_outputs,
                assumptions=g.assumptions,
            ) for g in result.goals},
            capabilities=capabilities,
            inputs={inp.name: inp for inp in result.inputs},
            assumptions=result.assumptions,
            unresolved_items=result.unresolved_items,
            compiled_at=utc_now(),
            compiled_content_sha256="",   # will be filled below
        )

        # Compute compiled_content_sha256
        canonical = compiled.model_dump(mode="json")
        canonical.pop("compiled_at", None)
        canonical.pop("compiled_content_sha256", None)
        content_sha256 = sha256_of_str(
            _json.dumps(canonical, sort_keys=True, ensure_ascii=False)
        )
        compiled = compiled.model_copy(update={"compiled_content_sha256": content_sha256})

        return compiled

    def _generate_manifest(self, compiled: CompiledSop) -> dict:
        manifest_data: dict = {
            "sop_id": compiled.sop_id,
            "title": compiled.title,
            "schema_version": compiled.schema_version,
            "compiled_at": compiled.compiled_at.isoformat(),
            "goals": list(compiled.goals.keys()),
            "capabilities": [
                {
                    "capability_id": c.capability_id,
                    "name": c.name,
                    "is_deferred": c.is_deferred,
                    "is_tool_candidate": c.is_tool_candidate,
                }
                for c in compiled.capabilities
            ],
            "required_inputs": list(compiled.inputs.keys()),
            "source_sha256": compiled.source.source_sha256,
            "compiled_content_sha256": compiled.compiled_content_sha256,
        }
        # Compute manifest_content_sha256 over the initial dict
        manifest_json_str = _json.dumps(manifest_data, sort_keys=True, ensure_ascii=False)
        manifest_data["manifest_content_sha256"] = sha256_of_str(manifest_json_str)
        return manifest_data

    def _generate_markdown(
        self, compiled: CompiledSop, result: InterpretationResult
    ) -> str:
        lines = [
            f"# SOP: {compiled.title}",
            "",
            f"**SOP ID:** `{compiled.sop_id}`  ",
            f"**Compiled:** {compiled.compiled_at.isoformat()}  ",
            f"**Schema:** {compiled.schema_version}",
            "",
        ]

        lines += [
            "## Source",
            f"- Path: `{compiled.source.source_path}`",
            f"- Format: {compiled.source.source_format}",
            f"- SHA256: `{compiled.source.source_sha256}`",
            "",
        ]

        lines += ["## Applications"]
        for app in result.applications:
            lines.append(f"- **{app.name}** (`{app.application_id}`)")
            for url in app.url_patterns:
                lines.append(f"  - URL: {url}")
        lines.append("")

        lines += ["## Goals"]
        for goal in result.goals:
            lines.append(f"### {goal.name} (`{goal.goal_id}`)")
            lines.append(goal.description)
            if goal.required_inputs:
                lines.append(f"**Required inputs:** {', '.join(goal.required_inputs)}")
            if goal.expected_outputs:
                lines.append(f"**Expected outputs:** {', '.join(goal.expected_outputs)}")
            if goal.capability_ids:
                entry = goal.entry_capability_id or (goal.capability_ids[0] if goal.capability_ids else "")
                lines.append(
                    f"**Entry capability:** {entry}"
                )
                lines.append(
                    f"**Capability IDs:** {', '.join(goal.capability_ids)}"
                )
            lines.append("")

        lines += ["## Required Inputs"]
        for inp in result.inputs:
            req = "required" if inp.required else "optional"
            default = f" (default: {inp.default_value})" if inp.default_value else ""
            lines.append(f"- `{inp.name}` ({req}{default}): {inp.description}")
        lines.append("")

        lines += ["## Capabilities"]
        for cap in compiled.capabilities:
            deferred_tag = " *(deferred)*" if cap.is_deferred else ""
            tool_tag = " *(tool candidate)*" if cap.is_tool_candidate else ""
            lines.append(f"### {cap.name} (`{cap.capability_id}`){deferred_tag}{tool_tag}")
            lines.append(cap.description)
            if not cap.is_deferred and cap.steps:
                lines.append("")
                lines.append("**Steps:**")
                for step in cap.steps:
                    val_part = f" → `{step.value}`" if step.value else ""
                    wait_part = (
                        f" (wait: {step.wait_condition.type})" if step.wait_condition else ""
                    )
                    lines.append(
                        f"{step.sequence}. `{step.action}` **{step.element_name}**"
                        f" ({step.element_type}){val_part}{wait_part}"
                    )
                    if step.dependencies:
                        lines.append(
                            f"   - *depends on:* {', '.join(step.dependencies)}"
                        )
                    for outcome in step.expected_outcomes:
                        terminal = " [terminal]" if outcome.is_terminal else ""
                        branch = (
                            f" → {outcome.next_capability_id}"
                            if outcome.next_capability_id
                            else ""
                        )
                        lines.append(
                            f"   - outcome: {outcome.description}{terminal}{branch}"
                        )
                    if step.notes:
                        lines.append(f"   - *notes:* {step.notes}")
            lines.append("")

        if result.assumptions:
            lines += ["## Assumptions"]
            for a in result.assumptions:
                lines.append(f"- {a}")
            lines.append("")

        if result.unresolved_items:
            lines += ["## Unresolved Items"]
            for u in result.unresolved_items:
                lines.append(f"- {u}")
            lines.append("")

        deferred = [c for c in compiled.capabilities if c.is_deferred]
        if deferred:
            lines += ["## Deferred Capabilities"]
            for cap in deferred:
                lines.append(
                    f"- `{cap.capability_id}`: {cap.name} — *not yet implemented*"
                )
            lines.append("")

        return "\n".join(lines)
