# Architecture Freeze v1

**Date:** 2026-03-04
**Branch:** stabilization/pass-1-shadow-fix
**Status:** FROZEN — no structural changes without explicit approval

---

## 1. Canonical Directory Contracts

### Active Data Directories

```
data/
├── raw/                                    # L0: Ingested source documents
│   ├── bsee/
│   │   ├── pdf/                            # 526 BSEE PDFs (canonical)
│   │   ├── text/                           # Extracted text
│   │   ├── _reports/                       # BSEE report metadata
│   │   └── manifest.csv
│   ├── csb/
│   │   ├── pdf/                            # CSB PDFs
│   │   ├── text/                           # Extracted text
│   │   └── manifest.csv
│   ├── phmsa/                              # Skeleton (no data)
│   └── tsb/                                # Skeleton (no data)
│
├── structured/                             # L1: LLM extraction outputs
│   ├── incidents/
│   │   └── schema_v2_3/                    # 739 canonical V2.3 JSONs (SINGLE SOURCE OF TRUTH)
│   ├── debug_llm_responses/                # Raw LLM text (forensic only, never read by pipeline)
│   ├── run_reports/                        # Extraction run metadata
│   └── structured_manifest.csv
│
├── processed/                              # L2: Analytics-ready exports
│   ├── flat_incidents_combined.csv         # 739 rows
│   └── controls_combined.csv              # 4,776 rows
│
├── corpus_v1/                              # Frozen V2.2 corpus (self-contained)
│   ├── raw_pdfs/                           # 148 source PDFs (gitignored)
│   ├── structured_json/                    # 147 V2.2 JSONs (gitignored)
│   ├── structured_json_noise/              # 66 quarantined
│   └── manifests/
│
├── sources/                                # Fallback URL discovery output
│   ├── bsee/
│   ├── csb/
│   └── phmsa/
│
configs/
└── sources/                                # Primary URL discovery output
    ├── bsee/
    ├── csb/
    └── phmsa/

out/
└── association_mining/                     # Script-only outputs
    ├── incidents_aggregated.json
    ├── incidents_flat.csv
    └── normalized_df.csv
```

### Archived Directories (non-executable)

```
archive/
├── data/
│   ├── legacy_structured_runs/
│   │   ├── canonical_v23/              # 575 JSONs — strict subset of schema_v2_3
│   │   └── raw/                        # 1,339 JSONs — historical extraction runs
│   ├── legacy_bsee_pdfs/               # 100 PDFs — URL-encoded names from acquire command
│   ├── legacy_pipeline_outputs/        # Empty dirs from inactive pipeline paths
│   ├── orphan_sample/                  # data/sample/ — zero code references
│   ├── legacy_interim/                 # data/interim/ — no code references
│   ├── derived_experiments/            # data/derived/ — docs-only references
│   ├── experimental_qc_extraction/     # data/processed/text/ — QC-only, not main pipeline
│   └── phmsa_placeholder/             # data/manifests/ — skeleton PHMSA manifest
├── deliverables/                       # Handoff zip bundle
└── legacy_quarantine/                  # Root _quarantine/ directory
```

---

## 1b. Schema Template Contract

- **Canonical template:** `assets/schema/incident_schema_v2_3_template.json`
- **Schema version:** 2.3 (content aligned with Jeffrey V2.3 canonical schema)
- **Loaded by:** `src/prompts/loader.py` → injected into LLM prompt via `{{SCHEMA_TEMPLATE}}`
- **Validated by:** Pydantic models in `src/models/incident_v23.py` (template is not used for validation)
- **Top-level keys:** `incident_id`, `source`, `context`, `event`, `bowtie`, `pifs`, `notes`

## 1c. Canonical Pipeline Flow

```
raw/ → structured/incidents/schema_v2_3/ → processed/ (flat CSVs)
                                         → out/association_mining/ (scripts)
```

Detailed:
```
L0 raw/<source>/text/
    → extract-structured
L1 structured/incidents/schema_v2_3/*.json
    → build-combined-exports
L2 processed/{flat_incidents_combined,controls_combined}.csv

L1 structured/incidents/schema_v2_3/*.json
    → jsonaggregation.py → jsonflattening.py → event_barrier_normalization.py
    out/association_mining/{aggregated,flat,normalized}
```

---

## 2. Data Invariants

1. **Single canonical structured bucket.** All validated V2.3 incident JSON lives in `data/structured/incidents/schema_v2_3/`. No other directory under `structured/incidents/` is a valid extraction target.

2. **739 incidents, 739 unique IDs.** The canonical bucket contains exactly 739 JSON files with 739 unique `incident_id` values. All have `"schema_version": "2.3"`.

3. **4,776 controls.** The canonical 739 incidents yield exactly 4,776 control rows when flattened via `get_controls()`.

4. **Layer isolation.** L0 (`raw/`) never reads from L1 or L2. L1 (`structured/`) reads from L0 only. L2 (`processed/`) reads from L1 only.

