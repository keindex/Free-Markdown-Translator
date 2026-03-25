from __future__ import annotations

import json
import logging
from pathlib import Path

from src.agents.format_guard_agent import FormatGuardAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.agents.translator_agent import TranslatorAgent
from src.core.pipeline import TranslationPipeline
from src.infra.config import TranslatorConfig
from src.llm.client import OpenAIProvider
from src.parser.markdown_parser import MarkdownParser
from src.parser.segment_extractor import SegmentExtractor
from src.validators.markdown_validator import MarkdownValidator


def _build_provider(config: TranslatorConfig):
    if config.provider.name == "openai":
        try:
            return OpenAIProvider(
                base_url=config.provider.base_url,
                api_key=config.provider.api_key,
                api_key_env=config.provider.api_key_env,
                model=config.provider.model,
                temperature=config.provider.temperature,
                max_tokens=config.provider.max_tokens,
            )
        except Exception as exc:
            logging.warning("OpenAI provider unavailable, falling back to no-op translation: %s", exc)
            return None
    logging.warning("Provider %s is not implemented; falling back to no-op translation.", config.provider.name)
    return None


def build_pipeline(config: TranslatorConfig) -> TranslationPipeline:
    provider = _build_provider(config)
    return TranslationPipeline(
        config=config,
        parser=MarkdownParser(),
        extractor=SegmentExtractor(),
        translator_agent=TranslatorAgent(provider),
        reviewer_agent=ReviewerAgent(provider if config.pipeline.enable_review else None),
        format_guard_agent=FormatGuardAgent(provider if config.pipeline.enable_format_guard else None),
        validator=MarkdownValidator(),
    )


def _looks_like_output_path(value: str) -> bool:
    return value.endswith(".md") or "\\" in value or "/" in value


def translate_command(
    paths: list[str],
    target_langs: list[str],
    config: TranslatorConfig,
    output_path: str | None = None,
) -> int:
    if any(_looks_like_output_path(lang) for lang in target_langs):
        raise ValueError("`--to` expects language codes, not file paths. Use `--output` to specify an output file.")
    if output_path and (len(paths) != 1 or len(target_langs) != 1):
        raise ValueError("`--output` can only be used with one input file and one target language.")

    pipeline = build_pipeline(config)
    logging.info("Translate job started: files=%s targets=%s", len(paths), ", ".join(target_langs))
    for raw_path in paths:
        input_path = Path(raw_path)
        logging.info("Processing source file: %s", input_path)
        for target_lang in target_langs:
            resolved_output_path = Path(output_path) if output_path else None
            result = pipeline.run(input_path, target_lang, write_output=True, output_path=resolved_output_path)
            logging.info("Translated %s -> %s", input_path, result.output_path)
            if config.output.write_report and result.output_path is not None:
                report_path = result.output_path.with_suffix(result.output_path.suffix + ".report.json")
                report_path.write_text(json.dumps(result.report, ensure_ascii=False, indent=2), encoding="utf-8")
                logging.info("Wrote translation report: %s", report_path)
    return 0


def validate_command(path: str, config: TranslatorConfig) -> int:
    parser = MarkdownParser()
    validator = MarkdownValidator()
    input_path = Path(path)
    source_text = input_path.read_text(encoding="utf-8")
    parsed = parser.parse(source_text, input_path, config.target_languages[0])
    report = validator.validate(parsed, source_text)
    output = {
        "input_path": str(input_path),
        "validation_passed": report.passed,
        "errors": report.errors,
        "warnings": report.warnings,
        "metrics": report.metrics,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if report.passed else 1


def report_command(path: str, target_lang: str, config: TranslatorConfig) -> int:
    pipeline = build_pipeline(config)
    result = pipeline.run(Path(path), target_lang, write_output=False)
    print(json.dumps(result.report, ensure_ascii=False, indent=2))
    return 0
