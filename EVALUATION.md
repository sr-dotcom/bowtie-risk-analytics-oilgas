# Evaluation — Bowtie Risk Analytics

Quantitative results for all three models and the RAG retrieval system. Metrics are sourced directly from `data/models/evaluation/training_report.json`, `data/models/evaluation/pif_ablation_report.json`, and `data/models/evaluation/data_recon_report.json`.

> **Reproduce artifacts:** See `docs/architecture/ARCHITECTURE_FREEZE_v1.md` → *4-step generation process* in RUNTIME.md.

---

## Training Data

| Property | Value |
|----------|-------|
| Extraction corpus (controls CSV) | `data/processed/controls_combined.csv` — 4,776 rows across 739 incidents |
| Training scope | **558 rows** — domain-informed filtering applied after extraction (LOC scenarios, sufficient evidence quality) |
| Incident groups in training scope | **174 unique incidents** |
| Incident types | Loss of Containment (LOC) scenarios |
| Sources | CSB, BSEE |

> The full extraction corpus of 4,688 training-eligible rows (4,776 total minus 88 `barrier_status=unknown`) is available in `data/models/artifacts/feature_matrix.parquet`. The 558-row training scope applies domain-informed filtering on top of this to focus on well-evidenced LOC controls.

**Label distribution (training scope, 558 rows):**

| Label | Positive | Positive rate |
|-------|----------|---------------|
| `label_barrier_failed` — barrier did not perform | — / 558 | ~72.9% |
| `label_barrier_failed_human` — barrier failed + human factor contributed | — / 558 | **11.3%** |

**Label derivation:**
```python
label_barrier_failed = barrier_status in {'failed', 'degraded', 'not_installed', 'bypassed'}
label_barrier_failed_human = label_barrier_failed AND (barrier_failed_human == True)
# Exclude rows where barrier_status == 'unknown'
```

**Cross-validation:** 5-fold `GroupKFold` on `incident_id`. Groups prevent PIF leakage — PIF features are incident-level (broadcast to all controls in the same incident), so fold boundaries must respect incident identity.

---

## Features

18 features total: 6 categorical + 9 PIF booleans + 3 numeric.

| # | Feature | Category | Type |
|---|---------|----------|------|
| 1 | `side` | barrier | Categorical (OrdinalEncoded) |
| 2 | `barrier_type` | barrier | Categorical (OrdinalEncoded) |
| 3 | `line_of_defense` | barrier | Categorical (OrdinalEncoded) |
| 4 | `barrier_family` | barrier | Categorical (OrdinalEncoded) — 25 families |
| 5 | `top_event_category` | incident_context | Categorical (OrdinalEncoded) |
| 6 | `source_agency` | incident_context | Categorical (OrdinalEncoded) |
| 7 | `pif_competence` | incident_context | Boolean (0/1) |
| 8 | `pif_communication` | incident_context | Boolean (0/1) |
| 9 | `pif_situational_awareness` | incident_context | Boolean (0/1) |
| 10 | `pif_procedures` | incident_context | Boolean (0/1) |
| 11 | `pif_tools_equipment` | incident_context | Boolean (0/1) |
| 12 | `pif_safety_culture` | incident_context | Boolean (0/1) |
| 13 | `pif_management_of_change` | incident_context | Boolean (0/1) |
| 14 | `pif_supervision` | incident_context | Boolean (0/1) |
| 15 | `pif_training` | incident_context | Boolean (0/1) |
| 16 | `supporting_text_count` | barrier | Numeric (int) |
| 17 | `primary_threat_category` | barrier | Numeric (encoded int) |
| 18 | `pathway_sequence` | barrier | Numeric (int) |
| 19 | `upstream_failure_rate` | barrier | Numeric (float) |

> PIFs dropped from the 12-feature set: `pif_fatigue`, `pif_workload`, `pif_time_pressure` — excluded during domain-informed feature selection. `source_agency` and `top_event_category` are incident-level, not barrier-level.

