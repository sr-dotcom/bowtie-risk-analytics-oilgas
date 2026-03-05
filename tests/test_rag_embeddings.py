import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from src.rag.embeddings.base import EmbeddingProvider
from src.rag.embeddings.sentence_transformers_provider import SentenceTransformerProvider


class TestEmbeddingProviderABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            EmbeddingProvider()

    def test_has_required_methods(self):
        assert hasattr(EmbeddingProvider, "embed")
        assert hasattr(EmbeddingProvider, "embed_batch")

    def test_has_dimension_property(self):
        assert hasattr(EmbeddingProvider, "dimension")


class TestSentenceTransformerProvider:
    @patch("src.rag.embeddings.sentence_transformers_provider.SentenceTransformer")
    def test_embed_single(self, mock_st_cls):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        mock_model.get_sentence_embedding_dimension.return_value = 3
        mock_st_cls.return_value = mock_model

        provider = SentenceTransformerProvider(model_name="test-model")
        result = provider.embed("hello")

        assert isinstance(result, np.ndarray)
        assert result.shape == (3,)
        mock_model.encode.assert_called_once()

    @patch("src.rag.embeddings.sentence_transformers_provider.SentenceTransformer")
    def test_embed_batch(self, mock_st_cls):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array(
            [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], dtype=np.float32
        )
        mock_model.get_sentence_embedding_dimension.return_value = 3
        mock_st_cls.return_value = mock_model

        provider = SentenceTransformerProvider(model_name="test-model")
        result = provider.embed_batch(["hello", "world"])

        assert isinstance(result, np.ndarray)
        assert result.shape == (2, 3)

    @patch("src.rag.embeddings.sentence_transformers_provider.SentenceTransformer")
    def test_dimension(self, mock_st_cls):
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_st_cls.return_value = mock_model

        provider = SentenceTransformerProvider(model_name="test-model")
        assert provider.dimension == 768

    @patch("src.rag.embeddings.sentence_transformers_provider.SentenceTransformer")
    def test_default_model_name(self, mock_st_cls):
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_st_cls.return_value = mock_model

        provider = SentenceTransformerProvider()
        mock_st_cls.assert_called_once_with("all-mpnet-base-v2")
