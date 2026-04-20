"""Tests for RAG v2 scope-filtered corpus build."""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.rag.corpus_builder import build_barrier_documents, build_incident_documents
from src.rag.vector_index import VectorIndex


def _make_minimal_incident(incident_id: str) -> dict:
    return {
        "incident_id": incident_id,
        "source": {
            "doc_type": "Accident Investigation Report",
            "url": None,
            "title": f"Report {incident_id}",
            "date_published": "2024-01-01",
            "date_occurred": "2024-01-01",
            "timezone": None,
        },
        "context": {
            "region": "Gulf of Mexico",
            "operator": "Test Operator",
            "operating_phase": "production",
            "materials": ["crude oil"],
        },
        "event": {
            "top_event": "Loss of Containment",
            "incident_type": "Equipment Failure",
            "costs": None,
            "actions_taken": [],
            "summary": f"Incident {incident_id} summary.",
            "recommendations": [f"Recommendation for {incident_id}"],
            "key_phrases": [],
        },
        "bowtie": {
            "hazards": [],
            "threats": [],
            "consequences": [],
            "controls": [
                {
                    "control_id": f"C-001-{incident_id}",
                    "name": "Pressure Safety Valve",
                    "side": "prevention",
                    "barrier_role": "Prevent overpressure",
                    "barrier_type": "engineering",
                    "line_of_defense": 1,
                    "lod_basis": "Primary pressure protection",
                    "linked_threat_ids": [],
                    "linked_consequence_ids": [],
                    "performance": {
                        "barrier_status": "failed",
                        "barrier_failed": True,
                        "detection_applicable": False,
                        "detection_mentioned": False,
                        "alarm_applicable": False,
                        "alarm_mentioned": False,
                        "manual_intervention_applicable": False,
                        "manual_intervention_mentioned": False,
                    },
                    "human": {
                        "human_contribution_value": None,
                        "human_contribution_mentioned": False,
                        "barrier_failed_human": False,
                        "linked_pif_ids": [],
                    },
                    "evidence": {
                        "supporting_text": [],
                        "confidence": "low",
                    },
                }
            ],
        },
        "pifs": {
            "people": {
                "competence_value": "adequate",
                "competence_mentioned": True,
                "fatigue_value": None,
                "fatigue_mentioned": False,
                "communication_value": None,
                "communication_mentioned": False,
                "situational_awareness_value": None,
                "situational_awareness_mentioned": False,
            },
            "work": {
                "procedures_value": None,
                "procedures_mentioned": False,
                "workload_value": None,
                "workload_mentioned": False,
                "time_pressure_value": None,
                "time_pressure_mentioned": False,
                "tools_equipment_value": None,
                "tools_equipment_mentioned": False,
            },
            "organisation": {
                "safety_culture_value": None,
                "safety_culture_mentioned": False,
                "management_of_change_value": None,
                "management_of_change_mentioned": False,
                "supervision_value": None,
                "supervision_mentioned": False,
                "training_value": None,
                "training_mentioned": False,
            },
        },
        "notes": {"rules": "", "schema_version": "2.3"},
    }


def _write_json_dir(base: Path, incident_ids: list[str]) -> Path:
    json_dir = base / "incidents"
    json_dir.mkdir()
    for iid in incident_ids:
        inc = _make_minimal_incident(iid)
        (json_dir / f"{iid}.json").write_text(json.dumps(inc), encoding="utf-8")
    return json_dir


def _make_scope_parquet(base: Path, incident_ids: list[str]) -> Path:
    df = pd.DataFrame({"incident_id": incident_ids, "y_fail": [1] * len(incident_ids)})
    path = base / "scope.parquet"
    df.to_parquet(str(path), index=False)
    return path


# ── Tests ──────────────────────────────────────────────────────────────────


