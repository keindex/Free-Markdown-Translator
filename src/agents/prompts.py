from __future__ import annotations

import json

from src.core.types import DocumentContext, SegmentBundle, TranslationResult


def build_translator_prompts(bundle: SegmentBundle, context: DocumentContext, source_lang: str, target_lang: str) -> tuple[str, str]:
    system_prompt = f"""
# Role
You are an expert Markdown Localization Agent specializing in technical documentation translation from {source_lang}(auto means auto detect) to {target_lang}.

# Constraints & Rules
1. **Output Format**: Return ONLY a valid JSON object. Do NOT wrap the output in markdown code blocks (e.g., no ```json).
2. **Placeholders**: Preserve ALL placeholders (e.g., {{variable}}, <tag>, [ref]) EXACTLY as they appear in the source. Do not translate, modify, or reorder them.
3. **Markdown Integrity**: Maintain all Markdown syntax (links, images, bold, lists, code blocks). Do not break structural elements.
4. **Consistency**: Ensure terminology consistency across all segments within this bundle.
5. **Context Priority**: 
   - Glossary terms MUST be translated exactly as defined in the provided glossary.
   - Adhere strictly to the Style Guide and Audience settings.
   - Use Document Abstract and Section Summaries to understand the broader context for ambiguous terms.

# Output Schema
Your response must match this JSON structure exactly:
{{
    "bundle_id": "string",
    "translations": [
        {{
            "segment_id": "string",
            "translated_text": "string"
        }}
    ]
}}
""".strip()
    payload = {
        "task": "translate",
        "source_language": source_lang,
        "target_language": target_lang,
        "document_context": {
            "title": context.title,
            "abstract": context.abstract,
            "section_summaries": context.section_summaries,
            "glossary": context.glossary,
            "style_guide": context.style_guide,
            "audience": context.audience,
            "usage_note": "Use the abstract and summaries to resolve ambiguity. Apply style_guide to all segments."
        },
        "bundle": {
            "bundle_id": bundle.bundle_id,
            "summary_before": bundle.summary_before,
            "summary_after": bundle.summary_after,
            "glossary_terms": bundle.glossary_terms,
            "style_instructions": bundle.style_instructions,
            "segments": [
                {
                    "segment_id": segment.segment_id,
                    "node_type": segment.node_type,
                    "context_path": segment.context_path,
                    "source_text": segment.source_text,
                    "protected_placeholders": [span.placeholder for span in segment.protected_spans],
                }
                for segment in bundle.segments
            ],
        },
    }
    return system_prompt, json.dumps(payload, ensure_ascii=False, indent=2)


def build_reviewer_prompts(bundle: SegmentBundle, context: DocumentContext, translations: list[TranslationResult]) -> tuple[str, str]:
    system_prompt = "You are a bilingual reviewer. Improve consistency only when needed, preserve placeholders, and return JSON only."
    payload = {
        "task": "review",
        "context": {
            "title": context.title,
            "glossary": context.glossary,
            "style_guide": context.style_guide,
        },
        "translations": [
            {
                "segment_id": segment.segment_id,
                "source_text": segment.source_text,
                "translated_text": translation.translated_text,
            }
            for segment, translation in zip(bundle.segments, translations)
        ],
    }
    return system_prompt, json.dumps(payload, ensure_ascii=False, indent=2)


def build_guard_prompts(bundle: SegmentBundle, translations: list[TranslationResult]) -> tuple[str, str]:
    system_prompt = "You are a markdown format guard. Only make minimal syntax-safe repairs, preserve placeholders, and return JSON only."
    payload = {
        "task": "format_guard",
        "translations": [
            {
                "segment_id": segment.segment_id,
                "source_text": segment.source_text,
                "translated_text": translation.translated_text,
                "protected_placeholders": [span.placeholder for span in segment.protected_spans],
            }
            for segment, translation in zip(bundle.segments, translations)
        ],
    }
    return system_prompt, json.dumps(payload, ensure_ascii=False, indent=2)
