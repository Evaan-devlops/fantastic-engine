"""Deterministic condition evaluation over runtime context. No eval()."""
from __future__ import annotations

from typing import Any

from sop_automation.models.sop import ConditionOperator, ConditionSpec


def _dot_path_lookup(context: dict[str, Any], key: str) -> tuple[bool, Any]:
    """Safely look up a dot-separated key path in context.

    Returns (found, value). Never raises.
    """
    parts = key.split(".")
    node: Any = context
    for part in parts:
        if not isinstance(node, dict):
            return False, None
        if part not in node:
            return False, None
        node = node[part]
    return True, node


class ConditionEvaluator:
    """Evaluate a ConditionSpec against a runtime context dict."""

    def evaluate(self, spec: ConditionSpec, context: dict[str, Any]) -> bool:
        found, value = _dot_path_lookup(context, spec.source_key)
        op = spec.operator
        ev = spec.expected_value

        if op == ConditionOperator.EXISTS:
            return found and value is not None
        if op == ConditionOperator.NOT_EXISTS:
            return not found or value is None
        if op == ConditionOperator.TRUE:
            return bool(value) is True
        if op == ConditionOperator.FALSE:
            return bool(value) is False

        if not found:
            return False

        if op == ConditionOperator.EQUALS:
            return value == ev
        if op == ConditionOperator.NOT_EQUALS:
            return value != ev
        if op == ConditionOperator.CONTAINS:
            if ev is None:
                return False
            return str(ev) in str(value)
        return False
