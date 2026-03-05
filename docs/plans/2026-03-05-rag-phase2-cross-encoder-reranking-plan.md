# Cross-Encoder Reranking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a cross-encoder reranking stage after RRF ranking to improve retrieval accuracy, controlled by a config flag for A/B testing.

**Architecture:** Insert `CrossEncoderReranker` between `HybridRetriever.retrieve()` and `build_context()` inside `RAGAgent.explain()`. Over-retrieve 30 candidates from RRF, re-score with cross-encoder using concatenated (query, passage) pairs, return final top-K. Existing pipeline unchanged when reranker is disabled.

**Tech Stack:** Python 3.10+, sentence-transformers CrossEncoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`), existing RAG infrastructure

---

### Task 0: Config Constants

**Files:**
- Modify: `src/rag/config.py`

**Step 1: Add reranker constants**

Append to `src/rag/config.py`:

```python
# Reranker (Phase-2)
RERANKER_ENABLED = True
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANKER_MAX_LENGTH = 512
RERANKER_BATCH_SIZE = 32
TOP_K_RERANK = 30
FINAL_TOP_K = 10
```

**Step 2: Commit**

```bash
git add src/rag/config.py
git commit -m "feat(rag): add reranker config constants"
```

---

### Task 1: Add `rerank_score` to `RetrievalResult`

**Files:**
- Modify: `src/rag/retriever.py:12-24`

**Step 1: Write the failing test**

Append to `tests/test_rag_retriever.py`:

```python
class TestRetrievalResultRerankScore:
    def test_default_rerank_score_is_none(self):
        r = RetrievalResult(
            incident_id="INC-1",
            control_id="C-1",
            barrier_family="training",
            barrier_failed_human=False,
            rrf_score=0.03,
            barrier_rank=1,
            incident_rank=1,
            barrier_sim_score=0.9,
            incident_sim_score=0.8,
        )
        assert r.rerank_score is None

    def test_rerank_score_can_be_set(self):
        r = RetrievalResult(
            incident_id="INC-1",
            control_id="C-1",
            barrier_family="training",
            barrier_failed_human=False,
            rrf_score=0.03,
            barrier_rank=1,
            incident_rank=1,
            barrier_sim_score=0.9,
            incident_sim_score=0.8,
            rerank_score=0.95,
        )
        assert r.rerank_score == 0.95
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rag_retriever.py::TestRetrievalResultRerankScore -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'rerank_score'`

**Step 3: Add field to `RetrievalResult`**

In `src/rag/retriever.py`, add after `incident_sim_score: float` (line 24):

```python
    rerank_score: float | None = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_rag_retriever.py -v`
Expected: PASS (all existing + 2 new tests)

**Step 5: Commit**

```bash
git add src/rag/retriever.py tests/test_rag_retriever.py
git commit -m "feat(rag): add rerank_score field to RetrievalResult"
```

---

### Task 2: CrossEncoderReranker — Core Implementation

**Files:**
- Create: `src/rag/reranker.py`
- Create: `tests/test_rag_reranker.py`

**Step 1: Write the failing tests**

```python
# tests/test_rag_reranker.py
import logging
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from src.rag.reranker import CrossEncoderReranker
from src.rag.retriever import RetrievalResult


def _make_candidate(incident_id: str, barrier_family: str, rrf: float) -> RetrievalResult:
    return RetrievalResult(
        incident_id=incident_id,
        control_id=f"C-{incident_id}",
        barrier_family=barrier_family,
        barrier_failed_human=False,
        rrf_score=rrf,
        barrier_rank=1,
        incident_rank=1,
        barrier_sim_score=0.9,
        incident_sim_score=0.8,
    )


def _make_barrier_meta(incident_id: str, name: str, role: str, summary: str) -> dict:
    return {
        "incident_id": incident_id,
        "barrier_role_match_text": f"Barrier: {name}\nRole: {role}\nLOD Basis: N/A",
        "barrier_family": "training",
        "incident_summary": summary,
    }


