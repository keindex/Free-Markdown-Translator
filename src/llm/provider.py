from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.core.types import ApiUsageSummary


class LLMProvider(ABC):
    @abstractmethod
    def chat_json(self, system_prompt: str, user_prompt: str, call_label: str = "llm") -> Any:
        raise NotImplementedError

    @abstractmethod
    def get_usage_summary(self) -> ApiUsageSummary:
        raise NotImplementedError
