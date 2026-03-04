# Data Pipeline Contract v1

Defines the canonical data layout, pipeline flow, layer responsibilities, and invariants for the Bowtie Risk Analytics project. All contributors and automation must conform to this contract.

---

## 1. Canonical Data Directory Structure

```
data/
├── raw/                          # Layer 0: Ingested source documents
│   ├── bsee/                     #   BSEE incident PDFs, text, manifests
│   │   ├── pdf/
│   │   ├── pdfs/                 #   Legacy PDF location (read-only, corpus_v1 reference)
│   │   ├── text/
│   │   └── manifest.csv
│   ├── csb/                      #   CSB incident PDFs, text, manifests
│   │   ├── pdf/
│   │   ├── text/
│   │   └── manifest.csv
│   ├── phmsa/                    #   PHMSA PDFs, text, manifests
│   │   ├── pdf/
│   │   ├── text/
│   │   └── manifest.csv
│   ├── tsb/                      #   TSB HTML downloads, extracted text
│   │   ├── html/
│   │   ├── text/
│   │   └── manifest.csv
│   ├── incidents_manifest_v0.csv #   Legacy acquire-mode manifest
│   └── text_manifest_v0.csv      #   Legacy extract-text manifest
│
├── structured/                   # Layer 1: LLM extraction outputs
│   ├── incidents/                #   Validated incident JSON (provider-bucketed)
│   │   └── schema_v2_3/          #     Default extraction target (canonical V2.3)
│   ├── debug_llm_responses/      #   Raw LLM response text (debug/audit only)
│   │   └── <provider>/           #     One subdir per provider name
│   ├── run_reports/              #   Extraction run metadata JSON
│   └── structured_manifest.csv   #   Extraction tracking manifest
│
├── processed/                    # Layer 2: Pipeline analytics outputs
│   ├── flat_incidents_combined.csv
│   ├── controls_combined.csv
│   ├── fleet_metrics.json
│   └── <incident_id>.json        #   Per-incident processed output
│
├── corpus_v1/                    # Frozen corpus (V2.2 schema, 147 incidents)
│   ├── raw_pdfs/                 #   148 source PDFs (read-only)
│   ├── structured_json/          #   147 Claude-extracted JSONs
│   ├── structured_json_noise/    #   66 quarantined non-incident JSONs
│   └── manifests/
│       └── corpus_v1_manifest.csv
│
├── sources/                      # Fallback URL discovery output
│   ├── bsee/                     #   (primary target is configs/sources/bsee/)
│   ├── csb/
│   └── phmsa/
│
configs/
└── sources/                      # Primary URL discovery output
    ├── bsee/
    │   ├── url_list.csv
    │   └── url_list_metadata.csv
    ├── csb/
    └── phmsa/

out/
└── association_mining/           # Association mining script outputs
    ├── incidents_aggregated.json
    ├── incidents_flat.csv
    └── normalized_df.csv

archive/                          # Non-executable historical storage (see Section 6)
└── data/
```

---

## 2. Canonical Pipeline Flow

### Primary Pipeline

```
WEB (CSB / BSEE / PHMSA / TSB)
        │
  discover-source
        │
  configs/sources/<source>/url_list.csv
        │
  ┌─────┴──────┐
  │            │
ingest-source  acquire
  │            │
  ▼            ▼
data/raw/<source>/          data/raw/
├── pdf/*.pdf               ├── *.pdf
├── text/*.txt              ├── incidents_manifest_v0.csv
└── manifest.csv            └── text_manifest_v0.csv
                                │
                          extract-text
                                │
                          data/raw/<source>/text/*.txt
                                │
                       extract-structured
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                   │
data/structured/        data/structured/     data/structured/
incidents/schema_v2_3/  debug_llm_responses/ run_reports/
              │
     ┌────────┴────────┐
     │                 │
convert-schema    schema-check
     │            quality-gate
     │            (read-only validation)
     │
build-combined-exports
     │
data/processed/
├── flat_incidents_combined.csv
└── controls_combined.csv
```

### Corpus Sub-Pipeline (self-contained)

