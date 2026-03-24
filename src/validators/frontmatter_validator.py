from __future__ import annotations

from src.core.types import ValidationReport
from src.parser.frontmatter import split_front_matter


class FrontMatterValidator:
    def validate(self, output_text: str) -> ValidationReport:
        try:
            split_front_matter(output_text)
            return ValidationReport(passed=True)
        except Exception as exc:
            return ValidationReport(passed=False, errors=[f"Front matter parse failed: {exc}"])
