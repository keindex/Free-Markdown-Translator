from __future__ import annotations

from src.agents.prompts import build_guard_prompts
from src.core.types import SegmentBundle, TranslationResult
from src.llm.provider import LLMProvider


class FormatGuardAgent:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider

    def repair_bundle(self, bundle: SegmentBundle, translations: list[TranslationResult]) -> list[TranslationResult]:
        if self.provider is None:
            return translations

        system_prompt, user_prompt = build_guard_prompts(bundle, translations)
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                payload = self.provider.chat_json(system_prompt, user_prompt, call_label="format_guard")
                repaired = {item["segment_id"]: item for item in payload.get("translations", [])}
                results: list[TranslationResult] = []
                for item in translations:
                    current = repaired.get(item.segment_id)
                    if current is None:
                        results.append(item)
                        continue
                    results.append(
                        TranslationResult(
                            segment_id=item.segment_id,
                            translated_text=current.get("translated_text", item.translated_text),
                            notes=current.get("notes", item.notes),
                            applied_terms=current.get("applied_terms", item.applied_terms),
                            confidence=float(current.get("confidence", item.confidence)),
                        )
                    )
                return results
            except Exception as exc:
                if attempt < max_attempts:
                    logging.warning("Format guard attempt %d/%d failed: %s", attempt, max_attempts, exc)
                    continue
                logging.error("Format guard failed after %d attempts, returning original translations: %s", max_attempts, exc)
                return translations
        return translations