class TestCrossEncoderReranker:
    @patch("src.rag.reranker.CrossEncoder")
    def test_rerank_scores_and_sorts(self, mock_ce_cls):
        mock_model = MagicMock()
        # Return scores: candidate 0 gets 0.3, candidate 1 gets 0.9, candidate 2 gets 0.6
        mock_model.predict.return_value = np.array([0.3, 0.9, 0.6])
        mock_ce_cls.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")

        candidates = [
            _make_candidate("INC-0", "training", 0.03),
            _make_candidate("INC-1", "monitoring", 0.02),
            _make_candidate("INC-2", "training", 0.01),
        ]
        metadata = [
            _make_barrier_meta("INC-0", "Valve", "Prevent", "Valve failure"),
            _make_barrier_meta("INC-1", "Training", "Train", "Training gap"),
            _make_barrier_meta("INC-2", "Alarm", "Alert", "Alarm failure"),
        ]

        results = reranker.rerank(
            barrier_query="safety training",
            incident_query="valve failure",
            candidates=candidates,
            barrier_metadata=metadata,
            top_k=3,
        )

        assert len(results) == 3
        assert results[0].rerank_score == pytest.approx(0.9)
        assert results[1].rerank_score == pytest.approx(0.6)
        assert results[2].rerank_score == pytest.approx(0.3)
        # Verify INC-1 is first (highest rerank score)
        assert results[0].incident_id == "INC-1"

    @patch("src.rag.reranker.CrossEncoder")
    def test_rerank_top_k_truncates(self, mock_ce_cls):
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        mock_ce_cls.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")

        candidates = [_make_candidate(f"INC-{i}", "training", 0.03 - i * 0.001) for i in range(5)]
        metadata = [_make_barrier_meta(f"INC-{i}", f"Control {i}", "Role", f"Summary {i}") for i in range(5)]

        results = reranker.rerank(
            barrier_query="query",
            incident_query="query",
            candidates=candidates,
            barrier_metadata=metadata,
            top_k=3,
        )

        assert len(results) == 3

    @patch("src.rag.reranker.CrossEncoder")
    def test_rerank_rrf_tiebreak(self, mock_ce_cls):
        mock_model = MagicMock()
        # Same rerank scores
        mock_model.predict.return_value = np.array([0.5, 0.5])
        mock_ce_cls.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")

        candidates = [
            _make_candidate("INC-0", "training", 0.01),  # lower RRF
            _make_candidate("INC-1", "training", 0.03),  # higher RRF
        ]
        metadata = [
            _make_barrier_meta("INC-0", "A", "Role", "Summary"),
            _make_barrier_meta("INC-1", "B", "Role", "Summary"),
        ]

        results = reranker.rerank(
            barrier_query="query",
            incident_query="query",
            candidates=candidates,
            barrier_metadata=metadata,
            top_k=2,
        )

        # INC-1 should be first (higher RRF as tiebreak)
        assert results[0].incident_id == "INC-1"

    @patch("src.rag.reranker.CrossEncoder")
    def test_rerank_empty_candidates(self, mock_ce_cls):
        mock_model = MagicMock()
        mock_ce_cls.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")

        results = reranker.rerank(
            barrier_query="query",
            incident_query="query",
            candidates=[],
            barrier_metadata=[],
            top_k=5,
        )

        assert results == []
        mock_model.predict.assert_not_called()

    @patch("src.rag.reranker.CrossEncoder")
    def test_rerank_passage_composition(self, mock_ce_cls):
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.9])
        mock_ce_cls.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")

        candidates = [_make_candidate("INC-0", "training", 0.03)]
        metadata = [_make_barrier_meta("INC-0", "PSV", "Prevent overpressure", "Valve ruptured")]

        reranker.rerank(
            barrier_query="safety valve",
            incident_query="pressure release",
            candidates=candidates,
            barrier_metadata=metadata,
            top_k=1,
        )

        # Verify the pairs passed to predict
        call_args = mock_model.predict.call_args[0][0]
        query, passage = call_args[0]
        assert query == "safety valve pressure release"
        assert "Barrier: PSV" in passage
        assert "Prevent overpressure" in passage
        assert "Incident: Valve ruptured" in passage

    @patch("src.rag.reranker.CrossEncoder")
    def test_rerank_logs_latency(self, mock_ce_cls, caplog):
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.5])
        mock_ce_cls.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")

        candidates = [_make_candidate("INC-0", "training", 0.03)]
        metadata = [_make_barrier_meta("INC-0", "A", "Role", "Summary")]

        with caplog.at_level(logging.DEBUG, logger="src.rag.reranker"):
            reranker.rerank(
                barrier_query="query",
                incident_query="query",
                candidates=candidates,
                barrier_metadata=metadata,
                top_k=1,
            )

        assert any("reranker_latency_ms" in r.message for r in caplog.records)
        assert any("num_candidates" in r.message for r in caplog.records)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rag_reranker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.rag.reranker'`

