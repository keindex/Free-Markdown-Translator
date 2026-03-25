from __future__ import annotations

import logging
from dataclasses import dataclass, field
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
    enable_translation_memory: bool = False
    fail_on_validation_error: bool = True
    review_min_bundle_chars: int = 1600
    review_min_segments: int = 6
    review_confidence_threshold: float = 0.85


@dataclass
class SegmentationConfig:
    max_bundle_chars: int = 6000
    min_bundle_segments: int = 3
    max_bundle_segments: int = 12


@dataclass
class StyleConfig:
    tone: str = "technical"
    preserve_terms: list[str] = field(default_factory=list)
    audience: str = "developers"
    instructions: list[str] = field(default_factory=list)


@dataclass
class OutputConfig:
    file_suffix_template: str = "{stem}.{lang}.md"
    write_report: bool = True


@dataclass
class TranslatorConfig:
    target_languages: list[str] = field(default_factory=lambda: ["zh-CN"])
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    segmentation: SegmentationConfig = field(default_factory=SegmentationConfig)
    style: StyleConfig = field(default_factory=StyleConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    glossary_path: str | None = None


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
            "enable_translation_memory": False,
            "fail_on_validation_error": True,
            "review_min_bundle_chars": 1600,
            "review_min_segments": 6,
            "review_confidence_threshold": 0.85,
        },
        "segmentation": {
            "max_bundle_chars": 6000,
            "min_bundle_segments": 3,
            "max_bundle_segments": 12,
        },
        "style": {
            "tone": "technical",
            "preserve_terms": ["Markdown", "OpenAI", "Python"],
            "audience": "developers",
            "instructions": [],
        },
        "output": {
            "file_suffix_template": "{stem}.{lang}.md",
            "write_report": True,
        },
        "glossary_path": None,
    }

def _load_yaml_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_config(config_path: str | None = None) -> TranslatorConfig:
    root = _workspace_root()
    candidates = []
    if config_path:
        candidates.append(Path(config_path))
    candidates.extend([root / "translator.yaml", root / "src" / "translator.yaml"])

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
        logging.info("No translator config found, using defaults.")

    return TranslatorConfig(
        target_languages=list(data["target_languages"]),
        provider=ProviderConfig(
            name=data["provider"]["name"],
            base_url=data["provider"]["base_url"],
            api_key=data["provider"].get("api_key"),
            api_key_env=data["provider"].get("api_key_env", ""),
            model=data["provider"]["model"],
            temperature=data["provider"]["temperature"],
            max_tokens=data["provider"]["max_tokens"],
        ),
        pipeline=PipelineConfig(**data["pipeline"]),
        segmentation=SegmentationConfig(**data["segmentation"]),
        style=StyleConfig(**data["style"]),
        output=OutputConfig(**data["output"]),
        glossary_path=data.get("glossary_path"),
    )
