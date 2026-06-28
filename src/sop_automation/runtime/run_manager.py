"""Single-run orchestrator: executes a TaskPlan step by step via graph traversal."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sop_automation.errors import DependencyError
from sop_automation.models.common import ActionType, RunStatus, StepStatus
from sop_automation.models.execution import RunState, StepProgress
from sop_automation.models.task import PlannedCapability, PlannedOutcome, PlannedStep, TaskPlan
from sop_automation.runtime.action_dispatcher import ActionDispatcher
from sop_automation.runtime.condition_evaluator import ConditionEvaluator
from sop_automation.runtime.value_resolver import ValueResolver
from sop_automation.storage.json_store import new_id, utc_now, write_json_atomic

if TYPE_CHECKING:
    from playwright.async_api import Page

_CREDENTIAL_NAMES = {"password", "passwd", "otp", "secret", "token", "credential"}

_PROGRESS_SYMBOLS = {
    StepStatus.COMPLETED: "v",
    StepStatus.RUNNING: "->",
    StepStatus.PENDING: " ",
    StepStatus.WAITING: "~",
    StepStatus.FAILED: "!",
    StepStatus.SKIPPED: "-",
}

_TERMINAL_ACTIONS = frozenset({
    ActionType.END_SUCCESS,
    ActionType.END_FAILURE,
    ActionType.DEFERRED,
})


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _is_credential_step(step: PlannedStep) -> bool:
    name_lower = step.element_name.lower()
    return any(cred in name_lower for cred in _CREDENTIAL_NAMES)


def _topological_sort(steps: list[PlannedStep]) -> list[PlannedStep]:
    """Kahn's algorithm for topological sort of steps within a capability."""
    step_map = {s.step_id: s for s in steps}
    in_degree: dict[str, int] = {s.step_id: 0 for s in steps}
    dependents: dict[str, list[str]] = {s.step_id: [] for s in steps}

    for step in steps:
        for dep in step.dependencies:
            if dep not in step_map:
                raise DependencyError(
                    f"Step '{step.step_id}' depends on '{dep}' which is not in this capability"
                )
            in_degree[step.step_id] += 1
            dependents[dep].append(step.step_id)

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    result: list[PlannedStep] = []

    while queue:
        sid = queue.pop(0)
        result.append(step_map[sid])
        for child in dependents[sid]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(result) != len(steps):
        raise DependencyError("Cycle detected in step dependencies")

    return result


def _select_outcome(
    step: PlannedStep,
    result_context: dict[str, Any],
    evaluator: ConditionEvaluator,
) -> PlannedOutcome | None:
    """Evaluate outcomes in order; return first match or default."""
    default: PlannedOutcome | None = None
    for outcome in step.outcomes:
        if outcome.is_default:
            default = outcome
            continue
        if outcome.condition is not None:
            if evaluator.evaluate(outcome.condition, result_context):
                return outcome
        else:
            return outcome
    return default


