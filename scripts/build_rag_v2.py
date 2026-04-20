#!/usr/bin/env python3
"""Build v2 RAG corpus scoped to 156-incident cascading training set.

Reads data/processed/cascading_training.parquet to determine the incident
scope, then builds barrier + incident document CSVs, embeddings, and FAISS
indexes under data/rag/v2/.

Usage:
    python scripts/build_rag_v2.py
"""
from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── path setup ────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.rag.corpus_builder import build_barrier_documents, build_incident_documents
from src.rag.embeddings.sentence_transformers_provider import SentenceTransformerProvider
from src.rag.vector_index import VectorIndex

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("build_rag_v2")

PARQUET_PATH = Path("data/processed/cascading_training.parquet")
JSON_DIR = Path("data/structured/incidents/schema_v2_3")
OUT_DIR = Path("data/rag/v2")
DATASETS_DIR = OUT_DIR / "datasets"
EMBEDDINGS_DIR = OUT_DIR / "embeddings"
BATCH_SIZE = 32


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> None:
    # ── 1. Resolve scope ───────────────────────────────────────────
    logger.info("Reading cascading training parquet: %s", PARQUET_PATH)
    df = pd.read_parquet(PARQUET_PATH)
    scope: set[str] = set(df["incident_id"].unique())
    logger.info("Scope resolved: %d unique incident_ids", len(scope))
    if not scope:
        logger.error("Filtered incident list is empty — aborting.")
        sys.exit(1)

    # Sanity check JSON dir has matching files
    json_files = list(JSON_DIR.glob("*.json"))
    if not json_files:
        logger.error("No JSON files in %s — aborting.", JSON_DIR)
        sys.exit(1)

    # ── 2. Build document CSVs ─────────────────────────────────────
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    barrier_csv = DATASETS_DIR / "barrier_documents.csv"
    incident_csv = DATASETS_DIR / "incident_documents.csv"

    logger.info("Building barrier documents (scope=%d)…", len(scope))
    n_barriers = build_barrier_documents(JSON_DIR, barrier_csv, incident_id_filter=scope)
    logger.info("Barrier CSV rows written: %d → %s", n_barriers, barrier_csv)

    logger.info("Building incident documents (scope=%d)…", len(scope))
    n_incidents = build_incident_documents(JSON_DIR, incident_csv, incident_id_filter=scope)
    logger.info("Incident CSV rows written: %d → %s", n_incidents, incident_csv)

    if n_barriers == 0 or n_incidents == 0:
        logger.error(
            "Zero rows written (barriers=%d, incidents=%d) — aborting.",
            n_barriers, n_incidents,
        )
        sys.exit(1)

    # ── 3. Read embed texts ────────────────────────────────────────
    import csv as csv_mod

    with open(barrier_csv, encoding="utf-8") as f:
        barrier_rows = list(csv_mod.DictReader(f))
    barrier_texts = [r["barrier_role_match_text"] for r in barrier_rows]

    with open(incident_csv, encoding="utf-8") as f:
        incident_rows = list(csv_mod.DictReader(f))
    incident_texts = [r["incident_embed_text"] for r in incident_rows]

    # ── 4. Compute embeddings ──────────────────────────────────────
    logger.info("Loading SentenceTransformerProvider (all-mpnet-base-v2)…")
    provider = SentenceTransformerProvider()

    logger.info("Embedding %d barrier texts (batch=%d)…", len(barrier_texts), BATCH_SIZE)
    barrier_emb = _embed_batched(provider, barrier_texts, BATCH_SIZE)
    logger.info("Barrier embeddings shape: %s", barrier_emb.shape)

    logger.info("Embedding %d incident texts (batch=%d)…", len(incident_texts), BATCH_SIZE)
    incident_emb = _embed_batched(provider, incident_texts, BATCH_SIZE)
    logger.info("Incident embeddings shape: %s", incident_emb.shape)

    # Rowcount consistency check
    if barrier_emb.shape[0] != n_barriers:
        logger.error(
            "Barrier embedding row mismatch: emb=%d csv=%d", barrier_emb.shape[0], n_barriers
        )
        sys.exit(1)
    if incident_emb.shape[0] != n_incidents:
        logger.error(
            "Incident embedding row mismatch: emb=%d csv=%d", incident_emb.shape[0], n_incidents
        )
        sys.exit(1)

    # ── 5. Save embeddings ─────────────────────────────────────────
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    barrier_emb_path = EMBEDDINGS_DIR / "barrier_embeddings.npy"
    incident_emb_path = EMBEDDINGS_DIR / "incident_embeddings.npy"

    np.save(str(barrier_emb_path), barrier_emb)
    np.save(str(incident_emb_path), incident_emb)
    logger.info("Saved barrier embeddings → %s", barrier_emb_path)
    logger.info("Saved incident embeddings → %s", incident_emb_path)

    # ── 6. Build + save FAISS indexes ─────────────────────────────
    barrier_faiss_path = OUT_DIR / "barrier_faiss.bin"
    incident_faiss_path = OUT_DIR / "incident_faiss.bin"

    logger.info("Building barrier FAISS index (dim=%d)…", barrier_emb.shape[1])
    barrier_index = VectorIndex.build(barrier_emb)
    barrier_index.save(barrier_faiss_path)
    logger.info("Saved barrier FAISS index → %s", barrier_faiss_path)

    logger.info("Building incident FAISS index (dim=%d)…", incident_emb.shape[1])
    incident_index = VectorIndex.build(incident_emb)
    incident_index.save(incident_faiss_path)
    logger.info("Saved incident FAISS index → %s", incident_faiss_path)

    # ── 7. Write BUILD_PROFILE.md ──────────────────────────────────
    profile_path = OUT_DIR / "BUILD_PROFILE.md"
    _write_build_profile(
        profile_path,
        scope_count=len(scope),
        barrier_csv_rows=n_barriers,
        incident_csv_rows=n_incidents,
        barrier_emb_shape=barrier_emb.shape,
        incident_emb_shape=incident_emb.shape,
        barrier_csv=barrier_csv,
        incident_csv=incident_csv,
        barrier_emb_path=barrier_emb_path,
        incident_emb_path=incident_emb_path,
        barrier_faiss_path=barrier_faiss_path,
        incident_faiss_path=incident_faiss_path,
    )
    logger.info("Written BUILD_PROFILE.md → %s", profile_path)
    logger.info("Build complete.")


