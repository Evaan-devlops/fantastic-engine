"""Service: list all compiled SOPs in the workspace."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sop_automation.storage.json_store import read_json
from sop_automation.storage.paths import resolve_path


@dataclass
class SopListEntry:
    sop_id: str
    title: str
    goals: list[str]
    compiled_at: datetime


class SopListService:
    def list_sops(self, workspace_root: Path) -> list[SopListEntry]:
        compiled_root = resolve_path(workspace_root, "compiled")
        if not compiled_root.exists():
            return []
        entries: list[SopListEntry] = []
        for compiled_json in compiled_root.glob("*/compiled_sop.json"):
            try:
                data = read_json(compiled_json)
                compiled_at_str = data.get("compiled_at", "")
                compiled_at = (
                    datetime.fromisoformat(compiled_at_str)
                    if compiled_at_str
                    else datetime.min
                )
                entries.append(SopListEntry(
                    sop_id=data.get("sop_id", "?"),
                    title=data.get("title", "?"),
                    goals=list(data.get("goals", {}).keys()),
                    compiled_at=compiled_at,
                ))
            except Exception as exc:
                print(f"Warning: skipping {compiled_json}: {exc}", file=sys.stderr)
        entries.sort(key=lambda e: e.compiled_at, reverse=True)
        return entries
