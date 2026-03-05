"""Embedding provider abstract base class."""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class EmbeddingProvider(ABC):
    """ABC for embedding providers. Implementations must define embed,
    embed_batch, and dimension."""

    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        """Embed a single text string. Returns a 1-D float32 array."""
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of texts. Returns a 2-D float32 array of shape
        (len(texts), dimension)."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors."""
        ...
