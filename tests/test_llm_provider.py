import pytest
from src.llm.base import LLMProvider
from src.llm.stub import StubProvider
import json

class TestStubProvider:
    def test_stub_returns_valid_json(self):
        provider = StubProvider()
        result = provider.extract("test prompt")
        data = json.loads(result)
        assert "incident_id" in data
        assert data["incident_id"] == "STUB-001"

    def test_stub_has_bowtie_controls(self):
        provider = StubProvider()
        data = json.loads(provider.extract("test"))
        assert len(data["bowtie"]["controls"]) >= 1

    def test_stub_has_required_fields(self):
        provider = StubProvider()
        data = json.loads(provider.extract("test"))
        assert "source" in data
        assert "context" in data
        assert "event" in data
        assert "bowtie" in data
        assert "pifs" in data
        assert "notes" in data

    def test_stub_implements_abc(self):
        provider = StubProvider()
        assert isinstance(provider, LLMProvider)