**Encoding:** OrdinalEncoder with `handle_unknown='use_encoded_value'`, `unknown_value=-1`. Saved to `data/models/artifacts/encoder.joblib`. Feature column order is locked in `data/models/artifacts/feature_names.json`.

---

## Model Performance

All metrics are 5-fold GroupKFold cross-validation means. F1 and MCC are for the positive (minority) class. Metrics reported: F1-minority, MCC, Precision, Recall.

### Model 1 — Barrier Did Not Perform (`label_barrier_failed`)

**XGBoost** (`n_estimators=300`, `max_depth=4`, `lr=0.05`, `scale_pos_weight=0.372`):

| Metric | Mean | Std |
|--------|------|-----|
| F1 (minority) | **0.928** | ±0.019 |
| MCC | **0.793** | ±0.037 |
| Precision | 0.942 | ±0.021 |
| Recall | 0.917 | ±0.037 |

**LogReg** (`class_weight=balanced`, `solver=lbfgs`, `C=1.0`):

| Metric | Mean | Std |
|--------|------|-----|
| F1 (minority) | 0.800 | ±0.051 |
| MCC | 0.469 | ±0.068 |
| Precision | 0.847 | ±0.045 |
| Recall | 0.758 | ±0.056 |

### Model 2 — Barrier Failed with Human Factor (`label_barrier_failed_human`)

**XGBoost** (`scale_pos_weight=1.971`):

| Metric | Mean | Std |
|--------|------|-----|
| F1 (minority) | **0.348** | ±0.060 |
| MCC | **0.266** | ±0.075 |
| Precision | 0.347 | ±0.082 |
| Recall | 0.366 | ±0.091 |

**LogReg:**

| Metric | Mean | Std |
|--------|------|-----|
| F1 (minority) | 0.383 | ±0.065 |
| MCC | 0.304 | ±0.093 |
| Precision | 0.275 | ±0.049 |
| Recall | 0.648 | ±0.126 |

> **Note:** Model 2 is inherently harder — the human factor contribution signal is sparse and noisier than the barrier failure signal. LogReg achieves higher recall at the cost of precision; XGBoost is more balanced. Both are deployed; the dashboard uses Model 1 probability as the primary risk score.

### Model 3 — Barrier Condition (3-class: effective / degraded / ineffective)

**XGBoost** (multiclass):

| Metric | Mean | Std |
|--------|------|-----|
| F1 (macro) | **0.588** | ±0.028 |
| F1 (weighted) | **0.726** | ±0.040 |
| MCC | **0.583** | ±0.042 |
| F1 (effective) | 0.863 | ±0.023 |
| F1 (degraded) | 0.092 | ±0.050 |
| F1 (ineffective) | 0.810 | ±0.034 |

**LogReg** (multiclass):

| Metric | Mean | Std |
|--------|------|-----|
| F1 (macro) | 0.508 | ±0.028 |
| F1 (weighted) | 0.570 | ±0.021 |
| MCC | 0.310 | ±0.038 |
| F1 (effective) | 0.659 | ±0.025 |
| F1 (degraded) | 0.269 | ±0.058 |
| F1 (ineffective) | 0.596 | ±0.053 |

> **Note:** The `degraded` class is the hardest — it sits between the two poles and has the least training support. XGBoost outperforms LogReg significantly on macro F1.

### Risk Thresholds (Model 1)

Percentile cutoffs computed over the 558-row training scope predictions:

| Threshold | Value | Meaning |
|-----------|-------|---------|
| p60 | 0.9801 | Low / Medium boundary |
| p80 | 0.9932 | Medium / High boundary |

Risk level assignment:
- **High** (red): probability ≥ 0.9932
- **Medium** (amber): 0.9801 ≤ probability < 0.9932
- **Low** (green): probability < 0.9801

Stored in `data/models/artifacts/risk_thresholds.json` (canonical: `frontend/public/risk_thresholds.json`).

---

## SHAP Explainability

SHAP TreeExplainer is used to produce per-barrier feature attributions for both models. Key implementation choices:

