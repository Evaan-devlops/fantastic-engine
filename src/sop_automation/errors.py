"""Typed error hierarchy for SOPAutomationV2."""
from __future__ import annotations


class SopAutomationError(Exception):
    """Base error — all domain errors inherit from this."""


class StorageError(SopAutomationError):
    """File read, write, or parse failure."""


class ValidationError(SopAutomationError):
    """Input or output failed Pydantic validation."""


class WorkspaceError(SopAutomationError):
    """Workspace directory or path resolution failure."""


class NotImplementedInPhase0Error(SopAutomationError):
    """Raised by CLI commands that are not yet implemented."""

    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__(f"Command '{command}' is not implemented in Phase 0.")


class ValueResolutionError(SopAutomationError):
    """A template placeholder could not be resolved from runtime context."""


class PagePreparationError(SopAutomationError):
    """A page wait condition timed out or cannot be satisfied."""


class DependencyError(SopAutomationError):
    """Step dependency cycle or unresolved dependency within a capability."""