```
data/corpus_v1/raw_pdfs/  +  data/raw/{csb,bsee}/text/
        │
  corpus-manifest  →  data/corpus_v1/manifests/corpus_v1_manifest.csv
        │
  corpus-extract   →  data/corpus_v1/structured_json/*.json
        │
  corpus-clean     →  moves noise to structured_json_noise/
```

### Association Mining Chain (scripts, not pipeline)

```
data/structured/incidents/schema_v2_3/*.json
    → scripts/association_mining/jsonaggregation.py
    → out/association_mining/incidents_aggregated.json
    → scripts/association_mining/jsonflattening.py
    → out/association_mining/incidents_flat.csv
    → scripts/association_mining/event_barrier_normalization.py
    → out/association_mining/normalized_df.csv
```

### LOC Scoring

```
data/raw/csb/manifest.csv  +  data/raw/csb/<text_path>
    → src/nlp/loc_scoring.py run()
    → data/processed/csb_loc_scored.csv
```

---

## 3. Layer Responsibilities

| Layer | Directory | Responsibility | Written by |
|-------|-----------|---------------|------------|
| **L0: Raw** | `data/raw/` | Source documents exactly as ingested. PDFs, extracted text, per-source manifests. | `acquire`, `extract-text`, `ingest-source` |
| **L1: Structured** | `data/structured/` | LLM extraction outputs. Validated V2.3 JSON, raw LLM debug text, run reports, extraction manifest. | `extract-structured`, `convert-schema` |
| **L2: Processed** | `data/processed/` | Analytics-ready flat exports, fleet metrics, per-incident processed JSON. | `build-combined-exports`, `process`, `loc_scoring` |
| **Corpus** | `data/corpus_v1/` | Frozen V2.2 corpus. Self-contained sub-pipeline. PDFs are read-only. | `corpus-manifest`, `corpus-extract`, `corpus-clean` |
| **Sources** | `data/sources/` | Fallback URL list storage (primary is `configs/sources/`). | `discover-source` (fallback only) |
| **Scripts** | `out/` | Association mining intermediate and final outputs. Not consumed by `src/pipeline.py`. | `jsonaggregation.py`, `jsonflattening.py`, `event_barrier_normalization.py` |

---

## 4. Invariants

These are non-negotiable rules. Violations indicate a bug or unauthorized change.

1. **Layer isolation.** L0 (`raw/`) never reads from L1 or L2. L1 (`structured/`) reads from L0 only. L2 (`processed/`) reads from L1 only. No reverse dependencies.

2. **Single source of truth for controls.** `get_controls()` in `src/ingestion/structured.py` is the only function that extracts controls from V2.2 or V2.3 structures. All consumers (flatten, analytics, export) call this function.

3. **Canonical schema is Jeffrey V2.3.** Eight top-level keys: `incident_id`, `schema_version`, `source`, `context`, `event`, `bowtie`, `pifs`, `notes`. All new extraction targets V2.3.

4. **BOM encoding for V2.3 JSON files.** Read with `encoding="utf-8-sig"`. Write without BOM in `encoding="utf-8"`.

5. **Manifests are append-only ledgers.** Manifest CSVs track pipeline state. Rows are appended or replaced by `doc_id`; rows are never silently deleted.

6. **Provider bucketing in `structured/incidents/`.** Subdirectories are named by LLM provider or schema version (`anthropic`, `openai`, `schema_v2_3`), never by source agency.

7. **Source bucketing in `raw/`.** Subdirectories are named by source agency (`bsee`, `csb`, `phmsa`, `tsb`), never by provider.

8. **`corpus_v1/` is frozen.** The 148-PDF / 147-JSON corpus is a fixed reference dataset. `corpus-extract` may fill gaps but does not overwrite existing JSONs.

9. **`debug_llm_responses/` is never read by pipeline.** It exists for forensic inspection only. No downstream command depends on its contents.

10. **`out/` is script-only.** No `src/pipeline.py` subcommand reads from or writes to `out/`. It is exclusively used by `scripts/association_mining/`.

---

## 5. Extension Rules

