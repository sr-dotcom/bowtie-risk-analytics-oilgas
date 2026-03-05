"""Sentence-transformers embedding provider."""
from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from src.rag.embeddings.base import EmbeddingProvider

DEFAULT_MODEL = "all-mpnet-base-v2"


class SentenceTransformerProvider(EmbeddingProvider):
    """EmbeddingProvider backed by sentence-transformers."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model = SentenceTransformer(model_name)
        self._dimension = self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> np.ndarray:
        return self._model.encode(text, normalize_embeddings=True).astype(np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, normalize_embeddings=True).astype(np.float32)

    @property
    def dimension(self) -> int:
        return self._dimension
