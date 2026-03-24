from __future__ import annotations

from copy import deepcopy

from src.core.types import ParsedDocument, TranslationResult
from src.parser.frontmatter import dump_front_matter


class AstMapper:
    def apply(self, doc: ParsedDocument, translations: list[TranslationResult]) -> ParsedDocument:
        updated = deepcopy(doc)
        body_lines = list(updated.lines)
        translation_map = {item.segment_id: item.translated_text for item in translations}

        for segment in sorted(
            [s for s in getattr(updated, "segments", []) if s.segment_id in translation_map and s.node_type != "front_matter"],
            key=lambda item: item.metadata["body_line_start"],
            reverse=True,
        ):
            start = segment.metadata["body_line_start"]
            end = segment.metadata["body_line_end"]
            new_lines = translation_map[segment.segment_id].splitlines()
            if translation_map[segment.segment_id].endswith("\n"):
                new_lines.append("")
            body_lines[start:end] = new_lines

        updated.lines = body_lines
        updated.body_text = "\n".join(body_lines)
        if doc.body_text.endswith("\n") and not updated.body_text.endswith("\n"):
            updated.body_text += "\n"

        front_matter = dict(updated.metadata.get("front_matter") or {})
        changed_frontmatter = False
        for segment in getattr(updated, "segments", []):
            if segment.node_type != "front_matter" or segment.segment_id not in translation_map:
                continue
            front_matter[segment.metadata["front_matter_key"]] = translation_map[segment.segment_id]
            changed_frontmatter = True
        if changed_frontmatter:
            updated.metadata["front_matter"] = front_matter
        return updated

    def render(self, doc: ParsedDocument) -> str:
        front_matter = doc.metadata.get("front_matter") or {}
        prefix = ""
        if front_matter:
            prefix = f"---\n{dump_front_matter(front_matter)}\n---\n"
        return f"{prefix}{doc.body_text}"