### Adding a RAG layer
- Create `data/rag/` at the same level as `raw/`, `structured/`, `processed/`.
- RAG reads from L1 (`structured/incidents/`) or L2 (`processed/`). Never from L0 directly.
- Embeddings and vector indices live under `data/rag/embeddings/` and `data/rag/indices/`.
- Add a `rag` subcommand to `pipeline.py` following existing argparse patterns.

### Adding modeling outputs
- Create `data/models/` for trained model artifacts, predictions, evaluation results.
- Models consume from L2 (`processed/`) or from `out/association_mining/` normalized outputs.
- Never write model artifacts into `structured/` or `raw/`.

### Adding dashboard data
- The Streamlit dashboard reads from `data/processed/` via `src/app/utils.py`.
- New dashboard data sources must be added to `data/processed/` or a new `data/dashboard/` directory.
- Dashboard code never writes to `data/`. It is strictly read-only.

### Adding a new ingestion source
- Extend `_DISCOVER_ADAPTERS` in `pipeline.py`.
- Extend `_DOC_TYPE_RULES` in `src/analytics/build_combined_exports.py`.
- Create `src/ingestion/sources/<source>_discover.py` and optionally `<source>_ingest.py`.
- Output follows the existing pattern: `data/raw/<source>/{pdf,text,manifest.csv}`.
- Add `configs/sources/<source>/` for URL lists.

---

## 6. Archive Policy

`archive/` is **non-executable historical storage**.

- No source code, script, test, or pipeline subcommand reads from or writes to `archive/`.
- Argparse defaults pointing into `archive/` (e.g., PHMSA placeholder, experimental QC) exist only as dormant stubs for unfinished features. They do not constitute active pipeline paths.
- Contents of `archive/` may be deleted without affecting pipeline behavior.
- `archive/` is gitignored. Its contents are local-only and not version-controlled.

Current archive contents:

| Path | Origin | Reason |
|------|--------|--------|
| `archive/legacy_quarantine/` | Root `_quarantine/` | Legacy quarantine directory |
| `archive/deliverables/` | Root zip file | Handoff deliverable bundle |
| `archive/data/orphan_sample/` | `data/sample/` | Unreferenced directory (not `data/samples/`) |
| `archive/data/legacy_interim/` | `data/interim/` | No code references |
| `archive/data/derived_experiments/` | `data/derived/` | Docs-only references |
| `archive/data/legacy_pipeline_outputs/` | Multiple `data/` subdirs | Directories with no active write path |
| `archive/data/experimental_qc_extraction/` | `data/processed/text/` | QC-only extraction, not in main pipeline |
| `archive/data/phmsa_placeholder/` | `data/manifests/` | Skeleton PHMSA manifest (unfinished) |

---

## 7. Do Not

1. **Do not write pipeline outputs to `data/raw/`.** Raw is for ingested source documents only. Analytics outputs belong in `processed/`.

2. **Do not create source-agency subdirectories under `data/structured/incidents/`.** Provider bucketing only. `structured/incidents/bsee/` is wrong; `structured/incidents/anthropic/` is correct.

3. **Do not read from `debug_llm_responses/` in any pipeline command.** It is a write-only debug sink.

4. **Do not bypass `get_controls()`.** Directly parsing `bowtie.controls` from JSON without going through `get_controls()` will break on V2.2/V2.3 schema differences.

5. **Do not store embeddings, model weights, or vector indices in `data/structured/` or `data/processed/`.** These belong in dedicated directories (`data/rag/`, `data/models/`).

6. **Do not write to `out/` from `src/pipeline.py`.** The `out/` tree is reserved for standalone scripts.

7. **Do not add new top-level directories under `data/` without updating this contract.** The current set (`raw`, `structured`, `processed`, `corpus_v1`, `sources`) is intentional.

8. **Do not delete or overwrite `corpus_v1/raw_pdfs/` contents.** This is a frozen reference dataset.

9. **Do not commit anything under `data/` except `data/samples/`.** All other `data/` directories are gitignored.

10. **Do not use `archive/` as a runtime dependency.** If code needs a path, it belongs in `data/` or `configs/`, not `archive/`.
