from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class FrontMatterData:
    raw: str
    data: dict[str, Any]
    body: str
    line_count: int


def split_front_matter(text: str) -> FrontMatterData:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return FrontMatterData(raw="", data={}, body=text, line_count=0)

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            raw_lines = lines[1:index]
            body = "\n".join(lines[index + 1 :])
            if text.endswith("\n"):
                body += "\n"
            raw = "\n".join(raw_lines)
            try:
                data = yaml.safe_load(raw) or {}
            except yaml.YAMLError as exc:
                logger.warning("Skipping invalid YAML frontmatter: %s", exc)
                return FrontMatterData(raw="", data={}, body=text, line_count=0)
            return FrontMatterData(raw=raw, data=data, body=body, line_count=index + 1)

    return FrontMatterData(raw="", data={}, body=text, line_count=0)


def dump_front_matter(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip()
