"""Template placeholder resolver for step values."""
from __future__ import annotations

import re
from typing import Any

from sop_automation.errors import ValueResolutionError

_PLACEHOLDER_RE = re.compile(r'\{\{([^}]+)\}\}')
_CREDENTIAL_KEYWORDS = {"password", "passwd", "otp", "secret", "token", "credential"}


def _is_credential(element_name: str) -> bool:
    name_lower = element_name.lower()
    return any(kw in name_lower for kw in _CREDENTIAL_KEYWORDS)


def _resolve_key(key: str, context: dict[str, Any]) -> Any:
    """Resolve a single placeholder key against context. Raises ValueResolutionError if missing."""
    parts = key.strip().split(".")
    if len(parts) < 2:
        raise ValueResolutionError(f"Invalid placeholder syntax: '{{{{{key}}}}}'")

    namespace = parts[0]
    if namespace == "input" and len(parts) == 2:
        name = parts[1]
        inputs = context.get("inputs", {})
        if name not in inputs:
            raise ValueResolutionError(f"Input '{{input.{name}}}' not found in context")
        return inputs[name]
    elif namespace == "output" and len(parts) == 2:
        name = parts[1]
        outputs = context.get("outputs", {})
        if name not in outputs:
            raise ValueResolutionError(f"Output '{{output.{name}}}' not found in context")
        return outputs[name]
    elif namespace == "steps" and len(parts) == 3:
        step_id = parts[1]
        field = parts[2]
        steps = context.get("steps", {})
        if step_id not in steps:
            raise ValueResolutionError(f"Step '{{steps.{step_id}.{field}}}' not found in context")
        step_data = steps[step_id]
        if field not in step_data:
            raise ValueResolutionError(
                f"Field '{field}' not found in step '{step_id}' context"
            )
        return step_data[field]
    else:
        raise ValueResolutionError(f"Unknown placeholder namespace: '{namespace}'")


class ValueResolver:
    """Resolves {{placeholder}} templates in step values."""

    def resolve(
        self,
        value: str | None,
        context: dict[str, Any],
        element_name: str = "",
    ) -> Any:
        if value is None:
            return None

        matches = _PLACEHOLDER_RE.findall(value)
        if not matches:
            return value

        if len(matches) == 1 and value.strip() == f"{{{{{matches[0]}}}}}":
            return _resolve_key(matches[0], context)

        def replace_match(m: re.Match) -> str:
            resolved = _resolve_key(m.group(1), context)
            return str(resolved)

        return _PLACEHOLDER_RE.sub(replace_match, value)
