"""FAISS IndexFlatIP wrapper with metadata mask support."""
from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np


class VectorIndex:
    """Thin wrapper around FAISS IndexFlatIP for exact inner-product search.

    Supports pre-filter metadata masking: pass a boolean mask to search()
    to restrict candidates before similarity search.
    """

    def __init__(self, index: faiss.IndexFlatIP, embeddings: np.ndarray) -> None:
        self._index = index
        self._embeddings = embeddings

    @classmethod
    def build(cls, embeddings: np.ndarray) -> VectorIndex:
        """Build a FAISS flat inner-product index from embeddings.

        Args:
            embeddings: (N, D) float32 array, should be L2-normalized.

        Raises:
            ValueError: If any vector norms deviate from 1.0 by more than 1e-4.
        """
        norms = np.linalg.norm(embeddings, axis=1)
        if np.any(np.abs(norms - 1.0) > 1e-4):
            raise ValueError(
                "All embedding vectors must be L2-normalized (unit length). "
                f"Found norms ranging from {norms.min():.6f} to {norms.max():.6f}."
            )
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        return cls(index, embeddings)

    @property
    def dimension(self) -> int:
        return self._index.d

    def search(
        self,
        query: np.ndarray,
        top_k: int = 10,
        mask: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Search for nearest neighbors.

        Args:
            query: 1-D float32 query vector.
            top_k: Number of results to return.
            mask: Optional boolean mask of shape (N,). Only True positions
                  are searched.

        Returns:
            (scores, indices) — both 1-D arrays sorted by descending score.
        """
        if mask is not None:
            candidate_idx = np.where(mask)[0]
            if len(candidate_idx) == 0:
                return np.array([], dtype=np.float32), np.array([], dtype=np.int64)
            subset = self._embeddings[candidate_idx]
            k = min(top_k, len(candidate_idx))
            q = query.reshape(1, -1)
            scores_sub, indices_sub = faiss.knn(
                q, subset, k, metric=faiss.METRIC_INNER_PRODUCT
            )
            scores = scores_sub[0]
            indices = candidate_idx[indices_sub[0]]
            return scores, indices

        k = min(top_k, self._index.ntotal)
        q = query.reshape(1, -1)
        scores, indices = self._index.search(q, k)
        return scores[0], indices[0]

    def save(self, path: Path) -> None:
        """Save FAISS index to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(path))

    @classmethod
    def load(cls, path: Path, embeddings: np.ndarray) -> VectorIndex:
        """Load FAISS index from disk.

        Args:
            path: Path to saved .faiss file.
            embeddings: The original embeddings array (needed for masked search).
        """
        index = faiss.read_index(str(path))
        return cls(index, embeddings)