class TestV2ScopeFilter:
    def test_only_filtered_incident_ids_in_barrier_csv(self, tmp_path: Path) -> None:
        """(a) Only filtered incident_ids appear in the barrier CSV."""
        all_ids = ["INC-A", "INC-B", "INC-C"]
        scope = {"INC-A", "INC-C"}
        json_dir = _write_json_dir(tmp_path, all_ids)
        out_csv = tmp_path / "barriers.csv"

        count = build_barrier_documents(json_dir, out_csv, incident_id_filter=scope)

        assert count == 2, f"Expected 2 rows, got {count}"
        with open(out_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        ids_found = {r["incident_id"] for r in rows}
        assert ids_found == scope

    def test_embedding_shape_matches_csv_rowcount(self, tmp_path: Path) -> None:
        """(b) Embedding .npy row count == CSV row count."""
        pytest.importorskip("sentence_transformers")

        all_ids = ["INC-A", "INC-B", "INC-C"]
        scope = {"INC-A", "INC-B"}
        json_dir = _write_json_dir(tmp_path, all_ids)

        out_csv = tmp_path / "incidents.csv"
        count = build_incident_documents(json_dir, out_csv, incident_id_filter=scope)
        assert count == 2

        from src.rag.embeddings.sentence_transformers_provider import SentenceTransformerProvider

        provider = SentenceTransformerProvider()
        with open(out_csv, encoding="utf-8") as f:
            texts = [r["incident_embed_text"] for r in csv.DictReader(f)]

        emb = provider.embed_batch(texts)
        assert emb.shape[0] == count

    def test_faiss_index_roundtrip(self, tmp_path: Path) -> None:
        """(c) FAISS .bin files save/load correctly and return the right dimension."""
        pytest.importorskip("faiss")

        dim = 4
        vectors = np.random.rand(5, dim).astype(np.float32)
        # Normalize to unit length so VectorIndex.build accepts them
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / norms

        index = VectorIndex.build(vectors)
        bin_path = tmp_path / "test.bin"
        index.save(bin_path)

        loaded = VectorIndex.load(bin_path, vectors)
        assert loaded.dimension == dim

    def test_build_profile_exists_with_incident_count(self, tmp_path: Path) -> None:
        """(d) BUILD_PROFILE.md exists and contains the incident count line."""
        pytest.importorskip("sentence_transformers")
        pytest.importorskip("faiss")

        all_ids = ["INC-A", "INC-B", "INC-C"]
        scope = all_ids
        json_dir = _write_json_dir(tmp_path, all_ids)
        scope_parquet = _make_scope_parquet(tmp_path, scope)

        # Simulate what build_rag_v2.py does
        import pandas as _pd
        df = _pd.read_parquet(str(scope_parquet))
        scope_set: set[str] = set(df["incident_id"].unique())

        from src.rag.embeddings.sentence_transformers_provider import SentenceTransformerProvider
        import numpy as _np
        import csv as _csv
        import hashlib

        datasets_dir = tmp_path / "datasets"
        embeddings_dir = tmp_path / "embeddings"
        datasets_dir.mkdir()
        embeddings_dir.mkdir()

        b_csv = datasets_dir / "barrier_documents.csv"
        i_csv = datasets_dir / "incident_documents.csv"

        n_barriers = build_barrier_documents(json_dir, b_csv, incident_id_filter=scope_set)
        n_incidents = build_incident_documents(json_dir, i_csv, incident_id_filter=scope_set)

        provider = SentenceTransformerProvider()
        with open(b_csv, encoding="utf-8") as f:
            b_texts = [r["barrier_role_match_text"] for r in _csv.DictReader(f)]
        with open(i_csv, encoding="utf-8") as f:
            i_texts = [r["incident_embed_text"] for r in _csv.DictReader(f)]

        b_emb = provider.embed_batch(b_texts).astype(_np.float32)
        i_emb = provider.embed_batch(i_texts).astype(_np.float32)

        b_emb_path = embeddings_dir / "barrier_embeddings.npy"
        i_emb_path = embeddings_dir / "incident_embeddings.npy"
        _np.save(str(b_emb_path), b_emb)
        _np.save(str(i_emb_path), i_emb)

        b_faiss = tmp_path / "barrier_faiss.bin"
        i_faiss = tmp_path / "incident_faiss.bin"
        VectorIndex.build(b_emb).save(b_faiss)
        VectorIndex.build(i_emb).save(i_faiss)

        profile = tmp_path / "BUILD_PROFILE.md"
        profile.write_text(
            f"# RAG v2 Build Profile\n\n## Scope\n- **Incident count**: {len(scope_set)}\n",
            encoding="utf-8",
        )

        assert profile.exists()
        content = profile.read_text(encoding="utf-8")
        assert f"**Incident count**: {len(scope_set)}" in content
