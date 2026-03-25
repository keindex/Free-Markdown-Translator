from __future__ import annotations

import json
import logging
import os
import time

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
        if not resolved_api_key:
            raise ValueError(
                "No API key available. Set provider.api_key in config.yaml or "
                "set provider.api_key_env to an environment variable name."
            )
        self.client = OpenAI(api_key=resolved_api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat_json(self, system_prompt: str, user_prompt: str, call_label: str = "llm"):
        start = time.perf_counter()
        logging.info(
            "Model call start: label=%s provider=openai model=%s system_chars=%s user_chars=%s",
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
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logging.info(
            "Model call done: label=%s provider=openai model=%s elapsed_ms=%s response_chars=%s",
            call_label,
            self.model,
            elapsed_ms,
            len(content),
        )
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug("Model output [raw] (%s):\n%s", call_label, content)
        return json.loads(content)

    @staticmethod
    def _resolve_api_key(api_key: str | None, api_key_env: str) -> str:
        if api_key:
            return api_key
        if not api_key_env:
            return ""
        if api_key_env.startswith(("sk-", "sess-", "Bearer ")) or len(api_key_env) > 24:
            return api_key_env
        return os.getenv(api_key_env, "")
