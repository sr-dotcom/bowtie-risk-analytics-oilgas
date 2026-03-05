"""RAG orchestrator: query -> retrieve -> context assembly."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from src.rag.config import TOP_K_RERANK
from src.rag.context_builder import ContextEntry, build_context
from src.rag.embeddings.base import EmbeddingProvider
from src.rag.retriever import HybridRetriever, RetrievalResult


@dataclass
class ExplanationResult:
    """Output of RAGAgent.explain()."""

    context_text: str
    results: list[RetrievalResult]
    metadata: dict[str, Any] = field(default_factory=dict)


PIF_NAMES = [
    "pif_competence", "pif_fatigue", "pif_communication",
    "pif_situational_awareness", "pif_procedures", "pif_workload",
    "pif_time_pressure", "pif_tools_equipment", "pif_safety_culture",
    "pif_management_of_change", "pif_supervision", "pif_training",
]


def _parse_bool(val: str) -> bool:
    return val.strip().lower() in ("true", "1", "yes")


class RAGAgent:
    """Orchestrator that wires retrieval and context assembly."""

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

    @classmethod
    def from_directory(
        cls,
        rag_dir: Path,
        embedding_provider: EmbeddingProvider,
        reranker: Any | None = None,
    ) -> RAGAgent:
        """Load RAG agent from a directory.

        Expects:
            rag_dir/datasets/barrier_documents.csv
            rag_dir/datasets/incident_documents.csv
            rag_dir/embeddings/barrier_embeddings.npy
            rag_dir/embeddings/incident_embeddings.npy
        """
        # Load embeddings
        barrier_emb = np.load(rag_dir / "embeddings" / "barrier_embeddings.npy")
        incident_emb = np.load(rag_dir / "embeddings" / "incident_embeddings.npy")

        # Load barrier metadata
        barrier_meta: list[dict[str, Any]] = []
        with open(rag_dir / "datasets" / "barrier_documents.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                barrier_meta.append(row)

        # Load incident metadata
        incident_meta: list[dict[str, Any]] = []
        with open(rag_dir / "datasets" / "incident_documents.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                incident_meta.append(row)

        # Extract retriever inputs from barrier metadata
        barrier_incident_ids = [r["incident_id"] for r in barrier_meta]
        incident_ids = [r["incident_id"] for r in incident_meta]
        barrier_families = [r["barrier_family"] for r in barrier_meta]
        barrier_failed_humans = [_parse_bool(r["barrier_failed_human"]) for r in barrier_meta]
        barrier_pif_flags = [
            {
                pif.replace("pif_", ""): _parse_bool(r.get(pif, "False"))
                for pif in PIF_NAMES
            }
            for r in barrier_meta
        ]

        retriever = HybridRetriever(
            barrier_embeddings=barrier_emb,
            incident_embeddings=incident_emb,
            barrier_incident_ids=barrier_incident_ids,
            incident_ids=incident_ids,
            barrier_families=barrier_families,
            barrier_failed_humans=barrier_failed_humans,
            barrier_pif_flags=barrier_pif_flags,
            embedding_provider=embedding_provider,
        )

        return cls(retriever, barrier_meta, incident_meta, reranker=reranker)

    def explain(
        self,
        barrier_query: str,
        incident_query: str,
        *,
        barrier_family: str | None = None,
        barrier_failed_human: bool | None = None,
        pif_filters: dict[str, bool] | None = None,
        top_k: int = 10,
        max_context_chars: int = 8000,
    ) -> ExplanationResult:
        """Run retrieval and build explanation context.

        Does NOT call an LLM. Returns structured context for downstream use.
        """
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

        # Build context entries with full metadata
        entries: list[ContextEntry] = []
        for r in results:
            b_meta = self._find_barrier_meta(r)
            i_meta = self._incident_meta.get(r.incident_id, {})

            supporting_text = []
            raw = b_meta.get("supporting_text", "[]")
            try:
                supporting_text = json.loads(raw) if raw else []
            except (json.JSONDecodeError, TypeError):
                supporting_text = []

            barrier_text = b_meta.get("barrier_role_match_text", "")
            lines = barrier_text.split("\n")
            barrier_name = lines[0].replace("Barrier: ", "") if len(lines) > 0 else ""
            barrier_role = lines[1].replace("Role: ", "") if len(lines) > 1 else ""
            lod_basis = lines[2].replace("LOD Basis: ", "") if len(lines) > 2 else ""

            entries.append(ContextEntry(
                incident_id=r.incident_id,
                control_id=b_meta.get("control_id", r.control_id),
                barrier_name=barrier_name,
                barrier_family=r.barrier_family,
                side=b_meta.get("side", ""),
                barrier_status=b_meta.get("barrier_status", ""),
                barrier_role=barrier_role,
                lod_basis=lod_basis,
                barrier_failed_human=r.barrier_failed_human,
                human_contribution_value=b_meta.get("human_contribution_value", ""),
                supporting_text=supporting_text,
                incident_summary=b_meta.get("incident_summary", i_meta.get("summary", "")),
                rrf_score=r.rrf_score,
                barrier_rank=r.barrier_rank,
                incident_rank=r.incident_rank,
            ))

        context_text = build_context(entries, max_context_chars=max_context_chars)

        return ExplanationResult(
            context_text=context_text,
            results=results,
            metadata={
                "barrier_query": barrier_query,
                "incident_query": incident_query,
                "barrier_family": barrier_family,
                "barrier_failed_human": barrier_failed_human,
                "pif_filters": pif_filters,
                "top_k": top_k,
                "result_count": len(results),
            },
        )

    def _find_barrier_meta(self, result: RetrievalResult) -> dict[str, Any]:
        """Find barrier metadata matching a retrieval result."""
        for meta in self._barrier_meta:
            if (
                meta["incident_id"] == result.incident_id
                and meta.get("barrier_family") == result.barrier_family
            ):
                return meta
        return {}
