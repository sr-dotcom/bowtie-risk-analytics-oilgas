"""Tests for src.llm.registry and robust JSON parsing."""
import json
import os
import pytest

from src.llm.registry import get_provider, SUPPORTED_PROVIDERS
from src.llm.base import LLMProvider
from src.llm.stub import StubProvider
from src.ingestion.structured import _parse_llm_json


class TestGetProvider:
    def test_stub_returns_stub_provider(self):
        provider = get_provider("stub")
        assert isinstance(provider, StubProvider)
        assert isinstance(provider, LLMProvider)

    def test_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")

    def test_non_stub_missing_key_raises_runtime_error(self):
        # Ensure the env var is unset
        for name in ("openai", "anthropic", "gemini"):
            env_var = f"{name.upper()}_API_KEY"
            env_backup = os.environ.pop(env_var, None)
            try:
                with pytest.raises(RuntimeError, match="not set"):
                    get_provider(name)
            finally:
                if env_backup is not None:
                    os.environ[env_var] = env_backup

    def test_supported_providers_tuple(self):
        assert "stub" in SUPPORTED_PROVIDERS
        assert "openai" in SUPPORTED_PROVIDERS
        assert "anthropic" in SUPPORTED_PROVIDERS
        assert "gemini" in SUPPORTED_PROVIDERS


class TestParseLlmJson:
    def test_plain_json(self):
        data = _parse_llm_json('{"a": 1}')
        assert data == {"a": 1}

    def test_markdown_fenced_json(self):
        raw = '```json\n{"a": 1}\n```'
        assert _parse_llm_json(raw) == {"a": 1}

    def test_json_with_preamble(self):
        raw = 'Here is the result:\n{"a": 1}'
        assert _parse_llm_json(raw) == {"a": 1}

    def test_nested_braces(self):
        raw = 'Text before {"a": {"b": 2}} text after'
        assert _parse_llm_json(raw) == {"a": {"b": 2}}

    def test_no_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_json("no json here at all")

    def test_empty_string_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_json("")


class TestStubEndToEnd:
    def test_stub_extract_produces_valid_schema_v2_3(self):
        provider = get_provider("stub")
        raw = provider.extract("some prompt")
        data = _parse_llm_json(raw)
        assert data["incident_id"] == "STUB-001"
        assert data["notes"]["schema_version"] == "2.3"
        assert len(data["bowtie"]["controls"]) >= 1