**Step 3: Write implementation**

```python
# src/rag/reranker.py
"""Cross-encoder reranker for post-RRF candidate re-scoring."""
from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
from sentence_transformers import CrossEncoder

from src.rag.config import FINAL_TOP_K, RERANKER_BATCH_SIZE, RERANKER_MAX_LENGTH, RERANKER_MODEL
from src.rag.retriever import RetrievalResult

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Re-score retrieval candidates using a cross-encoder model."""

    def __init__(
        self,
        model_name: str = RERANKER_MODEL,
        max_length: int = RERANKER_MAX_LENGTH,
        batch_size: int = RERANKER_BATCH_SIZE,
    ) -> None:
        self._model = CrossEncoder(model_name, max_length=max_length)
        self._batch_size = batch_size

    def _build_passage(
        self, candidate: RetrievalResult, barrier_metadata: list[dict[str, Any]]
    ) -> str:
        """Build labeled passage from barrier metadata."""
        meta = self._find_meta(candidate, barrier_metadata)
        barrier_text = meta.get("barrier_role_match_text", "")
        lines = barrier_text.split("\n")
        name = lines[0].replace("Barrier: ", "") if len(lines) > 0 else ""
        role = lines[1].replace("Role: ", "") if len(lines) > 1 else ""
        summary = meta.get("incident_summary", "")
        return f"Barrier: {name} — {role}\nIncident: {summary}"

    def _find_meta(
        self, candidate: RetrievalResult, barrier_metadata: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Find barrier metadata matching a candidate."""
        for meta in barrier_metadata:
            if (
                meta["incident_id"] == candidate.incident_id
                and meta.get("barrier_family") == candidate.barrier_family
            ):
                return meta
        return {}

    def rerank(
        self,
        barrier_query: str,
        incident_query: str,
        candidates: list[RetrievalResult],
        barrier_metadata: list[dict[str, Any]],
        top_k: int = FINAL_TOP_K,
    ) -> list[RetrievalResult]:
        """Re-score candidates with cross-encoder and return top-K.

        Args:
            barrier_query: Barrier search query text.
            incident_query: Incident search query text.
            candidates: RRF-ranked retrieval results to re-score.
            barrier_metadata: Full barrier metadata list for passage building.
            top_k: Number of results to return after reranking.

        Returns:
            Reranked list sorted by rerank_score desc, rrf_score desc tiebreak.
        """
        if not candidates:
            return []

        query = f"{barrier_query} {incident_query}"
        pairs: list[tuple[str, str]] = []
        for c in candidates:
            passage = self._build_passage(c, barrier_metadata)
            pairs.append((query, passage))

        t0 = time.perf_counter()
        scores = self._model.predict(pairs, batch_size=self._batch_size)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        logger.debug(
            "reranker_latency_ms=%.1f num_candidates=%d",
            elapsed_ms,
            len(candidates),
        )

        for c, score in zip(candidates, scores):
            c.rerank_score = float(score)

        candidates.sort(key=lambda r: (-r.rerank_score, -r.rrf_score))
        return candidates[:top_k]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_rag_reranker.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/rag/reranker.py tests/test_rag_reranker.py
git commit -m "feat(rag): add CrossEncoderReranker with latency logging"
```

---

### Task 3: Wire Reranker into RAGAgent

**Files:**
- Modify: `src/rag/rag_agent.py`
- Modify: `tests/test_rag_agent.py`

**Step 1: Write the failing tests**

Append to `tests/test_rag_agent.py`:

