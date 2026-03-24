from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    def chat_json(self, system_prompt: str, user_prompt: str, call_label: str = "llm") -> Any:
        raise NotImplementedError
