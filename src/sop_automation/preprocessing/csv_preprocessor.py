"""CSV SOP preprocessor — normalises a structured CSV into PreprocessedSource."""
from __future__ import annotations

import csv
from pathlib import Path

from sop_automation.errors import ValidationError
from sop_automation.models.common import SourceFormat
from sop_automation.models.sop import DetectedSection, DetectedSectionKind
from sop_automation.preprocessing.text_preprocessor import PreprocessedSource

CANONICAL_COLUMNS = {
    "sequence", "step_id", "application_id", "capability_id", "action",
    "element_name", "element_type", "value", "wait_condition",
    "expected_outcomes", "dependencies", "notes",
}
REQUIRED_COLUMNS = {"step_id", "action"}


def preprocess_csv(path: Path) -> PreprocessedSource:
    """Normalize CSV SOP source into PreprocessedSource. Uses stdlib csv only."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValidationError("CSV file has no header row")
        headers = [h.strip().lower() for h in reader.fieldnames if h]
        # Reject duplicate headers
        if len(headers) != len(set(headers)):
            raise ValidationError("CSV has duplicate column headers")
        # Reject missing required columns
        missing = REQUIRED_COLUMNS - set(headers)
        if missing:
            raise ValidationError(f"CSV missing required columns: {sorted(missing)}")
        rows = []
        for row in reader:
            normalized = {
                k.strip().lower(): (v.strip() if v else "")
                for k, v in row.items()
                if k
            }
            # Skip fully empty rows
            if not any(normalized.values()):
                continue
            rows.append(normalized)

    if not rows:
        raise ValidationError("CSV file has no data rows")

    sections = [
        DetectedSection(
            kind=DetectedSectionKind.NUMBERED_LIST,
            line_start=i + 2,  # +2: header is row 1
            line_end=i + 2,
            text=str(row),
        )
        for i, row in enumerate(rows)
    ]
    # Encode rows into normalized_text as TSV for human inspection
    normalized_text = "\t".join(headers) + "\n" + "\n".join(
        "\t".join(row.get(h, "") for h in headers) for row in rows
    )
    return PreprocessedSource(
        source_format=SourceFormat.CSV,
        normalized_text=normalized_text,
        sections=sections,
    )
