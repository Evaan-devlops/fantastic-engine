"""Service: prepare a SOP source file and write an InterpretationRequest."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sop_automation.errors import StorageError, ValidationError
from sop_automation.models.common import SourceFormat
from sop_automation.models.sop import InterpretationRequest, SopSource
from sop_automation.storage.json_store import (
    new_id,
    sha256_of_file,
    utc_now,
    write_bytes_atomic,
    write_json_atomic,
)
from sop_automation.storage.paths import resolve_path

_SOP_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')


@dataclass
class SopPrepareResult:
    request: InterpretationRequest
    request_path: Path


class SopPrepareService:
    def prepare(
        self,
        workspace_root: Path,
        source_path: Path,
        sop_id: str,
    ) -> SopPrepareResult:
        if not _SOP_ID_RE.match(sop_id):
            raise ValidationError(
                f"sop_id must be 1–64 alphanumeric/hyphen/underscore characters, got: {sop_id!r}"
            )
        if not source_path.exists():
            raise StorageError(f"Source file not found: {source_path}")

        suffix = source_path.suffix.lower()
        if suffix in (".txt", ".md"):
            from sop_automation.preprocessing.text_preprocessor import preprocess_text
            text = source_path.read_text(encoding="utf-8")
            preprocessed = preprocess_text(text)
            source_format = SourceFormat.NATURAL_LANGUAGE
        elif suffix == ".csv":
            from sop_automation.preprocessing.csv_preprocessor import preprocess_csv
            preprocessed = preprocess_csv(source_path)
            source_format = SourceFormat.CSV
        elif suffix == ".xlsx":
            from sop_automation.preprocessing.xlsx_preprocessor import preprocess_xlsx
            preprocessed = preprocess_xlsx(source_path)
            source_format = SourceFormat.XLSX
        else:
            raise ValidationError(
                f"Unsupported source format: {suffix!r}. Supported: .txt, .md, .csv, .xlsx"
            )

        # Preserve source file in sources/<sop_id>/
        sources_dir = resolve_path(workspace_root, f"sources/{sop_id}")
        sources_dir.mkdir(parents=True, exist_ok=True)
        preserved_filename = f"{sop_id}{source_path.suffix}"
        preserved_path = resolve_path(
            workspace_root, f"sources/{sop_id}/{preserved_filename}"
        )
        write_bytes_atomic(preserved_path, source_path.read_bytes())
        preserved_sha256 = sha256_of_file(preserved_path)

        sop_source = SopSource(
            sop_id=sop_id,
            source_format=source_format,
            source_path=str(source_path),
            preserved_path=str(preserved_path),
            source_sha256=preserved_sha256,
            created_at=utc_now(),
        )

        request = InterpretationRequest(
            request_id=new_id(),
            schema_version="1.0",
            sop_id=sop_id,
            source_path=str(preserved_path),    # preserved path, not original
            source_format=source_format,
            source_sha256=preserved_sha256,
            created_at=utc_now(),
            normalized_text=preprocessed.normalized_text,
            sections=preprocessed.sections,
            detected_urls=preprocessed.detected_urls,
            detected_placeholders=preprocessed.detected_placeholders,
            capability_hints=preprocessed.capability_hints,
            possible_condition_lines=preprocessed.possible_condition_lines,
            possible_deferred_lines=preprocessed.possible_deferred_lines,
        )

        sop_dir = resolve_path(workspace_root, f"compiled/{sop_id}")
        sop_dir.mkdir(parents=True, exist_ok=True)
        request_path = resolve_path(
            workspace_root, f"compiled/{sop_id}/interpretation_request.json"
        )
        write_json_atomic(request_path, request.model_dump(mode="json"))

        # Also write sop_source record
        source_record_path = resolve_path(
            workspace_root, f"sources/{sop_id}/sop_source.json"
        )
        write_json_atomic(source_record_path, sop_source.model_dump(mode="json"))

        return SopPrepareResult(request=request, request_path=request_path)