```python
from src.rag.reranker import CrossEncoderReranker


class TestRAGAgentWithReranker:
    def _build_agent_with_reranker(self, tmp_path):
        """Build a RAGAgent with a mock reranker."""
        import csv

        barrier_csv = tmp_path / "datasets" / "barrier_documents.csv"
        barrier_csv.parent.mkdir(parents=True)

        from src.rag.corpus_builder import BARRIER_DOC_COLUMNS
        barriers = []
        for i in range(6):
            inc_id = f"INC-{i // 2}"
            barriers.append({
                "incident_id": inc_id,
                "control_id": f"C-{i:03d}",
                "barrier_role_match_text": f"Barrier: Control {i}\nRole: Test role\nLOD Basis: Test basis",
                "barrier_family": "training" if i % 2 == 0 else "monitoring",
                "barrier_type": "administrative",
                "side": "prevention",
                "line_of_defense": "1st",
                "barrier_status": "failed" if i % 2 == 0 else "active",
                "barrier_failed": str(i % 2 == 0),
                "barrier_failed_human": str(i % 3 == 0),
                "human_contribution_value": "high" if i % 2 == 0 else "",
                "pif_competence": "True",
                "pif_fatigue": "False",
                "pif_communication": str(i % 2 == 0),
                "pif_situational_awareness": "False",
                "pif_procedures": "True",
                "pif_workload": "False",
                "pif_time_pressure": "False",
                "pif_tools_equipment": "False",
                "pif_safety_culture": "False",
                "pif_management_of_change": "False",
                "pif_supervision": "False",
                "pif_training": "True",
                "supporting_text": json.dumps(["Evidence text"]),
                "confidence": "high",
                "incident_summary": f"Incident {i // 2} summary.",
            })
        with open(barrier_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=BARRIER_DOC_COLUMNS)
            writer.writeheader()
            writer.writerows(barriers)

        incident_csv = tmp_path / "datasets" / "incident_documents.csv"
        from src.rag.corpus_builder import INCIDENT_DOC_COLUMNS
        incidents = []
        for i in range(3):
            incidents.append({
                "incident_id": f"INC-{i}",
                "incident_embed_text": f"Top Event: Event {i}\nSummary: Incident {i}",
                "top_event": f"Event {i}",
                "incident_type": "Equipment Failure",
                "operating_phase": "production",
                "materials": json.dumps(["oil"]),
                "region": "Gulf of Mexico",
                "operator": f"Operator {i}",
                "summary": f"Incident {i} summary.",
                "recommendations": json.dumps(["Fix it"]),
            })
        with open(incident_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=INCIDENT_DOC_COLUMNS)
            writer.writeheader()
            writer.writerows(incidents)

        rng = np.random.default_rng(42)
        barrier_emb = rng.standard_normal((6, 8)).astype(np.float32)
        barrier_emb /= np.linalg.norm(barrier_emb, axis=1, keepdims=True)
        incident_emb = rng.standard_normal((3, 8)).astype(np.float32)
        incident_emb /= np.linalg.norm(incident_emb, axis=1, keepdims=True)

        (tmp_path / "embeddings").mkdir(parents=True, exist_ok=True)
        np.save(tmp_path / "embeddings" / "barrier_embeddings.npy", barrier_emb)
        np.save(tmp_path / "embeddings" / "incident_embeddings.npy", incident_emb)

        mock_provider = MagicMock()
        mock_provider.embed.return_value = barrier_emb[0]
        mock_provider.dimension = 8

        mock_reranker = MagicMock(spec=CrossEncoderReranker)
        # rerank returns candidates with rerank_score attached
        def mock_rerank(barrier_query, incident_query, candidates, barrier_metadata, top_k=10):
            for i, c in enumerate(candidates):
                c.rerank_score = 1.0 - i * 0.1
            candidates.sort(key=lambda r: (-r.rerank_score, -r.rrf_score))
            return candidates[:top_k]
        mock_reranker.rerank.side_effect = mock_rerank

        agent = RAGAgent.from_directory(
            tmp_path, embedding_provider=mock_provider, reranker=mock_reranker
        )
        return agent, mock_reranker

    def test_explain_with_reranker_calls_rerank(self, tmp_path):
        agent, mock_reranker = self._build_agent_with_reranker(tmp_path)
        result = agent.explain(
            barrier_query="training",
            incident_query="failure",
        )
        mock_reranker.rerank.assert_called_once()
        assert isinstance(result, ExplanationResult)

    def test_explain_without_reranker_unchanged(self, tmp_path):
        """Verify Phase-1 behavior when no reranker provided."""
        import csv

        barrier_csv = tmp_path / "datasets" / "barrier_documents.csv"
        barrier_csv.parent.mkdir(parents=True)
        from src.rag.corpus_builder import BARRIER_DOC_COLUMNS, INCIDENT_DOC_COLUMNS
        barriers = []
        for i in range(6):
            inc_id = f"INC-{i // 2}"
            barriers.append({
                "incident_id": inc_id,
                "control_id": f"C-{i:03d}",
                "barrier_role_match_text": f"Barrier: Control {i}\nRole: Test role\nLOD Basis: Test basis",
                "barrier_family": "training" if i % 2 == 0 else "monitoring",
                "barrier_type": "administrative", "side": "prevention",
                "line_of_defense": "1st",
                "barrier_status": "failed" if i % 2 == 0 else "active",
                "barrier_failed": str(i % 2 == 0),
                "barrier_failed_human": str(i % 3 == 0),
                "human_contribution_value": "high" if i % 2 == 0 else "",
                "pif_competence": "True", "pif_fatigue": "False",
                "pif_communication": str(i % 2 == 0),
                "pif_situational_awareness": "False", "pif_procedures": "True",
                "pif_workload": "False", "pif_time_pressure": "False",
                "pif_tools_equipment": "False", "pif_safety_culture": "False",
                "pif_management_of_change": "False", "pif_supervision": "False",
                "pif_training": "True",
                "supporting_text": json.dumps(["Evidence text"]),
                "confidence": "high",
                "incident_summary": f"Incident {i // 2} summary.",
            })
        with open(barrier_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=BARRIER_DOC_COLUMNS)
            writer.writeheader()
            writer.writerows(barriers)
        incident_csv = tmp_path / "datasets" / "incident_documents.csv"
        incidents = []
        for i in range(3):
            incidents.append({
                "incident_id": f"INC-{i}",
                "incident_embed_text": f"Top Event: Event {i}\nSummary: Incident {i}",
                "top_event": f"Event {i}", "incident_type": "Equipment Failure",
                "operating_phase": "production", "materials": json.dumps(["oil"]),
                "region": "Gulf of Mexico", "operator": f"Operator {i}",
                "summary": f"Incident {i} summary.",
                "recommendations": json.dumps(["Fix it"]),
            })
        with open(incident_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=INCIDENT_DOC_COLUMNS)
            writer.writeheader()
            writer.writerows(incidents)

        rng = np.random.default_rng(42)
        barrier_emb = rng.standard_normal((6, 8)).astype(np.float32)
        barrier_emb /= np.linalg.norm(barrier_emb, axis=1, keepdims=True)
        incident_emb = rng.standard_normal((3, 8)).astype(np.float32)
        incident_emb /= np.linalg.norm(incident_emb, axis=1, keepdims=True)

        (tmp_path / "embeddings").mkdir(parents=True, exist_ok=True)
        np.save(tmp_path / "embeddings" / "barrier_embeddings.npy", barrier_emb)
        np.save(tmp_path / "embeddings" / "incident_embeddings.npy", incident_emb)

        mock_provider = MagicMock()
        mock_provider.embed.return_value = barrier_emb[0]
        mock_provider.dimension = 8

        # No reranker
        agent = RAGAgent.from_directory(tmp_path, embedding_provider=mock_provider)
        result = agent.explain(barrier_query="training", incident_query="failure")
        assert isinstance(result, ExplanationResult)
        # All results should have rerank_score == None
        for r in result.results:
            assert r.rerank_score is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rag_agent.py::TestRAGAgentWithReranker -v`
