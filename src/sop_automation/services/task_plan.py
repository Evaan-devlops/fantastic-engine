"""Service: build a dry-run task plan from a compiled SOP and goal."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sop_automation.errors import StorageError
from sop_automation.errors import ValidationError as SopValidationError
from sop_automation.models.sop import CompiledSop
from sop_automation.models.task import (
    BranchPoint,
    CapabilityEdge,
    PlannedCapability,
    PlannedOutcome,
    PlannedStep,
    TaskPlan,
)
from sop_automation.storage.json_store import (
    new_id,
    read_json,
    utc_now,
    write_json_atomic,
)
from sop_automation.storage.paths import resolve_path


@dataclass
class TaskPlanResult:
    plan: TaskPlan
    plan_path: Path


class TaskPlanService:
    def plan(
        self,
        workspace_root: Path,
        sop_id: str,
        goal_id: str,
        inputs: dict[str, str],
    ) -> TaskPlanResult:
        compiled_path = resolve_path(workspace_root, f"compiled/{sop_id}/compiled_sop.json")
        if not compiled_path.exists():
            raise StorageError(
                f"Compiled SOP not found: {compiled_path}. Run 'sop compile' first."
            )
        compiled = CompiledSop.model_validate(read_json(compiled_path))

        if goal_id not in compiled.goals:
            raise SopValidationError(
                f"Goal {goal_id!r} not found in SOP {sop_id!r}. "
                f"Available: {list(compiled.goals.keys())}"
            )

        goal = compiled.goals[goal_id]
        required_inputs = goal.required_inputs
        missing = [name for name in required_inputs if name not in inputs]
        if missing:
            raise SopValidationError(f"Missing required inputs: {missing}")

        cap_map = {c.capability_id: c for c in compiled.capabilities}
        entry_cap_id = goal.entry_capability_id or (goal.capability_ids[0] if goal.capability_ids else "")
        all_cap_ids = goal.capability_ids

        capability_edges: list[CapabilityEdge] = []
        branch_points: list[BranchPoint] = []
        deferred_destinations: list[str] = []
        planned_capabilities: list[PlannedCapability] = []

        # Edge from start → entry
        capability_edges.append(CapabilityEdge(
            from_capability_id=None,
            to_capability_id=entry_cap_id,
            is_conditional=False,
        ))

        # Collect all conditional edges from step outcomes (never skip based on existing targets)
        for cap_id in all_cap_ids:
            cap = cap_map.get(cap_id)
            if cap is None:
                continue
            for step in cap.steps:
                for o in step.expected_outcomes:
                    if o.next_capability_id is not None:
                        capability_edges.append(CapabilityEdge(
                            from_capability_id=cap_id,
                            to_capability_id=o.next_capability_id,
                            is_conditional=o.condition is not None or not o.is_default,
                            condition=o.condition,
                        ))

        # Build PlannedCapability for each non-deferred capability in the goal
        for cap_id in all_cap_ids:
            cap = cap_map.get(cap_id)
            if cap is None:
                continue
            if cap.is_deferred:
                deferred_destinations.append(cap_id)
                planned_capabilities.append(PlannedCapability(
                    capability_id=cap_id,
                    name=cap.name,
                    application_id=cap.application_id,
                    steps=[],
                    is_deferred=True,
                    is_tool_candidate=cap.is_tool_candidate,
                ))
                continue

            planned_steps: list[PlannedStep] = []
            for step in sorted(cap.steps, key=lambda s: s.sequence):
                planned_outcomes = [
                    PlannedOutcome(
                        outcome_id=o.outcome_id,
                        description=o.description,
                        is_terminal=o.is_terminal,
                        is_success=o.is_success,
                        condition=o.condition,
                        is_default=o.is_default,
                        next_capability_id=o.next_capability_id,
                    )
                    for o in step.expected_outcomes
                ]

                planned_steps.append(PlannedStep(
                    capability_id=cap_id,
                    capability_name=cap.name,
                    application_id=cap.application_id,
                    step_id=step.step_id,
                    sequence=step.sequence,
                    action=step.action,
                    element_name=step.element_name,
                    element_type=step.element_type,
                    value=step.value,
                    wait_condition=step.wait_condition,
                    wait_condition_notes=step.wait_condition_notes,
                    dependencies=step.dependencies,
                    outcomes=planned_outcomes,
                    source_line=step.source_line,
                ))

                # Branch point: step has any outcome with next_capability_id
                branching = [o for o in planned_outcomes if o.next_capability_id is not None]
                if branching:
                    branch_points.append(BranchPoint(
                        step_id=step.step_id,
                        capability_id=cap_id,
                        outcomes=planned_outcomes,
                    ))

            planned_capabilities.append(PlannedCapability(
                capability_id=cap_id,
                name=cap.name,
                application_id=cap.application_id,
                steps=planned_steps,
                is_deferred=False,
                is_tool_candidate=cap.is_tool_candidate,
            ))

        plan = TaskPlan(
            plan_id=new_id(),
            sop_id=sop_id,
            goal_id=goal_id,
            entry_capability_id=entry_cap_id,
            capabilities=planned_capabilities,
            capability_edges=capability_edges,
            branch_points=branch_points,
            inputs=inputs,
            deferred_destinations=deferred_destinations,
            created_at=utc_now(),
        )

        ts = utc_now().strftime("%Y%m%dT%H%M%S")
        runs_dir = resolve_path(workspace_root, "runs")
        runs_dir.mkdir(parents=True, exist_ok=True)
        plan_path = resolve_path(
            workspace_root, f"runs/dry_run_{sop_id}_{goal_id}_{ts}.json"
        )
        write_json_atomic(plan_path, plan.model_dump(mode="json"))

        return TaskPlanResult(plan=plan, plan_path=plan_path)
