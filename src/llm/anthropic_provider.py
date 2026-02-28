"""Anthropic Messages API provider (HTTP, no SDK dependency)."""
import logging
import os
import time
from typing import Any, Optional

import requests

from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
_API_URL = "https://api.anthropic.com/v1/messages"
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class AnthropicProvider(LLMProvider):
    """LLM provider that calls the Anthropic Messages API over HTTP.

    Args:
        api_key: Anthropic API key.  If *None*, reads ``ANTHROPIC_API_KEY`` from env.
        model: Model identifier (e.g. ``claude-sonnet-4-5-20250929``).
        max_output_tokens: Cap on response tokens.
        temperature: Sampling temperature.
        timeout: Per-request timeout in seconds.
        retries: Number of retries on transient (429 / 5xx) failures.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_output_tokens: int = 4096,
        temperature: float = 0.0,
        timeout: int = 120,
        retries: int = 2,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "AnthropicProvider requires ANTHROPIC_API_KEY env var but it is not set."
            )
        self.model = model or _DEFAULT_MODEL
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.retries = retries

        # Populated after each extract() call
        self.last_meta: dict[str, Any] = {}

    def extract(self, prompt: str) -> str:
        """Send *prompt* to the Anthropic Messages API and return the raw text.

        Retries on 429 and 5xx with exponential back-off (1s, 2s, 4s …).
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        last_err: Optional[Exception] = None
        attempts = 1 + self.retries

        for attempt in range(attempts):
            t0 = time.monotonic()
            try:
                resp = requests.post(
                    _API_URL,
                    headers=headers,
                    json=body,
                    timeout=self.timeout,
                )
                latency_ms = round((time.monotonic() - t0) * 1000)

                if resp.status_code == 200:
                    data = resp.json()
                    raw_text = self._extract_text(data)
                    self.last_meta = {
                        "provider": "anthropic",
                        "model": self.model,
                        "latency_ms": latency_ms,
                        "usage": data.get("usage"),
                        "stop_reason": data.get("stop_reason"),
                    }
                    return raw_text

                if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < attempts - 1:
                    delay = 2 ** attempt
                    logger.warning(
                        "Anthropic API %s (attempt %d/%d), retrying in %ds …",
                        resp.status_code, attempt + 1, attempts, delay,
                    )
                    time.sleep(delay)
                    last_err = RuntimeError(
                        f"Anthropic API returned {resp.status_code}: {resp.text[:300]}"
                    )
                    continue

                raise RuntimeError(
                    f"Anthropic API returned {resp.status_code}: {resp.text[:500]}"
                )

            except requests.RequestException as exc:
                last_err = exc
                if attempt < attempts - 1:
                    delay = 2 ** attempt
                    logger.warning(
                        "Anthropic request error (attempt %d/%d): %s, retrying in %ds …",
                        attempt + 1, attempts, exc, delay,
                    )
                    time.sleep(delay)
                    continue
                raise RuntimeError(
                    f"Anthropic request failed after {attempts} attempts: {exc}"
                ) from exc

        raise RuntimeError(
            f"Anthropic request failed after {attempts} attempts: {last_err}"
        )

    @staticmethod
    def _extract_text(response_data: dict) -> str:
        """Pull text from the Messages API JSON envelope."""
        for block in response_data.get("content", []):
            if block.get("type") == "text":
                return block["text"]
        raise RuntimeError(
            "Could not extract text from Anthropic Messages API payload."
        )