class RunManager:
    """Executes a task plan; manages state, events, and retry."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self._dispatcher = ActionDispatcher()
        self._evaluator = ConditionEvaluator()
        self._resolver = ValueResolver()
        self._state: RunState | None = None
        self._context: dict[str, Any] = {}
        self._auth_event: asyncio.Event = asyncio.Event()

    def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        event = {"type": event_type, "ts": _utc_now().isoformat(), **data}
        events_path = self.run_dir / "events.jsonl"
        with open(events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def _save_state(self) -> None:
        if self._state:
            write_json_atomic(
                self.run_dir / "run_state.json",
                self._state.model_dump(mode="json"),
            )

    async def start_run(
        self,
        run_id: str,
        plan: TaskPlan,
        page: "Page",
    ) -> RunState:
        self.run_dir.mkdir(parents=True, exist_ok=True)

        write_json_atomic(
            self.run_dir / "task_plan.json",
            plan.model_dump(mode="json"),
        )

        self._state = RunState(
            run_id=run_id,
            task_id=plan.plan_id,
            status=RunStatus.CREATED,
            inputs=plan.inputs,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        self._save_state()
        self._emit_event("run_created", {"run_id": run_id, "sop_id": plan.sop_id})

        self._context = {
            "inputs": dict(plan.inputs),
            "outputs": {},
            "steps": {},
        }

        self._state.status = RunStatus.RUNNING
        self._state.updated_at = _utc_now()
        self._save_state()

        await self._execute_plan(plan, page)
        return self._state

    async def _execute_plan(self, plan: TaskPlan, page: "Page") -> None:
        assert self._state is not None

        cap_map = {cap.capability_id: cap for cap in plan.capabilities}
        cursor: str | None = plan.entry_capability_id
        visited: set[str] = set()

        while cursor is not None:
            if cursor in visited:
                self._state.status = RunStatus.FAILED
                self._state.updated_at = _utc_now()
                self._save_state()
                self._emit_event("run_failed", {"reason": "RUNTIME_CYCLE", "capability_id": cursor})
                return

            visited.add(cursor)

            if cursor not in cap_map:
                self._state.status = RunStatus.FAILED
                self._state.updated_at = _utc_now()
                self._save_state()
                self._emit_event("run_failed", {"reason": f"CAPABILITY_NOT_FOUND: {cursor}"})
                return

            planned_cap = cap_map[cursor]

            if planned_cap.is_deferred:
                self._state.status = RunStatus.WAITING_FOR_DEFERRED_CAPABILITY
                self._state.updated_at = _utc_now()
                self._save_state()
                self._emit_event("capability_deferred", {"capability_id": cursor})
                return

            self._state.current_capability_id = planned_cap.capability_id
            self._state.updated_at = _utc_now()
            self._save_state()
            self._emit_event("capability_started", {"capability_id": planned_cap.capability_id})

            try:
                sorted_steps = _topological_sort(list(planned_cap.steps))
            except DependencyError as exc:
                self._state.status = RunStatus.FAILED
                self._state.updated_at = _utc_now()
                self._save_state()
                self._emit_event("run_failed", {"reason": str(exc)})
                return

            selected_outcome: PlannedOutcome | None = None
            for step in sorted_steps:
                if self._state.status not in (RunStatus.RUNNING,):
                    break

                prog = self._state.step_progress.get(step.step_id)
                if prog and prog.status == StepStatus.COMPLETED:
                    continue

                selected_outcome = await self._execute_step(step, page, plan)

                # Stop immediately when status left RUNNING (auth/fail/clarification/deferred)
                if self._state.status not in (RunStatus.RUNNING,):
                    break

                # Stop immediately when outcome is terminal or routes to next capability
                if selected_outcome is not None and (
                    selected_outcome.is_terminal or selected_outcome.next_capability_id
                ):
                    break

            # If execution was interrupted by a non-running status, let the caller handle it
            if self._state.status not in (RunStatus.RUNNING,):
                return

            self._emit_event("capability_completed", {"capability_id": planned_cap.capability_id})

            if selected_outcome is None:
                if self._state.status == RunStatus.RUNNING:
                    self._state.status = RunStatus.COMPLETED
                    self._state.updated_at = _utc_now()
                    self._save_state()
                    self._emit_event("run_succeeded", {"run_id": self._state.run_id})
                return

            if selected_outcome.is_terminal:
                if selected_outcome.is_success:
                    self._state.status = RunStatus.COMPLETED
                    self._state.updated_at = _utc_now()
                    self._save_state()
                    self._emit_event("run_succeeded", {"run_id": self._state.run_id})
                else:
                    self._state.status = RunStatus.FAILED
                    self._state.updated_at = _utc_now()
                    self._save_state()
                    self._emit_event("run_failed", {"reason": "END_FAILURE"})
                return

            cursor = selected_outcome.next_capability_id

        if self._state.status == RunStatus.RUNNING:
            self._state.status = RunStatus.COMPLETED
            self._state.updated_at = _utc_now()
            self._save_state()
            self._emit_event("run_succeeded", {"run_id": self._state.run_id})

    async def _check_auth_condition(self, step: PlannedStep, page: "Page") -> bool:
        """Evaluate MANUAL_AUTH post-auth condition against the live page. Fails closed."""
        if step.wait_condition is None:
            return False  # fail closed — a postcondition is required
        from sop_automation.runtime.page_preparation import PagePreparationService
        prep = PagePreparationService()
        try:
            await prep.prepare(page, step.wait_condition)
            return True
        except Exception:
            return False

    async def _execute_step(
        self,
        step: PlannedStep,
        page: "Page",
        plan: TaskPlan,
    ) -> PlannedOutcome | None:
        assert self._state is not None
        state = self._state

        prog = StepProgress(
            step_id=step.step_id,
            status=StepStatus.RUNNING,
            started_at=_utc_now(),
            attempt_count=0,
        )
        state.step_progress[step.step_id] = prog
        state.current_step_id = step.step_id
        state.updated_at = _utc_now()
        self._save_state()
        self._emit_event("step_started", {"step_id": step.step_id})

        # --- MANUAL_AUTH: suspend until signal_auth() fires; evaluate page condition each time ---
        if step.action == ActionType.MANUAL_AUTH:
            prog.status = StepStatus.WAITING
            state.status = RunStatus.WAITING_FOR_AUTH
            state.updated_at = _utc_now()
            self._save_state()
            self._emit_event("auth_waiting", {"step_id": step.step_id})
            print("\nAuthentication required. Complete login in browser.")

            while True:
                self._auth_event.clear()
                await self._auth_event.wait()

                # Honour cancellation before any state update
                if state.status == RunStatus.CANCELLED:
                    return None

                condition_passed = await self._check_auth_condition(step, page)
                if condition_passed:
                    self._context.setdefault("steps", {})[step.step_id] = {
                        "success": True,
                        "current_url": page.url,
                    }
                    prog.status = StepStatus.COMPLETED
                    prog.completed_at = _utc_now()
                    state.status = RunStatus.RUNNING
                    state.updated_at = _utc_now()
                    self._save_state()
                    self._emit_event("auth_verified", {"step_id": step.step_id})
                    break
                else:
                    state.status = RunStatus.WAITING_FOR_AUTH
                    state.updated_at = _utc_now()
                    self._save_state()
                    self._emit_event("auth_still_required", {"step_id": step.step_id})
                    # Loop: wait for next signal_auth()

            return _select_outcome(step, self._context, self._evaluator)

        # --- Terminal actions: bypass retry and clarification entirely ---
        if step.action in _TERMINAL_ACTIONS:
            prog.attempt_count = 1
            state.updated_at = _utc_now()
            self._save_state()

            result = await self._dispatcher.execute(
                page, step, self._context, self.run_dir, None
            )

            if step.action == ActionType.END_SUCCESS:
                prog.status = StepStatus.COMPLETED
                prog.completed_at = _utc_now()
                prog.current_url = result.current_url
                state.status = RunStatus.COMPLETED
                state.updated_at = _utc_now()
                self._context.setdefault("steps", {})[step.step_id] = {
                    "success": True,
                    "value": result.value,
                    "current_url": result.current_url,
                }
                self._save_state()
                self._emit_event("step_completed", {"step_id": step.step_id})
                self._emit_event("run_succeeded", {"run_id": state.run_id})
                return _select_outcome(step, self._context, self._evaluator)

            if step.action == ActionType.END_FAILURE:
                prog.status = StepStatus.FAILED
                prog.error_message = "END_FAILURE"
                prog.completed_at = _utc_now()
                state.status = RunStatus.FAILED
                state.updated_at = _utc_now()
                self._save_state()
                self._emit_event("step_failed", {"step_id": step.step_id, "error": "END_FAILURE"})
                self._emit_event("run_failed", {"reason": "END_FAILURE"})
                return None

            if step.action == ActionType.DEFERRED:
                prog.status = StepStatus.FAILED
                prog.error_message = "DEFERRED_CAPABILITY"
                prog.completed_at = _utc_now()
                state.status = RunStatus.WAITING_FOR_DEFERRED_CAPABILITY
                state.updated_at = _utc_now()
                self._save_state()
                self._emit_event("step_failed", {"step_id": step.step_id, "error": "DEFERRED_CAPABILITY"})
                self._emit_event("capability_deferred", {"step_id": step.step_id})
                return None

        # --- Resolve template placeholders in step value ---
        resolved_value: str | None = None
        try:
            resolved_value = self._resolver.resolve(step.value, self._context, step.element_name)
            if resolved_value is not None:
                resolved_value = str(resolved_value)
        except Exception as exc:
            prog.status = StepStatus.FAILED
            prog.error_message = f"VALUE_RESOLUTION_FAILED: {exc}"
            prog.completed_at = _utc_now()
            state.status = RunStatus.FAILED
            state.updated_at = _utc_now()
            self._save_state()
            self._emit_event("run_failed", {
                "step_id": step.step_id,
                "reason": "VALUE_RESOLUTION_FAILED",
                "error": str(exc),
            })
            return None

        # --- Retry loop (max 2 attempts) then clarification ---
        max_attempts = 2
        last_result = None
        for attempt in range(1, max_attempts + 1):
            prog.attempt_count = attempt
            state.updated_at = _utc_now()
            self._save_state()

            result = await self._dispatcher.execute(
                page, step, self._context, self.run_dir, resolved_value
            )
            last_result = result

            if result.success:
                prog.status = StepStatus.COMPLETED
                prog.completed_at = _utc_now()
                prog.current_url = result.current_url
                state.updated_at = _utc_now()
                self._context.setdefault("steps", {})[step.step_id] = {
                    "success": True,
                    "value": result.value,
                    "text": result.value,
                    "current_url": result.current_url,
                }
                self._save_state()
                self._emit_event("step_completed", {"step_id": step.step_id})

                outcome = _select_outcome(step, self._context, self._evaluator)
                if outcome is None and step.outcomes:
                    self._emit_event("step_no_outcome", {"step_id": step.step_id})
                elif outcome is not None:
                    prog.selected_outcome_id = outcome.outcome_id
                    state.branch_decisions[step.step_id] = outcome.outcome_id
                    self._save_state()
                    self._emit_event("branch_selected", {
                        "step_id": step.step_id,
                        "outcome_id": outcome.outcome_id,
                    })
                return outcome

            if attempt < max_attempts:
                prog.error_message = result.error_message
                state.updated_at = _utc_now()
                self._save_state()
                self._emit_event("step_retried", {
                    "step_id": step.step_id,
                    "attempt": attempt,
                    "error": result.error_message,
                })
                await asyncio.sleep(1.0)

        result = last_result
        prog.status = StepStatus.FAILED
        prog.error_message = result.error_message if result else "Unknown failure"
        prog.completed_at = _utc_now()

        if not _is_credential_step(step):
            try:
                screenshots_dir = self.run_dir / "screenshots"
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                shot_path = screenshots_dir / f"{step.step_id}_failure.png"
                await page.screenshot(path=str(shot_path))
                prog.screenshot_paths.append(str(shot_path))
            except Exception:
                pass

        state.updated_at = _utc_now()
        self._save_state()
        self._emit_event("step_failed", {
            "step_id": step.step_id,
            "error": prog.error_message,
        })

        clarification_data: dict[str, Any] = {
            "request_id": new_id(),
            "run_id": state.run_id,
            "capability_id": step.capability_id,
            "step_id": step.step_id,
            "error_message": prog.error_message,
            "current_url": prog.current_url or "",
            "expected_element": step.element_name,
            "locator_candidates": result.locator_candidates if result else [],
            "screenshot_path": prog.screenshot_paths[0] if prog.screenshot_paths else None,
            "created_at": _utc_now().isoformat(),
        }
        clarification_path = self.run_dir / "clarification_request.json"
        write_json_atomic(clarification_path, clarification_data)

        state.clarification_request_id = clarification_data["request_id"]
        state.status = RunStatus.WAITING_FOR_CLARIFICATION
        state.updated_at = _utc_now()
        self._save_state()
        self._emit_event("clarification_requested", {
            "request_id": clarification_data["request_id"],
            "step_id": step.step_id,
        })
        return None

    def signal_auth(self, verified: bool = True) -> None:
        """Wake the MANUAL_AUTH await so run_manager can re-evaluate the page condition."""
        self._auth_event.set()

    def cancel(self) -> None:
        if self._state:
            self._state.status = RunStatus.CANCELLED
            self._state.updated_at = _utc_now()
            self._save_state()
            self._emit_event("run_cancelled", {"run_id": self._state.run_id})
        self._auth_event.set()
