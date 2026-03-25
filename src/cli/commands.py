from __future__ import annotations

import copy
import json
import logging
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path

from src.agents.format_guard_agent import FormatGuardAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.agents.translator_agent import TranslatorAgent
from src.core.pipeline import TranslationPipeline
from src.infra.config import TranslatorConfig
from src.infra.logging import log_task_context
from src.llm.client import OpenAIProvider
from src.parser.markdown_parser import MarkdownParser
from src.parser.segment_extractor import SegmentExtractor
from src.validators.markdown_validator import MarkdownValidator


def _build_provider(config: TranslatorConfig):
    if config.provider.name == "openai":
        return OpenAIProvider(
            base_url=config.provider.base_url,
            api_key=config.provider.api_key,
            api_key_env=config.provider.api_key_env,
            model=config.provider.model,
            temperature=config.provider.temperature,
            max_tokens=config.provider.max_tokens,
        )
    raise ValueError(f"Provider {config.provider.name} is not implemented.")


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


@dataclass(frozen=True)
class TranslationTask:
    index: int
    total: int
    input_path: Path
    target_lang: str
    output_path: Path | None

    @property
    def label(self) -> str:
        return f"{self.index}/{self.total} {self.input_path.name} -> {self.target_lang}"


def _resolve_parallel_workers(config: TranslatorConfig, task_count: int) -> int:
    configured = max(1, config.execution.max_parallel_translations)
    return min(configured, max(1, task_count))


def _build_translation_tasks(paths: list[str], target_langs: list[str], output_path: str | None) -> list[TranslationTask]:
    total = len(paths) * len(target_langs)
    tasks: list[TranslationTask] = []
    index = 1
    for raw_path in paths:
        input_path = Path(raw_path)
        for target_lang in target_langs:
            tasks.append(
                TranslationTask(
                    index=index,
                    total=total,
                    input_path=input_path,
                    target_lang=target_lang,
                    output_path=Path(output_path) if output_path else None,
                )
            )
            index += 1
    return tasks


def _run_translation_task(task: TranslationTask, config: TranslatorConfig):
    with log_task_context(task.label):
        pipeline = build_pipeline(copy.deepcopy(config))
        logging.info("Translation task started: source=%s target=%s", task.input_path, task.target_lang)
        result = pipeline.run(task.input_path, task.target_lang, write_output=True, output_path=task.output_path)
        logging.info("Translation task finished: output=%s", result.output_path)
        return task, result


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

    tasks = _build_translation_tasks(paths, target_langs, output_path)
    max_workers = _resolve_parallel_workers(config, len(tasks))
    logging.info(
        "Translate job started: files=%s targets=%s tasks=%s max_parallel=%s",
        len(paths),
        ", ".join(target_langs),
        len(tasks),
        max_workers,
    )

    if max_workers == 1:
        for task in tasks:
            _, result = _run_translation_task(task, config)
            if config.output.write_report and result.output_path is not None:
                report_path = result.output_path.with_suffix(result.output_path.suffix + ".report.json")
                report_path.write_text(json.dumps(result.report, ensure_ascii=False, indent=2), encoding="utf-8")
                logging.info("Wrote translation report: %s", report_path)
        return 0

    completed = 0
    future_to_task = {}
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="mdtx-translate") as executor:
        for task in tasks:
            future_to_task[executor.submit(_run_translation_task, task, config)] = task

        pending = set(future_to_task)
        while pending:
            done, pending = wait(pending, return_when=FIRST_EXCEPTION)
            for future in done:
                task = future_to_task[future]
                try:
                    _, result = future.result()
                except Exception:
                    for pending_future in pending:
                        pending_future.cancel()
                    logging.exception(
                        "Translation task failed: source=%s target=%s",
                        task.input_path,
                        task.target_lang,
                    )
                    raise

                completed += 1
                if config.output.write_report and result.output_path is not None:
                    report_path = result.output_path.with_suffix(result.output_path.suffix + ".report.json")
                    report_path.write_text(json.dumps(result.report, ensure_ascii=False, indent=2), encoding="utf-8")
                    logging.info(
                        "[%s/%s] Wrote translation report: %s",
                        completed,
                        len(tasks),
                        report_path,
                    )
                logging.info(
                    "[%s/%s] Completed translation: %s -> %s",
                    completed,
                    len(tasks),
                    task.input_path,
                    result.output_path,
                )
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
