from __future__ import annotations

from src.core.types import DocumentContext, ParsedDocument, Segment
from src.infra.config import TranslatorConfig


class DocumentContextBuilder:
    def build(self, doc: ParsedDocument, segments: list[Segment], config: TranslatorConfig, glossary: dict[str, str]) -> DocumentContext:
        title = str((doc.metadata.get("front_matter") or {}).get("title", ""))
        if not title:
            title = next((" / ".join(segment.context_path) for segment in segments if segment.context_path), "")
        abstract = next((segment.source_text for segment in segments if segment.node_type == "paragraph"), "")
        section_summaries: dict[str, str] = {}
        for segment in segments:
            if not segment.context_path:
                continue
            path = " / ".join(segment.context_path)
            if path not in section_summaries and segment.node_type == "paragraph":
                section_summaries[path] = segment.source_text[:200]
        style_guide = [f"Tone: {config.style.tone}", f"Audience: {config.style.audience}", *config.style.instructions]
        if config.style.preserve_terms:
            style_guide.append("Preserve these terms: " + ", ".join(config.style.preserve_terms))
        return DocumentContext(
            title=title,
            abstract=abstract,
            section_summaries=section_summaries,
            glossary=glossary,
            style_guide=style_guide,
            audience=config.style.audience,
        )
