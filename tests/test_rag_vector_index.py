# tests/test_rag_vector_index.py
import numpy as np
import pytest
from src.rag.vector_index import VectorIndex


class TestVectorIndex:
    def _make_embeddings(self, n: int = 10, dim: int = 8) -> np.ndarray:
        rng = np.random.default_rng(42)
        vecs = rng.standard_normal((n, dim)).astype(np.float32)
        # L2 normalize for inner product similarity
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / norms

    def test_build_and_search(self):
        embeddings = self._make_embeddings(n=20, dim=8)
        index = VectorIndex.build(embeddings)
        scores, indices = index.search(embeddings[0], top_k=5)
        assert len(indices) == 5
        assert indices[0] == 0  # most similar to itself
        assert scores[0] >= scores[1]  # descending similarity

    def test_search_with_mask(self):
        embeddings = self._make_embeddings(n=20, dim=8)
        index = VectorIndex.build(embeddings)
        mask = np.zeros(20, dtype=bool)
        mask[5] = True
        mask[10] = True
        mask[15] = True
        scores, indices = index.search(embeddings[5], top_k=3, mask=mask)
        assert len(indices) <= 3
        assert all(i in {5, 10, 15} for i in indices)

    def test_save_and_load(self, tmp_path):
        embeddings = self._make_embeddings(n=10, dim=8)
        index = VectorIndex.build(embeddings)
        path = tmp_path / "test.faiss"
        index.save(path)
        assert path.exists()

        loaded = VectorIndex.load(path, embeddings)
        scores, indices = loaded.search(embeddings[0], top_k=3)
        assert len(indices) == 3
        assert indices[0] == 0

    def test_dimension(self):
        embeddings = self._make_embeddings(n=5, dim=16)
        index = VectorIndex.build(embeddings)
        assert index.dimension == 16

    def test_top_k_larger_than_candidates(self):
        embeddings = self._make_embeddings(n=3, dim=8)
        index = VectorIndex.build(embeddings)
        scores, indices = index.search(embeddings[0], top_k=10)
        assert len(indices) == 3

    def test_mask_with_no_candidates(self):
        embeddings = self._make_embeddings(n=5, dim=8)
        index = VectorIndex.build(embeddings)
        mask = np.zeros(5, dtype=bool)  # all False
        scores, indices = index.search(embeddings[0], top_k=3, mask=mask)
        assert len(indices) == 0
