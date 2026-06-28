"""Service: select a compiled SOP and goal from a TaskIntent."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sop_automation.errors import StorageError
from sop_automation.errors import ValidationError as SopValidationError
from sop_automation.models.sop import CompiledSop
from sop_automation.models.task import TaskIntent
from sop_automation.storage.json_store import read_json
from sop_automation.storage.paths import resolve_path


@dataclass
class SopSelectionResult:
    sop_id: str
    goal_id: str
    confidence: float
    alternatives: list[str]


class SopSelectorService:
    """Selects a compiled SOP and goal from a TaskIntent without LLM calls."""

    _CLEAR_WINNER_GAP = 0.3

    def select(
        self,
        intent: TaskIntent,
        workspace_root: Path,
    ) -> SopSelectionResult:
        if intent.preferred_sop_id:
            return self._select_preferred(intent, workspace_root)
        return self._select_by_scoring(intent, workspace_root)

    def _select_preferred(
        self,
        intent: TaskIntent,
        workspace_root: Path,
    ) -> SopSelectionResult:
        sop_id = intent.preferred_sop_id
        assert sop_id is not None
        compiled_path = resolve_path(workspace_root, f"compiled/{sop_id}/compiled_sop.json")
        if not compiled_path.exists():
            raise StorageError(f"Preferred SOP {sop_id!r} not found.")
        compiled = CompiledSop.model_validate(read_json(compiled_path))
        goal_id = self._find_goal(intent.requested_goal, compiled)
        if goal_id is None:
            raise SopValidationError(
                f"Goal {intent.requested_goal!r} not found in SOP {sop_id!r}. "
                f"Available: {list(compiled.goals.keys())}"
            )
        return SopSelectionResult(sop_id=sop_id, goal_id=goal_id, confidence=1.0, alternatives=[])

    def _select_by_scoring(
        self,
        intent: TaskIntent,
        workspace_root: Path,
    ) -> SopSelectionResult:
        compiled_dir = resolve_path(workspace_root, "compiled")
        if not compiled_dir.exists():
            raise StorageError("No compiled SOPs found.")

        candidates: list[tuple[float, str, str]] = []  # (score, sop_id, goal_id)

        for sop_dir in compiled_dir.iterdir():
            if not sop_dir.is_dir():
                continue
            sop_path = sop_dir / "compiled_sop.json"
            if not sop_path.exists():
                continue
            try:
                compiled = CompiledSop.model_validate(read_json(sop_path))
            except Exception:
                continue

            for goal_id, goal in compiled.goals.items():
                score = self._score(intent, compiled, goal_id, goal)
                if score > 0:
                    candidates.append((score, compiled.sop_id, goal_id))

        if not candidates:
            raise SopValidationError(
                f"No compiled SOP matches goal {intent.requested_goal!r}."
            )

        candidates.sort(key=lambda x: x[0], reverse=True)
        top_score, top_sop, top_goal = candidates[0]

        if len(candidates) >= 2:
            second_score = candidates[1][0]
            if (top_score - second_score) < self._CLEAR_WINNER_GAP:
                alternatives = [f"{s}/{g}" for _, s, g in candidates[1:4]]
                raise SopValidationError(
                    f"Ambiguous SOP selection. Top candidates: {[f'{top_sop}/{top_goal}'] + alternatives}. "
                    "Use --preferred-sop-id to specify."
                )

        alternatives = [f"{s}/{g}" for _, s, g in candidates[1:4]]
        return SopSelectionResult(
            sop_id=top_sop,
            goal_id=top_goal,
            confidence=top_score,
            alternatives=alternatives,
        )

    def _find_goal(self, requested_goal: str, compiled: CompiledSop) -> str | None:
        # Exact goal_id match
        if requested_goal in compiled.goals:
            return requested_goal
        # Alias match
        for goal_id, goal in compiled.goals.items():
            if requested_goal in goal.aliases:
                return goal_id
        return None

    def _score(
        self,
        intent: TaskIntent,
        compiled: CompiledSop,
        goal_id: str,
        goal: object,
    ) -> float:
        from sop_automation.models.sop import GoalDefinition
        assert isinstance(goal, GoalDefinition)
        score = 0.0
        req = intent.requested_goal.lower()

        # Exact goal_id match → high
        if req == goal_id.lower():
            score += 1.0
        # Alias match → high
        if req in [a.lower() for a in goal.aliases]:
            score += 0.9
        # Application hint overlap → medium
        goal_apps = {
            c.application_id
            for c in compiled.capabilities
            if c.capability_id in goal.capability_ids
        }
        for hint in intent.application_hints:
            if hint.lower() in {a.lower() for a in goal_apps}:
                score += 0.4
        # Token overlap on name/description → low
        req_tokens = set(req.split())
        name_tokens = set(goal.name.lower().split())
        desc_tokens = set(goal.description.lower().split())
        overlap = len(req_tokens & (name_tokens | desc_tokens))
        if overlap:
            score += min(0.3, overlap * 0.1)

        return score
