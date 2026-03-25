from __future__ import annotations

from src.agents.prompts import build_translator_prompts
from src.core.types import DocumentContext, SegmentBundle, TranslationResult
from src.llm.provider import LLMProvider


class TranslatorAgent:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider

    def translate_bundle(self, bundle: SegmentBundle, context: DocumentContext, target_lang: str) -> list[TranslationResult]:
        if self.provider is None:
            return [
                TranslationResult(
                    segment_id=segment.segment_id,
                    translated_text=segment.source_text,
                    notes=["No provider configured; source text returned unchanged."],
                    confidence=0.0,
                )
                for segment in bundle.segments
            ]

        system_prompt, user_prompt = build_translator_prompts(bundle, context, target_lang)
        payload = self.provider.chat_json(system_prompt, user_prompt, call_label="translate")
        return [
            TranslationResult(
                segment_id=item["segment_id"],
                translated_text=item["translated_text"],
                notes=item.get("notes", []),
                applied_terms=item.get("applied_terms", {}),
                confidence=float(item.get("confidence", 0.0)),
            )
            for item in payload.get("translations", [])
        ]
