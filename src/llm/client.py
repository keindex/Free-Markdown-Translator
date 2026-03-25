from __future__ import annotations

import json
import logging
import os
import threading
import time

from src.core.types import ApiUsageSummary
from src.llm.provider import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        api_key_env: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        from openai import OpenAI

        resolved_api_key = self._resolve_api_key(api_key=api_key, api_key_env=api_key_env)
        self.client = OpenAI(api_key=resolved_api_key or "mdtx-no-auth", base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._usage_lock = threading.Lock()
        self._usage_summary = ApiUsageSummary()

    def chat_json(self, system_prompt: str, user_prompt: str, call_label: str = "llm"):
        start = time.perf_counter()
        logging.info(
            "LLM start: %s model=%s chars=%s/%s",
            call_label,
            self.model,
            len(system_prompt),
            len(user_prompt),
        )
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug("Model input [system] (%s):\n%s", call_label, system_prompt)
            logging.debug("Model input [user] (%s):\n%s", call_label, user_prompt)

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
        self._record_usage(
            call_label=call_label,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logging.info(
            "LLM done: %s %sms chars=%s tokens=%s/%s/%s",
            call_label,
            elapsed_ms,
            len(content),
            prompt_tokens,
            completion_tokens,
            total_tokens,
        )
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug("Model output [raw] (%s):\n%s", call_label, content)
        return json.loads(content)

    def get_usage_summary(self) -> ApiUsageSummary:
        with self._usage_lock:
            summary = ApiUsageSummary()
            summary.merge(self._usage_summary)
            return summary

    def _record_usage(self, call_label: str, prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
        with self._usage_lock:
            self._usage_summary.add(
                call_label=call_label,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )

    @staticmethod
    def _resolve_api_key(api_key: str | None, api_key_env: str) -> str:
        if api_key:
            return api_key
        if not api_key_env:
            return ""
        if api_key_env.startswith(("sk-", "sess-", "Bearer ")) or len(api_key_env) > 24:
            return api_key_env
        return os.getenv(api_key_env, "")
