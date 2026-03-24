from __future__ import annotations

from src.core.types import ParsedDocument
from src.parser.ast_mapper import AstMapper


class MarkdownRenderer:
    def __init__(self) -> None:
        self.mapper = AstMapper()

    def render(self, doc: ParsedDocument) -> str:
        return self.mapper.render(doc)
