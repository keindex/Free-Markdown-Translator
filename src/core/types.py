from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProtectedSpan:
    placeholder: str
    original_text: str
    span_type: str


@dataclass
class Segment:
    segment_id: str
    node_type: str
    source_text: str
    context_path: list[str]
    line_start: int
    line_end: int
    metadata: dict[str, Any] = field(default_factory=dict)
    protected_spans: list[ProtectedSpan] = field(default_factory=list)


@dataclass
class SegmentBundle:
    bundle_id: str
    segments: list[Segment]
    summary_before: str
    summary_after: str
    glossary_terms: dict[str, str]
    style_instructions: list[str]


@dataclass
class TranslationResult:
    segment_id: str
    translated_text: str
    notes: list[str] = field(default_factory=list)
    applied_terms: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class ValidationReport:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentContext:
    title: str
    abstract: str
    section_summaries: dict[str, str]
    glossary: dict[str, str]
    style_guide: list[str]
    audience: str


@dataclass
class ParsedDocument:
    source_path: Path
    source_text: str
    body_text: str
    target_lang: str
    ast: list[Any]
    metadata: dict[str, Any]
    lines: list[str]
    body_line_offset: int = 0


@dataclass
class PipelineResult:
    input_path: Path
    output_path: Path | None
    translated_text: str
    segments: list[Segment]
    translations: list[TranslationResult]
    validation: ValidationReport
    report: dict[str, Any] = field(default_factory=dict)
