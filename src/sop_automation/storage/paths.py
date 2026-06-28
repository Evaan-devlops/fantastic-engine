"""Workspace path resolution with traversal protection."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sop_automation.errors import WorkspaceError


@dataclass(frozen=True)
class WorkspacePaths:
    """Canonical paths for all SOP runtime directories."""

    root: Path
    inbox: Path
    sources: Path
    compiled: Path
    manifests: Path
    runs: Path
    resolutions: Path
    routes: Path
    tool_build_requests: Path
    tools: Path
    generated: Path
    runtime: Path
    runtime_commands: Path
    runtime_acks: Path
    runtime_processed: Path
    runtime_failed: Path

    @classmethod
    def from_root(cls, root: Path) -> "WorkspacePaths":
        r = root.resolve()
        return cls(
            root=r,
            inbox=r / "inbox",
            sources=r / "sources",
            compiled=r / "compiled",
            manifests=r / "manifests",
            runs=r / "runs",
            resolutions=r / "resolutions",
            routes=r / "routes",
            tool_build_requests=r / "tool_build_requests",
            tools=r / "tools",
            generated=r / "generated",
            runtime=r / "runtime",
            runtime_commands=r / "runtime" / "commands",
            runtime_acks=r / "runtime" / "acknowledgements",
            runtime_processed=r / "runtime" / "processed",
            runtime_failed=r / "runtime" / "failed",
        )

    def all_dirs(self) -> list[Path]:
        return [
            self.inbox,
            self.sources,
            self.compiled,
            self.manifests,
            self.runs,
            self.resolutions,
            self.routes,
            self.tool_build_requests,
            self.tools,
            self.generated,
            self.runtime,
            self.runtime_commands,
            self.runtime_acks,
            self.runtime_processed,
            self.runtime_failed,
        ]


def resolve_path(workspace_root: Path, relative: str | Path) -> Path:
    root = workspace_root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise WorkspaceError(
            f"Path traversal rejected: '{relative}' resolves outside workspace root '{root}'"
        )
    return resolved