Expected: FAIL with `TypeError: from_directory() got an unexpected keyword argument 'reranker'`

**Step 3: Modify `RAGAgent`**

In `src/rag/rag_agent.py`:

1. Add import at top:
```python
from src.rag.config import TOP_K_RERANK
```

2. Modify `__init__()` to accept reranker:
```python
    def __init__(
        self,
        retriever: HybridRetriever,
        barrier_metadata: list[dict[str, Any]],
        incident_metadata: list[dict[str, Any]],
        reranker: Any | None = None,
    ) -> None:
        self._retriever = retriever
        self._barrier_meta = barrier_metadata
        self._incident_meta = {
            row["incident_id"]: row for row in incident_metadata
        }
        self._reranker = reranker
```

3. Modify `from_directory()` to accept and pass reranker:
```python
    @classmethod
    def from_directory(
        cls,
        rag_dir: Path,
        embedding_provider: EmbeddingProvider,
        reranker: Any | None = None,
    ) -> RAGAgent:
```
And change the return to:
```python
        return cls(retriever, barrier_meta, incident_meta, reranker=reranker)
```

4. Modify `explain()` to use reranker when available. Replace the section between `retriever.retrieve()` and the context entry building with:
```python
        # Determine retrieval depth
        retrieve_top_k = TOP_K_RERANK if self._reranker is not None else top_k

        results = self._retriever.retrieve(
            barrier_query=barrier_query,
            incident_query=incident_query,
            barrier_family=barrier_family,
            barrier_failed_human=barrier_failed_human,
            pif_filters=pif_filters,
            top_k=retrieve_top_k,
        )

        # Phase-2: Cross-encoder reranking
        if self._reranker is not None and results:
            results = self._reranker.rerank(
                barrier_query=barrier_query,
                incident_query=incident_query,
                candidates=results,
                barrier_metadata=self._barrier_meta,
                top_k=top_k,
            )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_rag_agent.py -v`
