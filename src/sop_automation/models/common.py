"""Shared enums and Pydantic base model configurations."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """Base for value objects and protocol artifacts — immutable after creation."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class MutableModel(BaseModel):
    """Base for runtime state models — mutable, updated through service methods."""

    model_config = ConfigDict(frozen=False, extra="forbid")


class SourceFormat(str, Enum):
    """Supported SOP source formats."""

    NATURAL_LANGUAGE = "NATURAL_LANGUAGE"
    CSV = "CSV"
    XLSX = "XLSX"
    BROWSER_OBSERVATION = "BROWSER_OBSERVATION"


class ActionType(str, Enum):
    """Browser and workflow actions a SOP step can perform."""

    OPEN = "OPEN"
    CLICK = "CLICK"
    FILL = "FILL"
    PRESS = "PRESS"
    SELECT = "SELECT"
    CHECK = "CHECK"
    UNCHECK = "UNCHECK"
    UPLOAD = "UPLOAD"
    DOWNLOAD = "DOWNLOAD"
    COPY = "COPY"
    WAIT = "WAIT"
    VERIFY = "VERIFY"
    HANDLE_POPUP = "HANDLE_POPUP"
    MANUAL_AUTH = "MANUAL_AUTH"
    BRANCH = "BRANCH"
    END_SUCCESS = "END_SUCCESS"
    END_FAILURE = "END_FAILURE"
    DEFERRED = "DEFERRED"


class ElementType(str, Enum):
    """UI element types that SOP steps can target."""

    PAGE = "PAGE"
    BUTTON = "BUTTON"
    LINK = "LINK"
    TEXTBOX = "TEXTBOX"
    TEXTAREA = "TEXTAREA"
    DROPDOWN = "DROPDOWN"
    OPTION = "OPTION"
    CHECKBOX = "CHECKBOX"
    RADIO = "RADIO"
    FILE_INPUT = "FILE_INPUT"
    DIALOG = "DIALOG"
    LIST = "LIST"
    ROW = "ROW"
    TEXT = "TEXT"
    STATUS = "STATUS"
    UNKNOWN = "UNKNOWN"


class RunStatus(str, Enum):
    """Lifecycle states of a task run."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_FOR_AUTH = "WAITING_FOR_AUTH"
    WAITING_FOR_CLARIFICATION = "WAITING_FOR_CLARIFICATION"
    WAITING_FOR_DEFERRED_CAPABILITY = "WAITING_FOR_DEFERRED_CAPABILITY"
    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    """Execution states of a single SOP step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    WAITING = "WAITING"
    FAILED = "FAILED"


class ClarificationType(str, Enum):
    """Reasons a clarification request is raised during execution."""

    ELEMENT_NOT_FOUND = "ELEMENT_NOT_FOUND"
    LABEL_CHANGED = "LABEL_CHANGED"
    TIMEOUT = "TIMEOUT"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    POPUP_BLOCKING = "POPUP_BLOCKING"
    EXPECTED_RESULT_ABSENT = "EXPECTED_RESULT_ABSENT"
    USER_DECISION_REQUIRED = "USER_DECISION_REQUIRED"


class ToolHealth(str, Enum):
    """Health state of a registered capability tool."""

    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    DISABLED = "DISABLED"
