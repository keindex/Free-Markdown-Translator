from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ProviderConfig:
    name: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    model: str = "gpt-5-mini"
    temperature: float = 0.2
    max_tokens: int = 4000


@dataclass
class PipelineConfig:
    mode: str = "balanced"
    enable_review: bool = False
    enable_format_guard: bool = False
    fail_on_validation_error: bool = True
    review_min_bundle_chars: int = 1600
    review_min_segments: int = 6
    review_confidence_threshold: float = 0.85


@dataclass
class SegmentationConfig:
    max_bundle_chars: int = 6000
    max_bundle_segments: int = 12


@dataclass
class InputConfig:
    file_pattern: str = "*.md"


@dataclass
class StyleConfig:
    tone: str = "technical"
    preserve_terms: list[str] = field(default_factory=list)
    audience: str = "developers"
    instructions: list[str] = field(default_factory=list)


@dataclass
class OutputConfig:
    directory: str = "output"
    file_suffix_template: str = "{stem}.{lang}.md"
    write_report: bool = True


@dataclass
class ExecutionConfig:
    max_parallel_translations: int = 1


@dataclass
class TranslatorConfig:
    target_languages: list[str] = field(default_factory=lambda: ["zh-CN"])
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    segmentation: SegmentationConfig = field(default_factory=SegmentationConfig)
    input: InputConfig = field(default_factory=InputConfig)
    style: StyleConfig = field(default_factory=StyleConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)


def _workspace_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _default_config_dict() -> dict[str, Any]:
    return {
        "target_languages": ["zh-CN"],
        "provider": {
            "name": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": None,
            "api_key_env": "OPENAI_API_KEY",
            "model": "gpt-5-mini",
            "temperature": 0.2,
            "max_tokens": 4000,
        },
        "pipeline": {
            "mode": "balanced",
            "enable_review": False,
            "enable_format_guard": False,
            "fail_on_validation_error": True,
            "review_min_bundle_chars": 1600,
            "review_min_segments": 6,
            "review_confidence_threshold": 0.85,
        },
        "segmentation": {
            "max_bundle_chars": 6000,
            "max_bundle_segments": 12,
        },
        "input": {
            "file_pattern": "*.md",
        },
        "style": {
            "tone": "technical",
            "preserve_terms": ["Markdown", "OpenAI", "Python"],
            "audience": "developers",
            "instructions": [],
        },
        "output": {
            "directory": "output",
            "file_suffix_template": "{stem}.{lang}.md",
            "write_report": True,
        },
        "execution": {
            "max_parallel_translations": 1,
        },
    }

def _load_yaml_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _filter_known_keys(section: dict[str, Any], config_type, section_name: str) -> dict[str, Any]:
    allowed = {item.name for item in fields(config_type)}
    unknown = sorted(set(section) - allowed)
    if unknown:
        logging.warning("Ignoring unsupported config keys in %s: %s", section_name, ", ".join(unknown))
    return {key: value for key, value in section.items() if key in allowed}


def load_config(config_path: str | None = None) -> TranslatorConfig:
    root = _workspace_root()
    candidates = []
    if config_path:
        candidates.append(Path(config_path))
    candidates.extend(
        [
            root / "config.yaml",
            root / "src" / "config.yaml",
            root / "translator.yaml",
            root / "src" / "translator.yaml",
        ]
    )

    loaded: dict[str, Any] | None = None
    loaded_path: Path | None = None
    for candidate in candidates:
        if candidate.exists():
            loaded = _load_yaml_file(candidate)
            loaded_path = candidate
            break

    data = _default_config_dict()
    if loaded_path is not None and loaded is not None:
        data = _merge_dict(data, loaded)
        logging.info("Loaded config from %s", loaded_path)
    else:
        logging.info("No config file found, using defaults.")

    return TranslatorConfig(
        target_languages=list(data["target_languages"]),
        provider=ProviderConfig(
            **_filter_known_keys(data["provider"], ProviderConfig, "provider"),
        ),
        pipeline=PipelineConfig(**_filter_known_keys(data["pipeline"], PipelineConfig, "pipeline")),
        segmentation=SegmentationConfig(**_filter_known_keys(data["segmentation"], SegmentationConfig, "segmentation")),
        input=InputConfig(**_filter_known_keys(data["input"], InputConfig, "input")),
        style=StyleConfig(**_filter_known_keys(data["style"], StyleConfig, "style")),
        output=OutputConfig(**_filter_known_keys(data["output"], OutputConfig, "output")),
        execution=ExecutionConfig(**_filter_known_keys(data["execution"], ExecutionConfig, "execution")),
    )
