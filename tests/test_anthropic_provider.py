"""Tests for AnthropicProvider (mocked HTTP, no real API key needed)."""
import json
import os
from unittest.mock import patch, MagicMock

import pytest
import requests

from src.llm.base import LLMProvider
from src.llm.anthropic_provider import AnthropicProvider
from src.llm.registry import get_provider


# -- helpers ------------------------------------------------------------------

def _messages_payload(text: str) -> dict:
    """Build a minimal Anthropic Messages API success envelope."""
    return {
        "id": "msg_abc123",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": "claude-sonnet-4-5-20250929",
        "usage": {"input_tokens": 50, "output_tokens": 120},
    }


def _mock_response(status_code: int = 200, json_data: dict | None = None, text: str = "") -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text or json.dumps(json_data or {})
    resp.json.return_value = json_data or {}
    return resp


# -- construction & fail-fast ------------------------------------------------

class TestAnthropicProviderInit:
    def test_missing_key_raises_runtime_error(self):
        env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                AnthropicProvider(api_key="")
        finally:
            if env_backup is not None:
                os.environ["ANTHROPIC_API_KEY"] = env_backup

    def test_explicit_key_accepted(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        assert isinstance(provider, LLMProvider)
        assert provider.model == "claude-sonnet-4-5-20250929"


# -- extract() ---------------------------------------------------------------

class TestAnthropicProviderExtract:
    @patch("src.llm.anthropic_provider.requests.post")
    def test_successful_extraction(self, mock_post: MagicMock) -> None:
        sample_json = '{"incident_id": "INC-001"}'
        mock_post.return_value = _mock_response(200, _messages_payload(sample_json))

        provider = AnthropicProvider(api_key="sk-ant-test")
        result = provider.extract("some prompt")

        assert result == sample_json
        assert provider.last_meta["provider"] == "anthropic"
        assert provider.last_meta["usage"]["input_tokens"] == 50

        # Verify request shape
        call_kwargs = mock_post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["messages"] == [{"role": "user", "content": "some prompt"}]
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["x-api-key"] == "sk-ant-test"
        assert headers["anthropic-version"] == "2023-06-01"

    @patch("src.llm.anthropic_provider.requests.post")
    def test_non_retryable_error_raises_immediately(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response(401, text="Unauthorized")
        provider = AnthropicProvider(api_key="sk-ant-test", retries=2)
        with pytest.raises(RuntimeError, match="401"):
            provider.extract("prompt")
        assert mock_post.call_count == 1

    @patch("src.llm.anthropic_provider.time.sleep")
    @patch("src.llm.anthropic_provider.requests.post")
    def test_retry_on_429_then_success(self, mock_post: MagicMock, mock_sleep: MagicMock) -> None:
        sample_json = '{"ok": true}'
        mock_post.side_effect = [
            _mock_response(429, text="Rate limited"),
            _mock_response(200, _messages_payload(sample_json)),
        ]
        provider = AnthropicProvider(api_key="sk-ant-test", retries=2)
        result = provider.extract("prompt")
        assert result == sample_json
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @patch("src.llm.anthropic_provider.time.sleep")
    @patch("src.llm.anthropic_provider.requests.post")
    def test_all_retries_exhausted_raises(self, mock_post: MagicMock, mock_sleep: MagicMock) -> None:
        mock_post.return_value = _mock_response(503, text="Overloaded")
        provider = AnthropicProvider(api_key="sk-ant-test", retries=1)
        with pytest.raises(RuntimeError, match="503"):
            provider.extract("prompt")
        assert mock_post.call_count == 2


# -- registry integration ----------------------------------------------------

class TestRegistryAnthropic:
    def test_registry_missing_key_raises_runtime_error(self):
        env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(RuntimeError, match="not set"):
                get_provider("anthropic")
        finally:
            if env_backup is not None:
                os.environ["ANTHROPIC_API_KEY"] = env_backup

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-registry"})
    def test_registry_resolves_anthropic_provider(self):
        provider = get_provider("anthropic", model="claude-haiku-4-5-20251001")
        assert isinstance(provider, AnthropicProvider)
        assert isinstance(provider, LLMProvider)
        assert provider.model == "claude-haiku-4-5-20251001"
