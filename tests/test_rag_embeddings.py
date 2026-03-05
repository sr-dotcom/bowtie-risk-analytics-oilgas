import pytest
from src.rag.embeddings.base import EmbeddingProvider


class TestEmbeddingProviderABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            EmbeddingProvider()

    def test_has_required_methods(self):
        assert hasattr(EmbeddingProvider, "embed")
        assert hasattr(EmbeddingProvider, "embed_batch")

    def test_has_dimension_property(self):
        assert hasattr(EmbeddingProvider, "dimension")