- **Separate explainers:** Model 1 and Model 2 always use separate `TreeExplainer` instances with separate 200-sample background arrays (`shap_background_model1.npy`, `shap_background_model2.npy`). SHAP values from the two models are never merged.
- **Feature categories:** 9 PIF features plus `top_event_category` and `source_agency` are labeled `incident_context`; 4 barrier categorical + 3 numeric are labeled `barrier`. The API and dashboard use this to distinguish barrier-specific signals from incident context signals.
- **Serialization:** `TreeExplainer` holds C++ weak references and cannot be pickled. It is recreated at `BarrierPredictor.__init__()` from the saved model + background array. Never serialize `TreeExplainer` directly.
- **API output:** `POST /predict` returns `model1_shap` and `model2_shap` as lists of `{feature, value, category}` objects, sorted by absolute contribution in the dashboard's SHAP waterfall chart.

**Degradation factors:** PIF SHAP values are mapped to process safety display names via `configs/mappings/pif_to_degradation.yaml` and surfaced in the `/predict` response as `degradation_factors`.

---

## PIF Ablation Study

Comparison of full 18-feature model vs. non-PIF baseline (6 categorical + 3 numeric). Source: `data/models/evaluation/pif_ablation_report.json`.

### Model 1 (barrier failure)

| Features | F1 mean | F1 std | MCC mean | MCC std |
|----------|---------|--------|----------|---------|
| Full (18 features) | 0.885 | ±0.008 | 0.615 | ±0.028 |
| Non-PIF (6 features) | 0.884 | ±0.010 | 0.613 | ±0.030 |
| **PIF impact** | **neutral** | — | — | — |

### Model 2 (human factor sensitivity)

| Features | F1 mean | F1 std | MCC mean | MCC std |
|----------|---------|--------|----------|---------|
| Full (18 features) | 0.696 | ±0.029 | 0.525 | ±0.031 |
| Non-PIF (6 features) | 0.658 | ±0.040 | 0.459 | ±0.047 |
| **PIF impact** | **improved** | — | — | — |

**Interpretation:** PIFs are neutral for predicting whether a barrier failed (Model 1 is driven mainly by barrier characteristics), but materially improve human factor sensitivity prediction (Model 2). This validates including PIFs as features despite their incident-level broadcast nature.

> Advisory only: the ablation uses the same GroupKFold splits on the same data for direct comparability.

---

## RAG Retrieval

**Corpus:** 526 incidents, 3,253 barrier controls, 25 barrier families (subset of 739 canonical — filtered to incidents with RAG-quality barrier text).
**Embedding model:** `all-mpnet-base-v2` (768-dim, sentence-transformers).
**Index:** FAISS `IndexFlatIP` (inner product on L2-normalized vectors = cosine similarity).

### Benchmark Results (50-query evaluation)

| Metric | Baseline (bi-encoder only) | With CrossEncoder reranker |
|--------|---------------------------|---------------------------|
| Top-1 Hit Rate | 0.30 | 0.30 |
| Top-5 Hit Rate | 0.56 | 0.56 |
| Top-10 Hit Rate | 0.62 | 0.60 |
| MRR | 0.40 | 0.42 |

The cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`) is optional and disabled by default. The recall bottleneck at the retrieval stage dominates — improving the bi-encoder or growing the corpus has more impact than reranking.

**Confidence gate:** `barrier_sim_score ≥ 0.25` (cosine similarity). Below this threshold the `/explain` endpoint returns "No matching incidents found." without calling the LLM. The `rrf_score` is rank-based and has no natural threshold; always use `barrier_sim_score` for the gate.

### Retrieval Pipeline

1. **Metadata filter** — optional filter by `barrier_family` or `barrier_failed_human`
2. **Barrier FAISS search** — top-50 by cosine similarity
3. **Incident FAISS search** — top-20 by cosine similarity
4. **Intersection** — keep barrier results whose parent incident also appeared in the incident results
5. **RRF ranking** — `score = 1/(60 + r_barrier) + 1/(60 + r_incident)` — final top-10 returned

See `docs/rag_experiment_history.md` for full research context and experiment history.
