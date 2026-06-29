"""Runtime diagnostic classification and redaction helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_SECRET_KEYWORDS = (
    "password",
    "passwd",
    "otp",
    "token",
    "secret",
    "credential",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
)

_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|otp|token|secret|credential|authorization|cookie|api_key|apikey)\b"
    r"\s*[:=]\s*[^,\s;]+"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")


@dataclass(frozen=True)
class CandidateAttempt:
    """Structured record of one locator strategy attempt during element resolution."""

    strategy: str
    match_count: int
    visible: bool | None = None
    enabled: bool | None = None
    editable: bool | None = None
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"strategy": self.strategy, "match_count": self.match_count}
        if self.visible is not None:
            d["visible"] = self.visible
        if self.enabled is not None:
            d["enabled"] = self.enabled
        if self.editable is not None:
            d["editable"] = self.editable
        if self.rejection_reason is not None:
            d["rejection_reason"] = self.rejection_reason
        return d


def is_secret_field(name: str) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in _SECRET_KEYWORDS)


def redact_text(value: object) -> str:
    text = str(value)
    text = _SECRET_ASSIGNMENT_RE.sub(lambda m: f"{m.group(1)}=<redacted>", text)
    text = _BEARER_RE.sub("Bearer <redacted>", text)
    text = _EMAIL_RE.sub("<redacted-email>", text)
    return text


_VALUE_KEYS = frozenset({"expected_value", "observed_value", "value", "resolved_value"})


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact secret-keyed values. Handles nested dicts and lists of dicts.

    When a dict contains element_name that names a credential field, value-bearing
    keys (expected_value, observed_value, value, resolved_value) are also redacted.
    """
    element_name = data.get("element_name", "")
    is_credential_context = isinstance(element_name, str) and is_secret_field(element_name)

    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if is_secret_field(key):
            redacted[key] = "<redacted>"
        elif is_credential_context and key in _VALUE_KEYS:
            redacted[key] = "<redacted>"
        elif isinstance(value, dict):
            redacted[key] = redact_mapping(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_mapping(item) if isinstance(item, dict) else redact_text(str(item))
                for item in value
            ]
        elif isinstance(value, str):
            redacted[key] = redact_text(value)
        else:
            redacted[key] = value
    return redacted


def classify_failure(message: str | None) -> str:
    text = (message or "").lower()
    if "ambiguous locator" in text:
        return "LOCATOR_AMBIGUOUS"
    if "could not locate element" in text:
        return "LOCATOR_NOT_FOUND"
    if "branch_not_recognized" in text or "branch not recognized" in text:
        return "BRANCH_NOT_RECOGNIZED"
    if "authentication_error" in text or "authentication error" in text:
        return "AUTHENTICATION_ERROR"
    if "element was not attached" in text or "detached" in text:
        return "ELEMENT_DETACHED"
    if "not visible" in text or ("visible" in text and "timed out" in text):
        return "ELEMENT_NOT_VISIBLE"
    if "not editable" in text or "element_editable" in text:
        return "ELEMENT_NOT_EDITABLE"
    if "not become enabled" in text or "element_enabled" in text:
        return "ELEMENT_NOT_ENABLED"
    if "not actionable" in text or "intercept" in text:
        return "ELEMENT_NOT_ACTIONABLE"
    if "postcondition" in text or "condition not met" in text:
        return "POSTCONDITION_NOT_MET"
    if "navigation" in text and ("timeout" in text or "timed out" in text):
        return "NAVIGATION_TIMEOUT"
    if "timeout" in text or "timed out" in text:
        return "ACTION_TIMEOUT"
    if "browser" in text and "closed" in text:
        return "BROWSER_CLOSED"
    return "RUNTIME_ERROR"
