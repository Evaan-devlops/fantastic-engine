"""Tests for preprocessing layer — written but not run (Phase 1)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sop_automation.preprocessing.text_preprocessor import preprocess_text
from sop_automation.preprocessing.csv_preprocessor import preprocess_csv
from sop_automation.models.common import SourceFormat
from sop_automation.models.sop import DetectedSectionKind


# ---------------------------------------------------------------------------
# Text preprocessor tests
# ---------------------------------------------------------------------------

class TestTextPreprocessorHeadings:
    def test_text_detect_heading_hash_prefix(self) -> None:
        text = "# Step 1\nDo something"
        result = preprocess_text(text)
        kinds = [s.kind for s in result.sections]
        assert DetectedSectionKind.HEADING in kinds

    def test_text_detect_heading_allcaps(self) -> None:
        text = "LOGIN PROCEDURE\nSome detail here"
        result = preprocess_text(text)
        kinds = [s.kind for s in result.sections]
        assert DetectedSectionKind.HEADING in kinds


class TestTextPreprocessorListItems:
    def test_text_detect_numbered_item(self) -> None:
        text = "1. Click the button"
        result = preprocess_text(text)
        kinds = [s.kind for s in result.sections]
        assert DetectedSectionKind.NUMBERED_LIST in kinds

    def test_text_detect_bullet_dash(self) -> None:
        text = "- Open browser"
        result = preprocess_text(text)
        kinds = [s.kind for s in result.sections]
        assert DetectedSectionKind.BULLET_LIST in kinds


class TestTextPreprocessorDetectors:
    def test_text_detect_url(self) -> None:
        text = "Navigate to https://example.com to begin"
        result = preprocess_text(text)
        assert len(result.detected_urls) > 0
        assert "https://example.com" in result.detected_urls

    def test_text_detect_placeholder(self) -> None:
        text = "Enter {{input.email}} in the field"
        result = preprocess_text(text)
        assert "{{input.email}}" in result.detected_placeholders

    def test_text_detect_tool_marker(self) -> None:
        text = "authentication: tool"
        result = preprocess_text(text)
        assert len(result.capability_hints) > 0
        kinds = [s.kind for s in result.sections]
        assert DetectedSectionKind.TOOL_MARKER in kinds

    def test_text_detect_deferred_marker(self) -> None:
        text = "get_code will be created later"
        result = preprocess_text(text)
        assert len(result.possible_deferred_lines) > 0

    def test_text_detect_condition_if(self) -> None:
        text = "if login fails, retry the step"
        result = preprocess_text(text)
        assert len(result.possible_condition_lines) > 0


class TestTextPreprocessorEmptyInput:
    def test_text_empty_input_returns_empty_collections(self) -> None:
        result = preprocess_text("")
        assert result.sections == []
        assert result.detected_urls == []
        assert result.detected_placeholders == []
        assert result.capability_hints == []
        assert result.possible_condition_lines == []
        assert result.possible_deferred_lines == []


# ---------------------------------------------------------------------------
# CSV preprocessor tests
# ---------------------------------------------------------------------------

class TestCsvPreprocessor:
    def test_csv_normalize_valid_file(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "sop.csv"
        csv_file.write_text(
            "step_id,action,element_name\n"
            "step_001,CLICK,login_button\n"
            "step_002,FILL,email_field\n",
            encoding="utf-8",
        )
        result = preprocess_csv(csv_file)
        assert result.source_format == SourceFormat.CSV
        assert len(result.sections) > 0

    def test_csv_reject_missing_step_id_column(self, tmp_path: Path) -> None:
        from sop_automation.errors import ValidationError
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text(
            "action,element_name\n"
            "CLICK,login_button\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError, match="step_id"):
            preprocess_csv(csv_file)

    def test_csv_reject_missing_action_column(self, tmp_path: Path) -> None:
        from sop_automation.errors import ValidationError
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text(
            "step_id,element_name\n"
            "step_001,login_button\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError, match="action"):
            preprocess_csv(csv_file)

    def test_csv_reject_duplicate_headers(self, tmp_path: Path) -> None:
        from sop_automation.errors import ValidationError
        csv_file = tmp_path / "dup.csv"
        csv_file.write_text(
            "step_id,step_id,action\n"
            "step_001,step_001,CLICK\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError, match="duplicate"):
            preprocess_csv(csv_file)

    def test_csv_skip_empty_trailing_rows(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "trailing.csv"
        csv_file.write_text(
            "step_id,action,element_name\n"
            "step_001,CLICK,login_button\n"
            "step_002,FILL,email_field\n"
            ",,,\n",
            encoding="utf-8",
        )
        result = preprocess_csv(csv_file)
        assert len(result.sections) == 2


# ---------------------------------------------------------------------------
# XLSX preprocessor tests (using mocks — openpyxl not installed)
# ---------------------------------------------------------------------------

class TestXlsxPreprocessor:
    def test_xlsx_reject_formula_in_cell(self, tmp_path: Path) -> None:
        from sop_automation.preprocessing.xlsx_preprocessor import preprocess_xlsx
        from sop_automation.errors import ValidationError

        formula_cell = MagicMock()
        formula_cell.data_type = "f"
        formula_cell.value = "=A1+B1"
        formula_cell.coordinate = "C2"

        header_cell_1 = MagicMock()
        header_cell_1.value = "step_id"
        header_cell_1.data_type = "s"

        header_cell_2 = MagicMock()
        header_cell_2.value = "action"
        header_cell_2.data_type = "s"

        mock_ws = MagicMock()
        mock_ws.sheet_state = "visible"
        mock_ws.title = "Sheet1"
        mock_ws.iter_rows.return_value = iter([
            (header_cell_1, header_cell_2),
            (formula_cell, formula_cell),
        ])

        mock_wb = MagicMock()
        mock_wb.worksheets = [mock_ws]

        dummy = tmp_path / "test.xlsx"
        dummy.write_bytes(b"")

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            with pytest.raises(ValidationError, match="formula"):
                preprocess_xlsx(dummy)

    def test_xlsx_prefer_sop_sheet(self, tmp_path: Path) -> None:
        from sop_automation.preprocessing.xlsx_preprocessor import preprocess_xlsx

        def _make_sheet(title: str) -> MagicMock:
            ws = MagicMock()
            ws.sheet_state = "visible"
            ws.title = title
            h1 = MagicMock(); h1.value = "step_id"; h1.data_type = "s"
            h2 = MagicMock(); h2.value = "action"; h2.data_type = "s"
            d1 = MagicMock(); d1.value = "step_001"; d1.data_type = "s"
            d2 = MagicMock(); d2.value = "CLICK"; d2.data_type = "s"
            ws.iter_rows.return_value = iter([
                (h1, h2),
                (d1, d2),
            ])
            return ws

        sheet1 = _make_sheet("Sheet1")
        sop_sheet = _make_sheet("SOP")

        mock_wb = MagicMock()
        mock_wb.worksheets = [sheet1, sop_sheet]

        dummy = tmp_path / "test.xlsx"
        dummy.write_bytes(b"")

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            result = preprocess_xlsx(dummy)

        # SOP sheet was used — iter_rows called on sop_sheet, not sheet1
        sop_sheet.iter_rows.assert_called()
        assert result.source_format.value == "XLSX"

    def test_xlsx_fallback_first_visible_sheet(self, tmp_path: Path) -> None:
        from sop_automation.preprocessing.xlsx_preprocessor import preprocess_xlsx

        h1 = MagicMock(); h1.value = "step_id"; h1.data_type = "s"
        h2 = MagicMock(); h2.value = "action"; h2.data_type = "s"
        d1 = MagicMock(); d1.value = "step_001"; d1.data_type = "s"
        d2 = MagicMock(); d2.value = "CLICK"; d2.data_type = "s"

        mock_ws = MagicMock()
        mock_ws.sheet_state = "visible"
        mock_ws.title = "MyData"
        mock_ws.iter_rows.return_value = iter([
            (h1, h2),
            (d1, d2),
        ])

        mock_wb = MagicMock()
        mock_wb.worksheets = [mock_ws]

        dummy = tmp_path / "test.xlsx"
        dummy.write_bytes(b"")

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            result = preprocess_xlsx(dummy)

        assert result.source_format.value == "XLSX"

    def test_xlsx_reject_empty_workbook(self, tmp_path: Path) -> None:
        from sop_automation.preprocessing.xlsx_preprocessor import preprocess_xlsx
        from sop_automation.errors import ValidationError

        mock_ws = MagicMock()
        mock_ws.sheet_state = "hidden"
        mock_ws.title = "HiddenSheet"

        mock_wb = MagicMock()
        mock_wb.worksheets = [mock_ws]

        dummy = tmp_path / "test.xlsx"
        dummy.write_bytes(b"")

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            with pytest.raises(ValidationError, match="no visible sheets"):
                preprocess_xlsx(dummy)


# ---------------------------------------------------------------------------
# New condition / branch / URL tests (correction 14)
# ---------------------------------------------------------------------------

class TestTextPreprocessorConditions:
    def test_text_detect_condition_when(self) -> None:
        result = preprocess_text("when login succeeds go to dashboard")
        assert 1 in result.possible_condition_lines

    def test_text_detect_condition_unless(self) -> None:
        result = preprocess_text("unless user is already logged in, proceed")
        assert 1 in result.possible_condition_lines

    def test_text_detect_branch_arrow_notation(self) -> None:
        result = preprocess_text("-> success_path")
        kinds = [s.kind for s in result.sections]
        assert DetectedSectionKind.BRANCH_DESTINATION in kinds

    def test_text_url_trailing_punctuation_stripped(self) -> None:
        result = preprocess_text("See https://example.com. For details.")
        assert "https://example.com" in result.detected_urls
        assert "https://example.com." not in result.detected_urls


# ---------------------------------------------------------------------------
# Real XLSX test (correction 12)
# ---------------------------------------------------------------------------

def test_xlsx_real_workbook_normalizes_correctly(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    from sop_automation.preprocessing.xlsx_preprocessor import preprocess_xlsx
    from sop_automation.models.common import SourceFormat

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SOP"
    ws.append(["step_id", "action", "element_name", "element_type"])
    ws.append(["s1", "CLICK", "login_btn", "BUTTON"])
    xlsx_path = tmp_path / "test.xlsx"
    wb.save(str(xlsx_path))

    result = preprocess_xlsx(xlsx_path)
    assert result.source_format == SourceFormat.XLSX
    assert len(result.sections) == 1
