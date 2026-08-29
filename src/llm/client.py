from __future__ import annotations

import json
import logging
import os
import threading
import time

from src.core.types import ApiUsageSummary
from src.llm.provider import LLMProvider


class OpenAIProvider(LLMProvider):
    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 2  # seconds
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504, 524}  # 524 is Cloudflare timeout

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

        response = self._call_with_retry(system_prompt, user_prompt, call_label)
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
        payload = json.loads(content)
        # Check for API error responses embedded in JSON
        if isinstance(payload, dict):
            if payload.get("status") == "error" or payload.get("error"):
                error_msg = payload.get("message") or payload.get("error", {}).get("message", str(payload))
                raise ValueError(f"LLM returned error response: {error_msg}")
            if "translations" in payload and isinstance(payload["translations"], list):
                # Validate that translations contain expected fields
                for item in payload["translations"]:
                    if not isinstance(item, dict) or "segment_id" not in item:
                        raise ValueError(f"LLM returned malformed translation item: {item}")
        return payload

    def _call_with_retry(self, system_prompt: str, user_prompt: str, call_label: str):
        """Call the LLM API with automatic retry logic for transient errors."""
        from openai import APIStatusError, APITimeoutError

        last_exception = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return self.client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
            except APITimeoutError as e:
                last_exception = e
                if attempt < self.MAX_RETRIES:
                    delay = self.INITIAL_RETRY_DELAY * (2 ** attempt)
                    logging.warning(
                        "LLM timeout (%s), retrying in %ds (attempt %d/%d)",
                        call_label,
                        delay,
                        attempt + 1,
                        self.MAX_RETRIES,
                    )
                    time.sleep(delay)
                    continue
                raise
            except APIStatusError as e:
                last_exception = e
                status_code = getattr(e.response, "status_code", None)
                
                # Check if the error is retryable
                if status_code in self.RETRYABLE_STATUS_CODES and attempt < self.MAX_RETRIES:
                    # Try to extract retry_after from the error response
                    retry_after = self._extract_retry_after(e)
                    delay = retry_after if retry_after else self.INITIAL_RETRY_DELAY * (2 ** attempt)
                    
                    logging.warning(
                        "LLM error %s (%s retryable), retrying in %ds (attempt %d/%d)",
                        status_code,
                        call_label,
                        delay,
                        attempt + 1,
                        self.MAX_RETRIES,
                    )
                    time.sleep(delay)
                    continue
                raise

    @staticmethod
    def _extract_retry_after(error: Exception) -> int | None:
        """Extract retry_after value from the error response if available."""
        try:
            # Try to get the response body
            response = getattr(error, "response", None)
            if response is None:
                return None
            
            # Try to parse JSON from response
            body = getattr(response, "json", None)
            if callable(body):
                data = body()
            else:
                data = getattr(response, "text", "")
                if isinstance(data, str):
                    import json
                    data = json.loads(data)
            
            # Look for retry_after in the response
            if isinstance(data, dict):
                retry_after = data.get("retry_after")
                if retry_after and isinstance(retry_after, (int, float)):
                    return int(retry_after)
        except Exception:
            # If we can't extract retry_after, we'll use exponential backoff
            pass
        
        return None


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
