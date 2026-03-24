from __future__ import annotations

from src.core.types import ParsedDocument, ValidationReport
from src.validators.frontmatter_validator import FrontMatterValidator
from src.validators.structure_validator import StructureValidator


class MarkdownValidator:
    def __init__(self) -> None:
        self.frontmatter_validator = FrontMatterValidator()
        self.structure_validator = StructureValidator()

    def validate(self, source_doc: ParsedDocument, output_text: str) -> ValidationReport:
        frontmatter_report = self.frontmatter_validator.validate(output_text)
        structure_report = self.structure_validator.validate(source_doc, output_text)
        return ValidationReport(
            passed=frontmatter_report.passed and structure_report.passed,
            errors=[*frontmatter_report.errors, *structure_report.errors],
            warnings=[*frontmatter_report.warnings, *structure_report.warnings],
            metrics={**frontmatter_report.metrics, **structure_report.metrics},
        )