5. **BOM encoding.** V2.3 JSON files are read with `encoding="utf-8-sig"`, written with `encoding="utf-8"`.

6. **Provider bucketing in structured/.** Subdirectories are named by provider or schema version, never by source agency.

7. **Source bucketing in raw/.** Subdirectories are named by source agency, never by provider.

8. **Single PDF directory per source.** Each source has exactly one `pdf/` directory. The legacy `pdfs/` (plural) path is archived and must not be recreated.

9. **Manifests are append-only.** Rows are appended or replaced by `doc_id`; never silently deleted.

10. **`debug_llm_responses/` is write-only.** No pipeline command reads from it.

---

## 3. Export Invariants

| Export | Location | Rows | Writer |
|--------|----------|------|--------|
| `flat_incidents_combined.csv` | `data/processed/` | 739 | `build_combined_exports.py` |
| `controls_combined.csv` | `data/processed/` | 4,776 | `build_combined_exports.py` |
| `incidents_aggregated.json` | `out/association_mining/` | 739 | `jsonaggregation.py` |
| `incidents_flat.csv` | `out/association_mining/` | 4,776 | `jsonflattening.py` |
| `normalized_df.csv` | `out/association_mining/` | 4,776 | `event_barrier_normalization.py` |

Each export has exactly one writer. No duplicate outputs exist.

---

## 4. Archived Directories Policy

`archive/` is non-executable historical storage.

- No source code, script, test, or pipeline subcommand reads from `archive/`.
- Argparse defaults pointing into `archive/` (PHMSA placeholder, experimental QC) are dormant stubs.
- Contents may be deleted without affecting pipeline behavior.
- `archive/` is gitignored and local-only.

---

## 5. Modeling / RAG Extension Boundary

No RAG, embedding, vector, or ML prediction code exists in the codebase.

### Extension rules:

| Extension | Where to place data | Reads from | Must NOT write to |
|-----------|-------------------|------------|------------------|
| RAG / embeddings | `data/rag/` | L1 (`structured/incidents/schema_v2_3/`) or L2 (`processed/`) | `structured/`, `raw/` |
| Model artifacts | `data/models/` | L2 (`processed/`) or `out/association_mining/` | `structured/`, `raw/` |
| Dashboard data | `data/processed/` or `data/dashboard/` | L2 only | `structured/`, `raw/` |

New top-level `data/` directories require updating `docs/architecture/data_pipeline_contract_v1.md`.

---

## 6. Active Sources

| Source | Status | Data |
|--------|--------|------|
| **BSEE** | Active | 526 PDFs, 624 text files, 690 JSONs in schema_v2_3 |
| **CSB** | Active | 49 PDFs, 49 JSONs in schema_v2_3 |
| **PHMSA** | Skeleton | Empty dirs, header-inspection stub only |
| **TSB** | Skeleton | Empty dirs, manifest.csv only |

PHMSA and TSB are isolated ingestion adapters. They:
- Are imported only by `pipeline.py` (top-level)
- Have no data flowing through the pipeline
- Do not interfere with CSB/BSEE processing
- Are handled generically by `build_combined_exports.py` via lookup tables

---

## 7. Forbidden Patterns

1. Do not create additional directories under `data/structured/incidents/` beyond `schema_v2_3/`.
2. Do not recreate `data/raw/bsee/pdfs/` (legacy, archived).
3. Do not recreate `data/structured/incidents/canonical_v23/` or `data/structured/incidents/raw/` (archived).
4. Do not write pipeline outputs to `data/raw/`.
5. Do not read from `archive/` in any pipeline command.
6. Do not bypass `get_controls()` for control extraction.
7. Do not store ML/RAG artifacts in `structured/` or `raw/`.
8. Do not write to `out/` from `src/pipeline.py`.
9. Do not add `data/` directories without updating the architecture contract.
10. Do not use `rglob` against `data/structured/incidents/` root — always target `schema_v2_3/` directly.

---

## 8. Test Summary

| Suite | Result |
|-------|--------|
| pytest | **300 passed, 1 skipped** |
| build-combined-exports | **739 incidents, 4,776 controls** |
| association mining (full chain) | **739 aggregated → 4,776 flattened → 4,776 normalized** |
| smoke test | **passed** |
| pipeline CLI help | **all 15 subcommands load** |

---

## 9. Statement of Freeze

This architecture is frozen as of 2026-03-04. The data layer, directory structure, and pipeline contracts defined in this document and in `docs/architecture/data_pipeline_contract_v1.md` are authoritative.

Structural changes (new data directories, path renames, new export writers) require:
1. Updating `data_pipeline_contract_v1.md`
2. Updating this freeze document
3. Re-running the full validation suite (all 5 phases)
4. Explicit approval

The codebase is ready for modeling, RAG, and advanced analytics work within the extension boundaries defined above.
