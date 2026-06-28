"""Text/Markdown SOP preprocessor — deterministic structural feature detection only."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sop_automation.models.common import SourceFormat
from sop_automation.models.sop import (
    DetectedSection,
    DetectedSectionKind,
)


@dataclass
class PreprocessedSource:
    source_format: SourceFormat
    normalized_text: str
    sections: list[DetectedSection] = field(default_factory=list)
    detected_urls: list[str] = field(default_factory=list)
    detected_placeholders: list[str] = field(default_factory=list)
    capability_hints: list[str] = field(default_factory=list)
    possible_condition_lines: list[int] = field(default_factory=list)
    possible_deferred_lines: list[int] = field(default_factory=list)


_URL_RE = re.compile(r'https?://\S+')
_PLACEHOLDER_RE = re.compile(r'\{\{input\.\w+\}\}')
_TOOL_MARKER_RE = re.compile(r':\s*tool\b', re.IGNORECASE)
_DEFERRED_RE = re.compile(r'will be created later', re.IGNORECASE)
_CONDITION_RE = re.compile(r'\b(if|otherwise|unless|when|until|wait)\b', re.IGNORECASE)
_BRANCH_RE = re.compile(r'^(?:->|→|>)\s*\w')
_NUMBERED_RE = re.compile(r'^\d+[.)]\s')
_BULLET_RE = re.compile(r'^[-*•]\s')


def preprocess_text(text: str) -> PreprocessedSource:
    """Detect deterministic structural features from TXT/MD source. No NL inference."""
    lines = text.splitlines()
    sections: list[DetectedSection] = []
    detected_urls: list[str] = []
    detected_placeholders: list[str] = []
    capability_hints: list[str] = []
    possible_condition_lines: list[int] = []
    possible_deferred_lines: list[int] = []

    for i, line in enumerate(lines):
        lineno = i + 1  # 1-based
        stripped = line.strip()
        if not stripped:
            continue

        # Headings: # prefix or ALL-CAPS ≥4 chars with no lowercase
        if stripped.startswith('#'):
            sections.append(DetectedSection(
                kind=DetectedSectionKind.HEADING,
                line_start=lineno,
                line_end=lineno,
                text=stripped,
            ))
        elif len(stripped) >= 4 and stripped == stripped.upper() and any(c.isalpha() for c in stripped):
            sections.append(DetectedSection(
                kind=DetectedSectionKind.HEADING,
                line_start=lineno,
                line_end=lineno,
                text=stripped,
            ))
        elif _NUMBERED_RE.match(stripped):
            sections.append(DetectedSection(
                kind=DetectedSectionKind.NUMBERED_LIST,
                line_start=lineno,
                line_end=lineno,
                text=stripped,
            ))
        elif _BULLET_RE.match(stripped):
            sections.append(DetectedSection(
                kind=DetectedSectionKind.BULLET_LIST,
                line_start=lineno,
                line_end=lineno,
                text=stripped,
            ))

        # URLs
        for url in _URL_RE.findall(line):
            url = url.rstrip('.,);:\'"')
            if url and url not in detected_urls:
                detected_urls.append(url)

        # Input placeholders
        for ph in _PLACEHOLDER_RE.findall(line):
            if ph not in detected_placeholders:
                detected_placeholders.append(ph)

        # ": tool" marker — entire line is a capability hint
        if _TOOL_MARKER_RE.search(line):
            capability_hints.append(stripped)
            sections.append(DetectedSection(
                kind=DetectedSectionKind.TOOL_MARKER,
                line_start=lineno,
                line_end=lineno,
                text=stripped,
            ))

        # Deferred marker
        if _DEFERRED_RE.search(line):
            possible_deferred_lines.append(lineno)
            sections.append(DetectedSection(
                kind=DetectedSectionKind.DEFERRED_MARKER,
                line_start=lineno,
                line_end=lineno,
                text=stripped,
            ))

        # Condition words
        if _CONDITION_RE.search(line):
            possible_condition_lines.append(lineno)
            if not any(
                s.line_start == lineno and s.kind == DetectedSectionKind.CONDITION_LINE
                for s in sections
            ):
                sections.append(DetectedSection(
                    kind=DetectedSectionKind.CONDITION_LINE,
                    line_start=lineno,
                    line_end=lineno,
                    text=stripped,
                ))

        # Branch destination: lines starting with →, ->, or >
        if _BRANCH_RE.match(stripped):
            sections.append(DetectedSection(
                kind=DetectedSectionKind.BRANCH_DESTINATION,
                line_start=lineno,
                line_end=lineno,
                text=stripped,
            ))

    return PreprocessedSource(
        source_format=SourceFormat.NATURAL_LANGUAGE,
        normalized_text=text,
        sections=sections,
        detected_urls=detected_urls,
        detected_placeholders=detected_placeholders,
        capability_hints=capability_hints,
        possible_condition_lines=possible_condition_lines,
        possible_deferred_lines=possible_deferred_lines,
    )
