"""XLSX SOP preprocessor — normalises an Excel workbook into PreprocessedSource."""
from __future__ import annotations

from pathlib import Path

from sop_automation.errors import ValidationError
from sop_automation.models.common import SourceFormat
from sop_automation.models.sop import DetectedSection, DetectedSectionKind
from sop_automation.preprocessing.csv_preprocessor import REQUIRED_COLUMNS
from sop_automation.preprocessing.text_preprocessor import PreprocessedSource


def preprocess_xlsx(path: Path) -> PreprocessedSource:
    """Normalize XLSX SOP source. Imports openpyxl lazily."""
    try:
        import openpyxl  # noqa: PLC0415
    except ImportError as exc:
        raise ValidationError(
            "openpyxl is required for .xlsx files. Install with: pip install openpyxl>=3.1"
        ) from exc

    wb = openpyxl.load_workbook(path, read_only=True, data_only=False)
    try:
        visible_sheets = [ws for ws in wb.worksheets if ws.sheet_state == "visible"]
        if not visible_sheets:
            raise ValidationError("XLSX workbook has no visible sheets")

        # Prefer sheet named "SOP" (case-insensitive)
        ws = next(
            (s for s in visible_sheets if s.title.upper() == "SOP"),
            visible_sheets[0],
        )

        rows_iter = ws.iter_rows(values_only=False)
        # Find header row (first non-empty row)
        header_row = None
        for row in rows_iter:
            values = [cell.value for cell in row]
            if any(v is not None for v in values):
                header_row = row
                break

        if header_row is None:
            raise ValidationError("XLSX sheet has no header row")

        # Reject formulas in header cells
        for cell in header_row:
            if cell.data_type == "f" or (isinstance(cell.value, str) and cell.value.startswith("=")):
                raise ValidationError(f"XLSX formula in header at column {cell.coordinate}")

        # Reject blank headers within the used header range
        for col_idx, cell in enumerate(header_row):
            v = cell.value
            if v is None or str(v).strip() == "":
                remaining = [header_row[j].value for j in range(col_idx + 1, len(header_row))]
                if any(r is not None and str(r).strip() for r in remaining):
                    raise ValidationError(f"XLSX header row has a blank cell at column {col_idx + 1}")

        # Use column-index mapping to preserve positions
        col_to_header: dict[int, str] = {}
        for col_idx, cell in enumerate(header_row):
            v = cell.value
            if v is not None and str(v).strip():
                col_to_header[col_idx] = str(v).strip().lower()
        headers = list(col_to_header.values())

        if len(headers) != len(set(headers)):
            raise ValidationError("XLSX has duplicate column headers")

        missing = REQUIRED_COLUMNS - set(headers)
        if missing:
            raise ValidationError(f"XLSX missing required columns: {sorted(missing)}")

        data_rows = []
        for row in rows_iter:
            # Reject formulas in operational cells
            for cell in row:
                if cell.data_type == "f" or (
                    isinstance(cell.value, str) and cell.value.startswith("=")
                ):
                    raise ValidationError(
                        f"XLSX formula rejected at cell {cell.coordinate}. "
                        "SOP data must not contain formulas."
                    )
            # Map cells by column index to header name
            normalized: dict[str, str] = {}
            for col_idx, header_name in col_to_header.items():
                if col_idx < len(row):
                    cell_val = row[col_idx].value
                    normalized[header_name] = str(cell_val).strip() if cell_val is not None else ""
                else:
                    normalized[header_name] = ""
            if not any(normalized.values()):
                continue  # skip fully empty trailing rows
            data_rows.append(normalized)

    finally:
        wb.close()

    if not data_rows:
        raise ValidationError("XLSX sheet has no data rows")

    sections = [
        DetectedSection(
            kind=DetectedSectionKind.NUMBERED_LIST,
            line_start=i + 2,
            line_end=i + 2,
            text=str(row),
        )
        for i, row in enumerate(data_rows)
    ]
    normalized_text = "\t".join(headers) + "\n" + "\n".join(
        "\t".join(row.get(h, "") for h in headers) for row in data_rows
    )
    return PreprocessedSource(
        source_format=SourceFormat.XLSX,
        normalized_text=normalized_text,
        sections=sections,
    )
