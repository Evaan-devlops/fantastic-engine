"""Atomic command queue for runtime host communication."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from pathlib import Path

from sop_automation.models.runtime import CommandAcknowledgement, RuntimeCommand
from sop_automation.storage.json_store import read_json, write_json_atomic


def submit_command(commands_dir: Path, command: RuntimeCommand) -> Path:
    """Write a command atomically; return its file path."""
    commands_dir.mkdir(parents=True, exist_ok=True)
    path = commands_dir / f"{command.command_id}.json"
    write_json_atomic(path, command.model_dump(mode="json"))
    return path


def poll_commands(commands_dir: Path) -> list[Path]:
    """Return command files sorted by modification time (oldest first)."""
    if not commands_dir.exists():
        return []
    files = [f for f in commands_dir.iterdir() if f.suffix == ".json" and f.is_file()]
    return sorted(files, key=lambda f: f.stat().st_mtime)


def consume_command(path: Path, processed_dir: Path | None = None, failed_dir: Path | None = None) -> RuntimeCommand:
    """Parse and validate a command file; move to processed/ on success or failed/ on parse error.

    Validates BEFORE deleting so a corrupt file lands in failed/ with evidence.
    """
    data = read_json(path)
    try:
        command = RuntimeCommand.model_validate(data)
    except Exception as exc:
        if failed_dir is not None:
            failed_dir.mkdir(parents=True, exist_ok=True)
            dest = failed_dir / path.name
            error_path = failed_dir / f"{path.stem}_error.json"
            try:
                shutil.move(str(path), str(dest))
                write_json_atomic(error_path, {"file": path.name, "error": str(exc), "raw": data})
            except OSError:
                pass
        else:
            try:
                os.unlink(path)
            except OSError:
                pass
        raise

    if processed_dir is not None:
        processed_dir.mkdir(parents=True, exist_ok=True)
        dest = processed_dir / path.name
        try:
            shutil.move(str(path), str(dest))
        except OSError:
            try:
                os.unlink(path)
            except OSError:
                pass
    else:
        try:
            os.unlink(path)
        except OSError:
            pass

    return command


def write_acknowledgement(acks_dir: Path, ack: CommandAcknowledgement) -> None:
    """Write an acknowledgement atomically."""
    acks_dir.mkdir(parents=True, exist_ok=True)
    path = acks_dir / f"{ack.command_id}.json"
    write_json_atomic(path, ack.model_dump(mode="json"))


def read_acknowledgement(acks_dir: Path, command_id: str) -> CommandAcknowledgement | None:
    """Read an acknowledgement by command_id; return None if not found."""
    path = acks_dir / f"{command_id}.json"
    if not path.exists():
        return None
    try:
        return CommandAcknowledgement.model_validate(read_json(path))
    except Exception:
        return None


def poll_for_ack(
    acks_dir: Path,
    command_id: str,
    timeout_s: float = 10.0,
    poll_interval_s: float = 0.25,
) -> CommandAcknowledgement | None:
    """Synchronous bounded poll for an acknowledgement file. Returns None on timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        ack = read_acknowledgement(acks_dir, command_id)
        if ack is not None:
            return ack
        time.sleep(poll_interval_s)
    return None
