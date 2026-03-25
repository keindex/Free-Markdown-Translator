from __future__ import annotations

import json

from src.core.types import DocumentContext, SegmentBundle, TranslationResult


def _compact_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _compact_context(context: DocumentContext) -> dict:
    payload: dict[str, object] = {}
    if context.title:
        payload["title"] = context.title[:120]
    if context.style_guide:
        payload["style"] = context.style_guide[:3]
    return payload


def build_translator_prompts(bundle: SegmentBundle, context: DocumentContext, target_lang: str) -> tuple[str, str]:
    system_prompt = (
        f"You are an expert Markdown translation specialist. Detect the source language automatically and translate markdown text to {target_lang}. "
        'Input JSON fields: task=job type, ctx=shared document hints, segments=list of units to translate, '
        "segment_id=stable output key, context=local section path, text=source text. "
        'Return JSON only: {"translations":[{"segment_id":"...","translated_text":"..."}]}. '
        "Translate only text, **preserve placeholders**, URLs, code, and markdown control syntax exactly."
    )
    payload = {
        "task": "translate",
        "ctx": _compact_context(context),
        "segments": [
                {
                    "segment_id": segment.segment_id,
                    "context": " / ".join(segment.context_path[-2:]) if segment.context_path else "",
                    "text": segment.source_text,
                }
                for segment in bundle.segments
            ],
    }
    return system_prompt, _compact_json(payload)


def build_reviewer_prompts(bundle: SegmentBundle, context: DocumentContext, translations: list[TranslationResult]) -> tuple[str, str]:
    system_prompt = (
        'Review translations only if needed. Return JSON only: {"translations":[{"segment_id":"...","translated_text":"..."}]}. '
        "Keep placeholders and markdown syntax unchanged."
    )
    payload = {
        "task": "review",
        "ctx": _compact_context(context),
        "translations": [
            {
                "segment_id": segment.segment_id,
                "source": segment.source_text,
                "text": translation.translated_text,
            }
            for segment, translation in zip(bundle.segments, translations)
        ],
    }
    return system_prompt, _compact_json(payload)


def build_guard_prompts(bundle: SegmentBundle, translations: list[TranslationResult]) -> tuple[str, str]:
    system_prompt = (
        'Repair markdown-format issues only. Return JSON only: {"translations":[{"segment_id":"...","translated_text":"..."}]}. '
        "Make minimal edits and keep placeholders unchanged."
    )
    payload = {
        "task": "format_guard",
        "translations": [
            {
                "segment_id": segment.segment_id,
                "source": segment.source_text,
                "text": translation.translated_text,
            }
            for segment, translation in zip(bundle.segments, translations)
        ],
    }
    return system_prompt, _compact_json(payload)
