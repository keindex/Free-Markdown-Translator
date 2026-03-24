from __future__ import annotations

from pathlib import Path

import yaml


class Glossary:
    def load(self, path: str | None) -> dict[str, str]:
        if not path:
            return {}
        glossary_path = Path(path)
        if not glossary_path.exists():
            return {}
        with glossary_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items()}