Expected: PASS (all existing + 2 new tests)

**Step 5: Commit**

```bash
git add src/rag/rag_agent.py tests/test_rag_agent.py
git commit -m "feat(rag): wire CrossEncoderReranker into RAGAgent"
```

---

### Task 4: Integration Test with Reranker

**Files:**
- Modify: `tests/test_rag_integration.py`

**Step 1: Append integration test**

Append to `tests/test_rag_integration.py`:

```python
class TestRAGIntegrationWithReranker:
    def test_end_to_end_with_reranker(self, tmp_path):
        # 1. Create JSON incidents (reuse helper)
        json_dir = tmp_path / "incidents"
        json_dir.mkdir()
        for i, (event, barrier) in enumerate([
            ("Pressure vessel rupture", "Pressure Safety Valve"),
            ("Gas leak from flange", "Flange Inspection Program"),
            ("Crane dropped load", "Lift Plan Procedure"),
        ]):
            path = json_dir / f"inc_{i}.json"
            path.write_text(json.dumps(_make_incident(f"INC-{i}", event, barrier)))

        # 2. Build corpus
        rag_dir = tmp_path / "rag"
        datasets_dir = rag_dir / "datasets"
        datasets_dir.mkdir(parents=True)
        b_count = build_barrier_documents(json_dir, datasets_dir / "barrier_documents.csv")
        i_count = build_incident_documents(json_dir, datasets_dir / "incident_documents.csv")

        # 3. Generate mock embeddings
        rng = np.random.default_rng(42)
        dim = 8
        barrier_emb = rng.standard_normal((b_count, dim)).astype(np.float32)
        barrier_emb /= np.linalg.norm(barrier_emb, axis=1, keepdims=True)
        incident_emb = rng.standard_normal((i_count, dim)).astype(np.float32)
        incident_emb /= np.linalg.norm(incident_emb, axis=1, keepdims=True)

        emb_dir = rag_dir / "embeddings"
        emb_dir.mkdir()
        np.save(emb_dir / "barrier_embeddings.npy", barrier_emb)
        np.save(emb_dir / "incident_embeddings.npy", incident_emb)

        # 4. Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.embed.return_value = barrier_emb[0]
        mock_provider.dimension = dim

        # 5. Mock reranker
        from src.rag.reranker import CrossEncoderReranker
        mock_reranker = MagicMock(spec=CrossEncoderReranker)
        def mock_rerank(barrier_query, incident_query, candidates, barrier_metadata, top_k=10):
            for i, c in enumerate(candidates):
                c.rerank_score = 1.0 - i * 0.1
            candidates.sort(key=lambda r: (-r.rerank_score, -r.rrf_score))
            return candidates[:top_k]
        mock_reranker.rerank.side_effect = mock_rerank

        # 6. Create agent with reranker
        agent = RAGAgent.from_directory(
            rag_dir, embedding_provider=mock_provider, reranker=mock_reranker
        )

        # 7. Run explain
        result = agent.explain(
            barrier_query="pressure safety valve",
            incident_query="vessel rupture",
            top_k=3,
        )

        assert isinstance(result, ExplanationResult)
        assert len(result.context_text) > 0
        mock_reranker.rerank.assert_called_once()
        # Results should have rerank_score set
        for r in result.results:
            assert r.rerank_score is not None
```

**Step 2: Run integration tests**

Run: `pytest tests/test_rag_integration.py -v`
Expected: PASS (existing + new test)

**Step 3: Commit**

```bash
git add tests/test_rag_integration.py
git commit -m "test(rag): add reranker integration test"
```

---

### Task 5: Full Test Suite Verification

**Step 1: Run full test suite**

Run: `pytest -v --tb=short`
Expected: All 351+ existing tests PASS, all new reranker tests PASS

**Step 2: If any failures, fix without modifying existing pipeline behavior**

The reranker is additive — existing tests should not be affected. If `RetrievalResult` field addition causes issues, verify `rerank_score=None` default is backward compatible.

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat(rag): complete Phase-2 cross-encoder reranking"
```
