"""Workspace initialisation service."""
from __future__ import annotations

from pathlib import Path

from sop_automation.storage.paths import WorkspacePaths


class WorkspaceService:
    """Manages workspace directory lifecycle."""

    def init(self, workspace_root: Path) -> list[tuple[str, str]]:
        """Create all required SOP directories under *workspace_root*.

        Returns a list of (relative_path, status) tuples where status is
        one of: 'CREATED', 'EXISTS', 'ERROR'.
        """
        paths = WorkspacePaths.from_root(workspace_root)
        results: list[tuple[str, str]] = []

        for directory in paths.all_dirs():
            rel = str(directory.relative_to(paths.root))
            try:
                if directory.exists():
                    results.append((rel, "EXISTS"))
                else:
                    directory.mkdir(parents=True, exist_ok=True)
                    results.append((rel, "CREATED"))
            except OSError:
                results.append((rel, "ERROR"))

        return results
