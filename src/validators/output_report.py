from __future__ import annotations

from src.core.types import PipelineResult


class OutputReportBuilder:
    def build(self, result: PipelineResult) -> dict:
        return {
            "input_path": str(result.input_path),
            "output_path": str(result.output_path) if result.output_path else None,
            "segment_count": len(result.segments),
            "translation_count": len(result.translations),
            "validation_passed": result.validation.passed,
            "errors": result.validation.errors,
            "warnings": result.validation.warnings,
            "metrics": result.validation.metrics,
        }
