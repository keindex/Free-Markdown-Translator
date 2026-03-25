from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt

from src.core.types import ParsedDocument
from src.parser.frontmatter import split_front_matter


class MarkdownParser:
    def __init__(self) -> None:
        self.md = MarkdownIt("commonmark", {"html": True}).enable("table")

    def parse(self, text: str, source_path: Path, target_lang: str) -> ParsedDocument:
        front_matter = split_front_matter(text)
        body_lines = front_matter.body.splitlines()
        if front_matter.body.endswith("\n"):
            body_lines.append("")
        tokens = self.md.parse(front_matter.body)
        metadata = {"front_matter": front_matter.data, "front_matter_raw": front_matter.raw}
        return ParsedDocument(
            source_path=source_path,
            source_text=text,
            body_text=front_matter.body,
            target_lang=target_lang,
            ast=tokens,
            metadata=metadata,
            lines=body_lines,
            body_line_offset=front_matter.line_count,
        )
