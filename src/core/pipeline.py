from __future__ import annotations

import logging
from pathlib import Path

from src.agents.format_guard_agent import FormatGuardAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.agents.translator_agent import TranslatorAgent
from src.core.errors import TranslationPipelineError
from src.core.orchestrator import Orchestrator
from src.core.types import PipelineResult, TranslationResult
from src.infra.config import TranslatorConfig
from src.memory.document_context import DocumentContextBuilder
from src.memory.glossary import Glossary
from src.parser.ast_mapper import AstMapper
from src.parser.markdown_parser import MarkdownParser
from src.parser.renderer import MarkdownRenderer
from src.parser.segment_extractor import ProtectedSpanProcessor, SegmentExtractor
from src.validators.markdown_validator import MarkdownValidator
from src.validators.output_report import OutputReportBuilder


class TranslationPipeline:
    def __init__(
        self,
        config: TranslatorConfig,
        parser: MarkdownParser,
        extractor: SegmentExtractor,
        translator_agent: TranslatorAgent,
        reviewer_agent: ReviewerAgent,
        format_guard_agent: FormatGuardAgent,
        validator: MarkdownValidator,
    ) -> None:
        self.config = config
        self.parser = parser
        self.extractor = extractor
        self.translator_agent = translator_agent
        self.reviewer_agent = reviewer_agent
        self.format_guard_agent = format_guard_agent
        self.validator = validator
        self.context_builder = DocumentContextBuilder()
        self.glossary = Glossary()
        self.orchestrator = Orchestrator()
        self.protected_span_processor = ProtectedSpanProcessor()
        self.mapper = AstMapper()
        self.renderer = MarkdownRenderer()
        self.report_builder = OutputReportBuilder()

    def run(self, input_path: Path, target_lang: str, write_output: bool = True, output_path: Path | None = None) -> PipelineResult:
        logging.info("Pipeline start: source=%s target=%s", input_path, target_lang)
        source_text = input_path.read_text(encoding="utf-8")
        parsed = self.parser.parse(source_text, input_path, target_lang)
        logging.info("Parsed markdown document.")
        segments = self.extractor.extract(parsed)
        parsed.segments = segments  # type: ignore[attr-defined]
        logging.info("Extracted %s translatable segments.", len(segments))

        glossary = self.glossary.load(self.config.glossary_path)
        context = self.context_builder.build(parsed, segments, self.config, glossary)
        bundles = self.orchestrator.build_bundles(segments, context, self.config)
        logging.info("Built %s translation bundles.", len(bundles))

        all_translations: list[TranslationResult] = []
        segment_lookup = {segment.segment_id: segment for segment in segments}
        mode = self._normalized_mode()
        for index, bundle in enumerate(bundles, start=1):
            logging.info(
                "Translating bundle %s/%s: id=%s segments=%s",
                index,
                len(bundles),
                bundle.bundle_id,
                len(bundle.segments),
            )
            translations = self.translator_agent.translate_bundle(
                bundle=bundle,
                context=context,
                target_lang=target_lang,
            )
            if self._should_run_review(bundle, translations):
                logging.info("Reviewing bundle %s (mode=%s).", bundle.bundle_id, mode)
                translations = self.reviewer_agent.review_bundle(bundle, translations, context)
            for item in translations:
                item.translated_text = self.protected_span_processor.restore(item.translated_text, segment_lookup[item.segment_id])
            all_translations.extend(translations)

        output_text, validation, all_translations = self._render_and_validate(
            parsed=parsed,
            segments=segments,
            translations=all_translations,
        )
        if not validation.passed and self._should_run_format_guard(validation):
            logging.info(
                "Validation failed; running format guard fallback (mode=%s errors=%s).",
                mode,
                len(validation.errors),
            )
            repaired = []
            translations_by_bundle = self._translations_by_bundle(bundles, all_translations)
            for bundle in bundles:
                bundle_translations = translations_by_bundle[bundle.bundle_id]
                repaired.extend(self.format_guard_agent.repair_bundle(bundle, bundle_translations))
            for item in repaired:
                item.translated_text = self.protected_span_processor.restore(item.translated_text, segment_lookup[item.segment_id])
            output_text, validation, all_translations = self._render_and_validate(
                parsed=parsed,
                segments=segments,
                translations=repaired,
            )

        if self.config.pipeline.fail_on_validation_error and not validation.passed:
            raise TranslationPipelineError("; ".join(validation.errors))

        final_output_path = output_path or self._build_output_path(input_path, target_lang)
        if write_output:
            final_output_path.write_text(output_text, encoding="utf-8")
            logging.info("Wrote translated markdown: %s", final_output_path)

        result = PipelineResult(
            input_path=input_path,
            output_path=final_output_path if write_output else None,
            translated_text=output_text,
            segments=segments,
            translations=all_translations,
            validation=validation,
        )
        result.report = self.report_builder.build(result)
        return result

    def _build_output_path(self, input_path: Path, target_lang: str) -> Path:
        normalized_lang = self._normalize_lang_for_filename(target_lang)
        file_name = self.config.output.file_suffix_template.format(stem=input_path.stem, lang=normalized_lang)
        return input_path.with_name(file_name)

    @staticmethod
    def _normalize_lang_for_filename(target_lang: str) -> str:
        return target_lang.split("-")[0].split("_")[0].lower()

    def _normalized_mode(self) -> str:
        mode = (self.config.pipeline.mode or "balanced").strip().lower()
        if mode not in {"fast", "balanced", "strict"}:
            return "balanced"
        return mode

    def _should_run_review(self, bundle, translations: list[TranslationResult]) -> bool:
        if self.config.pipeline.enable_review:
            return True

        mode = self._normalized_mode()
        if mode == "fast":
            return False
        if mode == "strict":
            return True

        bundle_chars = sum(len(segment.source_text) for segment in bundle.segments)
        low_confidence = any(item.confidence < self.config.pipeline.review_confidence_threshold for item in translations)
        has_notes = any(item.notes for item in translations)
        return (
            len(bundle.segments) >= self.config.pipeline.review_min_segments
            or bundle_chars >= self.config.pipeline.review_min_bundle_chars
            or low_confidence
            or has_notes
        )

    def _should_run_format_guard(self, validation) -> bool:
        if self.config.pipeline.enable_format_guard:
            return True
        return self._normalized_mode() in {"balanced", "strict"} and not validation.passed

    def _render_and_validate(self, parsed, segments, translations):
        updated = self.mapper.apply(parsed, translations)
        updated.segments = segments  # type: ignore[attr-defined]
        output_text = self.renderer.render(updated)
        logging.info("Rendered translated markdown.")
        validation = self.validator.validate(parsed, output_text)
        logging.info(
            "Validation finished: passed=%s errors=%s warnings=%s",
            validation.passed,
            len(validation.errors),
            len(validation.warnings),
        )
        return output_text, validation, translations

    @staticmethod
    def _translations_by_bundle(bundles, translations: list[TranslationResult]) -> dict[str, list[TranslationResult]]:
        translation_map = {item.segment_id: item for item in translations}
        output: dict[str, list[TranslationResult]] = {}
        for bundle in bundles:
            output[bundle.bundle_id] = [translation_map[segment.segment_id] for segment in bundle.segments if segment.segment_id in translation_map]
        return output