def _embed_batched(provider: SentenceTransformerProvider, texts: list[str], batch_size: int) -> np.ndarray:
    chunks: list[np.ndarray] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        chunks.append(provider.embed_batch(batch))
        logger.info("  Embedded rows %d–%d", start, start + len(batch) - 1)
    return np.vstack(chunks).astype(np.float32)


def _write_build_profile(
    path: Path,
    scope_count: int,
    barrier_csv_rows: int,
    incident_csv_rows: int,
    barrier_emb_shape: tuple[int, ...],
    incident_emb_shape: tuple[int, ...],
    barrier_csv: Path,
    incident_csv: Path,
    barrier_emb_path: Path,
    incident_emb_path: Path,
    barrier_faiss_path: Path,
    incident_faiss_path: Path,
) -> None:
    artifacts = [
        ("barrier_documents.csv", barrier_csv),
        ("incident_documents.csv", incident_csv),
        ("barrier_embeddings.npy", barrier_emb_path),
        ("incident_embeddings.npy", incident_emb_path),
        ("barrier_faiss.bin", barrier_faiss_path),
        ("incident_faiss.bin", incident_faiss_path),
    ]
    sha_lines = "\n".join(f"- `{name}`: `{_sha256(p)}`" for name, p in artifacts)
    content = f"""# RAG v2 Build Profile

## Scope
- **Incident count**: {scope_count}
- **Barrier CSV rows**: {barrier_csv_rows}
- **Incident CSV rows**: {incident_csv_rows}

## Embedding Shapes
- `barrier_embeddings.npy`: {barrier_emb_shape}
- `incident_embeddings.npy`: {incident_emb_shape}

## Artifact SHA256
{sha_lines}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
