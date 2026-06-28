"""Unit tests for ConditionEvaluator — written but not run."""
from __future__ import annotations

import pytest

from sop_automation.models.sop import ConditionOperator, ConditionSpec
from sop_automation.runtime.condition_evaluator import ConditionEvaluator


def _spec(
    source_key: str,
    operator: ConditionOperator,
    expected_value: str | int | float | bool | None = None,
) -> ConditionSpec:
    return ConditionSpec(source_key=source_key, operator=operator, expected_value=expected_value)


class TestConditionEvaluator:
    """Tests for ConditionEvaluator.evaluate."""

    def setup_method(self) -> None:
        self.evaluator = ConditionEvaluator()

    # ------------------------------------------------------------------
    # EQUALS
    # ------------------------------------------------------------------

    def test_equals_match(self) -> None:
        spec = _spec("status", ConditionOperator.EQUALS, "active")
        result = self.evaluator.evaluate(spec, {"status": "active"})
        assert result is True

    def test_equals_no_match(self) -> None:
        spec = _spec("status", ConditionOperator.EQUALS, "active")
        result = self.evaluator.evaluate(spec, {"status": "inactive"})
        assert result is False

    def test_int_expected_value(self) -> None:
        spec = _spec("count", ConditionOperator.EQUALS, 5)
        result = self.evaluator.evaluate(spec, {"count": 5})
        assert result is True

    def test_bool_expected_value(self) -> None:
        spec = _spec("enabled", ConditionOperator.EQUALS, True)
        result = self.evaluator.evaluate(spec, {"enabled": True})
        assert result is True

    # ------------------------------------------------------------------
    # NOT_EQUALS
    # ------------------------------------------------------------------

    def test_not_equals(self) -> None:
        spec = _spec("mode", ConditionOperator.NOT_EQUALS, "headless")
        assert self.evaluator.evaluate(spec, {"mode": "headed"}) is True
        assert self.evaluator.evaluate(spec, {"mode": "headless"}) is False

    # ------------------------------------------------------------------
    # TRUE / FALSE
    # ------------------------------------------------------------------

    def test_true_on_truthy_value(self) -> None:
        spec = _spec("label", ConditionOperator.TRUE)
        result = self.evaluator.evaluate(spec, {"label": "some-value"})
        assert result is True

    def test_false_on_falsy_value(self) -> None:
        spec = _spec("label", ConditionOperator.FALSE)
        result = self.evaluator.evaluate(spec, {"label": ""})
        assert result is True

    # ------------------------------------------------------------------
    # EXISTS / NOT_EXISTS
    # ------------------------------------------------------------------

    def test_exists_found(self) -> None:
        spec = _spec("run_id", ConditionOperator.EXISTS)
        result = self.evaluator.evaluate(spec, {"run_id": "abc-123"})
        assert result is True

    def test_exists_not_found(self) -> None:
        spec = _spec("run_id", ConditionOperator.EXISTS)
        result = self.evaluator.evaluate(spec, {})
        assert result is False

    def test_exists_none_value_returns_false(self) -> None:
        spec = _spec("run_id", ConditionOperator.EXISTS)
        result = self.evaluator.evaluate(spec, {"run_id": None})
        assert result is False

    def test_not_exists_missing_key(self) -> None:
        spec = _spec("run_id", ConditionOperator.NOT_EXISTS)
        result = self.evaluator.evaluate(spec, {})
        assert result is True

    def test_not_exists_key_present(self) -> None:
        spec = _spec("run_id", ConditionOperator.NOT_EXISTS)
        result = self.evaluator.evaluate(spec, {"run_id": "abc-123"})
        assert result is False

    # ------------------------------------------------------------------
    # CONTAINS
    # ------------------------------------------------------------------

    def test_contains_partial_match(self) -> None:
        spec = _spec("message", ConditionOperator.CONTAINS, "error")
        result = self.evaluator.evaluate(spec, {"message": "fatal error occurred"})
        assert result is True

    def test_contains_no_match(self) -> None:
        spec = _spec("message", ConditionOperator.CONTAINS, "timeout")
        result = self.evaluator.evaluate(spec, {"message": "success"})
        assert result is False

    # ------------------------------------------------------------------
    # Dot-path nested lookup
    # ------------------------------------------------------------------

    def test_dot_path_nested_lookup(self) -> None:
        spec = _spec("steps.step_001.success", ConditionOperator.EQUALS, True)
        context: dict = {"steps": {"step_001": {"success": True}}}
        result = self.evaluator.evaluate(spec, context)
        assert result is True

    # ------------------------------------------------------------------
    # Missing key edge cases
    # ------------------------------------------------------------------

    def test_missing_key_returns_false_for_equals(self) -> None:
        spec = _spec("nonexistent_key", ConditionOperator.EQUALS, "value")
        result = self.evaluator.evaluate(spec, {})
        assert result is False
