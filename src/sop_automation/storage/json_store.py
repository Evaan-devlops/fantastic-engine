"""Atomic JSON/JSONL storage helpers, SHA-256 utilities, and ID generation."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sop_automation.errors import StorageError


def write_json_atomic(path: Path, data: Any) -> None:
    """Write *data* to *path* atomically using a temp file and os.replace().

    Never writes a partial file to the live path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
            encoding="utf-8",
        ) as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            tmp_path = f.name
        os.replace(tmp_path, path)
    except OSError as exc:
        raise StorageError(f"Failed to write '{path}': {exc}") from exc


def read_json(path: Path) -> Any:
    """Read and parse a JSON file.

    Raises StorageError on missing file or parse failure.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StorageError(f"File not found: '{path}'") from exc
    except json.JSONDecodeError as exc:
        raise StorageError(f"JSON parse error in '{path}': {exc}") from exc
    except OSError as exc:
        raise StorageError(f"Failed to read '{path}': {exc}") from exc


def append_jsonl(path: Path, record: Any) -> None:
    """Append a single JSON record as a line to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError as exc:
        raise StorageError(f"Failed to append to '{path}': {exc}") from exc


def sha256_of_file(path: Path) -> str:
    """Return the hex SHA-256 digest of a file's contents."""
    try:
        h = hashlib.sha256(path.read_bytes())
        return h.hexdigest()
    except OSError as exc:
        raise StorageError(f"Failed to hash '{path}': {exc}") from exc


def sha256_of_str(text: str) -> str:
    """Return the hex SHA-256 digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


def new_id() -> str:
    """Generate a collision-resistant random ID (32 hex characters)."""
    return uuid.uuid4().hex


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Write *data* to *path* atomically using a temp file in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False, suffix=".tmp") as f:
        f.write(data)
        tmp_path = f.name
    os.replace(tmp_path, path)


def write_text_atomic(path: Path, text: str) -> None:
    """Write *text* to *path* atomically using a temp file and os.replace().

    Never writes a partial file to the live path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
            encoding="utf-8",
        ) as f:
            f.write(text)
            tmp_path = f.name
        os.replace(tmp_path, path)
    except OSError as exc:
        raise StorageError(f"Failed to write '{path}': {exc}") from exc
