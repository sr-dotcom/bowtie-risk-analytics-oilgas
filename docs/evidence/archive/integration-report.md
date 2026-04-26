# Integration Report: event_barrier_normalizationv2.py

**Date:** 2026-03-03
**Source:** Fork `pqhunter15/bowtie-risk-analytics-oilgas` → `scripts/association_mining/event_barrier_normalizationv2.py`
**Target:** Canonical repo `sr-dotcom/bowtie-risk-analytics-oilgas`

---

## 1. Fork Script Analysis

### What It Is

A **Colab notebook export** (~3200 lines) that implements a 4-quadrant barrier normalization pipeline:

| Quadrant | Side | Type | Family Assignment Function | Output Column |
|----------|------|------|---------------------------|---------------|
| 1 | Prevention | Administrative | `assign_admin_family()` | `admin_family` |
| 2 | Prevention | Engineering | `assign_eng_family()` | `eng_family` |
| 3 | Mitigation | Administrative | `assign_mit_admin_family()` | `mit_admin_family` |
| 4 | Mitigation | Engineering | `assign_mit_eng_family()` | `mit_eng_family` |

### Input Files

| File | Source | Schema |
|------|--------|--------|
| `flat_incidents_combinedV3.csv` | Google Drive hardcoded path | V2.3 flat columns (`incident__event__top_event`, `incident__event__incident_type`, `incident_id`) |
| `controls_combinedV3.csv` | Google Drive hardcoded path | V2.3 flat controls (`name`, `side`, `barrier_role`, `barrier_type`, `barrier_status`, `barrier_failed`, etc.) |

### Output File

- **`normalized_dfV1.csv`** — Written to Colab working directory (line 3213)

### Output Schema (COMMON_COLS)

```
incident_id, control_id, control_name_raw, control_name_norm,
barrier_role_raw, barrier_role_norm, family_match_text_norm,
barrier_level, barrier_type, barrier_family,
line_of_defense, lod_basis, barrier_status, barrier_failed,
human_contribution_value, barrier_failed_human, confidence,
supporting_text_count, source_agency, provider_bucket, json_path
```

### External Dependencies

| Dependency | Type | Status in Canonical |
|------------|------|---------------------|
| `google.colab.drive` | Colab-only | **MUST REMOVE** |
| `sentence_transformers` (all-MiniLM-L6-v2) | ML model | **NOT in requirements.txt** — used for LOC filtering + embedding fallback |
| `sklearn.metrics.pairwise.cosine_similarity` | ML utility | Already available via scikit-learn (not in requirements.txt) |
| `rapidfuzz` | Fuzzy matching | **NOT in requirements.txt** — used for barrier name clustering |
| `networkx` | Graph clustering | **NOT in requirements.txt** — used for barrier name clustering |
| `nltk.stem.snowball.SnowballStemmer` | NLP | **NOT in requirements.txt** — used for token stemming in rules |
| `pandas`, `numpy`, `re`, `hashlib` | Standard | Already available |

### Schema Assumptions

The script reads **V2.3 flat column names** from `controls_combined.csv`:
- `name` → control name
- `side` → "prevention" / "mitigation" (V2.3 uses "left"/"right" — **MISMATCH RISK**)
- `barrier_role`, `barrier_type`, `barrier_status`, `barrier_failed`
- `human_contribution_value`, `barrier_failed_human`
- `confidence`, `supporting_text_count`
- `line_of_defense`, `lod_basis`
- `source_agency`, `provider_bucket`, `json_path`
- `incident_id`, `control_id`

**Critical finding:** The script filters on `side == "prevention"` and `side == "mitigation"`, but the canonical V2.3 schema uses `side: "left"` / `side: "right"`. The fork's input CSVs appear to use human-readable labels ("prevention"/"mitigation") rather than canonical V2.3 values.

---

## 2. Canonical Repo Current State

### What Already Exists

| Component | Canonical Location | Status |
|-----------|-------------------|--------|
| JSON aggregation | `scripts/association_mining/jsonaggregation.py` | ✓ EXISTS — clean CLI, no hardcoded paths |
| JSON flattening | `scripts/association_mining/jsonflattening.py` | ✓ EXISTS — clean CLI, reads aggregated JSON |
| Smoke test | `scripts/association_mining/smoke_test.py` | ✓ EXISTS — validates aggregation + flattening |
| Event barrier normalization | — | ✗ MISSING |
| `src/analytics/flatten.py` | `src/analytics/flatten.py` | ✓ EXISTS — alternative flatten (from JSON, not aggregated) |
| `src/analytics/build_combined_exports.py` | `src/analytics/build_combined_exports.py` | ✓ EXISTS — produces `flat_incidents_combined.csv` + `controls_combined.csv` |
| `src/analytics/control_coverage_v0.py` | `src/analytics/control_coverage_v0.py` | ✓ EXISTS — coverage metrics from flat controls |

### Pipeline Gap

The canonical backbone currently produces:

```
Incident JSON → build_combined_exports.py → flat_incidents_combined.csv + controls_combined.csv
                                              ↓
                                         control_coverage_v0.py → coverage/gaps CSVs
```

What's missing:

```
controls_combined.csv → [LOC filtering] → [barrier normalization] → normalized_df.csv
```

---

## 3. What the Fork Script Actually Does (Logic Decomposition)

### Phase A: LOC Event Filtering (lines 1–177)
- Loads `flat_incidents_combined.csv`
- Uses `sentence_transformers` to embed `top_event + incident_type`
- Compares against LOC anchor phrases (positive) and non-LOC anchors (negative)
- Filters to incidents with `loc_pos > 0.45` and `loc_margin > 0.10`
- Joins filtered incidents with controls → `controls_loc_df`

**Note:** The canonical repo already has `src/nlp/loc_scoring.py` doing keyword-based LOC scoring. The fork uses embedding-based scoring — a different approach.

### Phase B: Text Normalization (lines 220–324)
- Abbreviation expansion (PSV→pressure safety valve, etc.)
- Punctuation removal, whitespace collapse
- Role normalization (mitigation→mitigate, etc.)
- Stop phrase removal

### Phase C: Barrier Name Clustering (lines 388–652)
- Token-based blocking (head nouns)
- Fuzzy matching via `rapidfuzz` (token_set_ratio ≥ 90)
- Semantic matching via embeddings (cosine ≥ 0.84)
- Graph clustering via `networkx` connected components
- Canonical name selection (most frequent raw name in cluster)

**Assessment:** This is exploratory/research code for understanding the data. The clustering results are NOT used in the final output. The script explicitly says (line 726): "we will not use this to further transform barrier names."

### Phase D: Family Assignment — 4 Quadrants (lines 727–3113)
Each quadrant follows the same pattern:
1. Filter controls by `side` + `barrier_type`
2. Normalize text (abbreviation expansion + whitespace)
3. **Rule-based classification** — ordered token-contains checks against stemmed tokens
4. **Embedding fallback** — encode with sentence-transformers, compare to family anchor centroids
5. Assign family label

**Family taxonomies (domain knowledge):**

| Quadrant | # Families | Key Families |
|----------|-----------|--------------|
| Prevention Admin | 10 | training, procedures, change_management, monitoring, regulatory_and_permits, hazard_analysis_prework_checks, operating_controls_and_limits, communication, planning, maintenance |
| Prevention Engineering | 5 | overpressurization_gas_discharge_gas_isolation, fluid_discharge_and_containment, prevention_of_ignition, detection_monitoring_alarms, mechanical_integrity |
| Mitigation Admin | 13 | emergency_shutdown_isolation_depressurization, detection_monitoring_surveillance, active_intervention_to_stop_release, fire_response_firewatch_ignition_control, evacuation_muster_shelter_exclusion_access_control, medical_response_and_evacuation, environmental_response_cleanup_reporting, incident_command_coordination_and_comms, investigation_corrective_action_post_incident_verification, supervision_staffing_oversight, emergency_preparedness_planning_training_drills, ppe_and_respiratory_protection, permits_controlled_work_during_response |
| Mitigation Engineering | 17 | gas_detection_atmospheric_monitoring, alarms_general_alarm_pa, emergency_shutdown_isolation, emergency_disconnect_eds, well_control_barriers_kill, pressure_relief_blowdown_flare_disposal, ignition_source_control, active_fire_protection_firefighting, passive_fire_blast_protection, control_room_habitability_hvac_pressurization, emergency_power_backup_utilities, spill_containment_environmental_mitigation, chemical_release_scrubbing_neutralization, physical_protection_retention_restraints, emergency_escape_access_rescue_decon, structural_mechanical_integrity_escalation_prevention, remote_monitoring_intervention_subsea, marine_collision_avoidance |

### Phase E: Combine and Export (lines 3145–3213)
- Unifies all 4 quadrants into `all_barriers_df`
- Adds `barrier_level` (prevention/mitigation), `barrier_type` (admin/engineering), `barrier_family`
- Selects COMMON_COLS
- Writes `normalized_dfV1.csv`

---

## 4. Integration Assessment

### What MUST Be Copied

| Item | Reason |
|------|--------|
| Family taxonomy dictionaries (ADMIN_FAMILIES, ENGINEERING_BARRIER_FAMILIES, MIT_ADMIN_FAMILIES, MIT_ENG_FAMILIES) | Core domain knowledge — defines barrier family groupings |
| Abbreviation maps (ABBR_MAP variants) | Domain abbreviation expansion |
| Rule-based family assignment functions (assign_admin_family, assign_eng_family, assign_mit_admin_family, assign_mit_eng_family) | Core classification logic |
| Text normalization functions (normalize_control_name, normalize_for_family) | Preprocessing pipeline |
| COMMON_COLS output schema | Defines normalized_df.csv contract |

### What MUST Be Refactored

| Item | Issue | Fix |
|------|-------|-----|
| Google Colab imports | `from google.colab import drive` | Remove entirely |
| Hardcoded Drive paths | `/content/drive/MyDrive/...` | CLI args with defaults matching canonical paths |
| `side` field values | Script uses "prevention"/"mitigation"; canonical V2.3 uses "left"/"right" | Map at input: `left→prevention`, `right→mitigation` |
| Embedding fallback | Requires `sentence_transformers` + model download at runtime | Make optional; rule-only mode as default |
| LOC filtering | Uses embeddings; canonical has keyword-based `loc_scoring.py` | Decouple: LOC filtering is separate concern, not part of normalization |
| Duplicate function definitions | Functions redefined 2-3 times in notebook flow | Consolidate to single definitions |
| `!pip install` commands | Colab shell commands | Move to requirements.txt |

### What MUST NOT Be Imported

| Item | Reason |
|------|--------|
| Barrier name clustering pipeline (lines 388–720) | Exploratory analysis; explicitly not used in output |
| LOC embedding filtering (Phase A) | Separate concern; canonical has `loc_scoring.py` |
| `display()` / `print()` QA cells | Notebook inspection code |
| Manual overrides (lines 1846, 1851) | Ad-hoc fixes (`other_engineering→mechanical_integrity`, `prevention_of_ignition→overpressurization`) — should be encoded as rules if needed |
| Second-pass admin family reassignment (lines 1277–1308) | Aggressive fallback with min_sim=0.25 — quality questionable |

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **`side` field mismatch** — canonical V2.3 uses "left"/"right", fork expects "prevention"/"mitigation" | HIGH | Add explicit mapping at pipeline entry; validate before processing |
| **New dependencies** — `sentence_transformers`, `rapidfuzz`, `nltk`, `networkx`, `scikit-learn` | HIGH | Make embedding fallback optional; rule-only mode needs only `nltk` (stemmer). Consider replacing stemmer with simple `str.startswith` to avoid nltk dependency entirely |
| **Embedding model download** — `all-MiniLM-L6-v2` downloads ~80MB on first use | MEDIUM | Default to rule-only; embedding mode as explicit opt-in flag |
| **Taxonomy drift** — hardcoded family names become stale as corpus grows | LOW | Taxonomies are domain-constant (O&G safety barrier categories don't change often) |
| **Manual overrides baked in** — two families force-merged in notebook | MEDIUM | Encode as explicit rules or remove; don't silently carry notebook decisions |

---

## 6. Minimal Integration Strategy

### Target Architecture

```
scripts/association_mining/event_barrier_normalization.py   (NEW — clean CLI script)
```

### Proposed Pipeline

```
Incident JSON
  → jsonaggregation.py          (EXISTS — no changes)
  → jsonflattening.py           (EXISTS — no changes)
  → event_barrier_normalization.py  (NEW — from fork, refactored)
  → normalized_df.csv           (OUTPUT)
```

### Implementation Steps

1. **Create `scripts/association_mining/event_barrier_normalization.py`** — clean CLI script with:
   - `argparse` interface (input CSV, output CSV, optional flags)
   - Side mapping: `left→prevention`, `right→mitigation`
   - Text normalization functions (consolidated, no duplicates)
   - All 4 family taxonomy dicts
   - All 4 rule-based assignment functions
   - Embedding fallback **disabled by default** (`--use-embeddings` flag)
   - Combine into COMMON_COLS → write CSV

2. **Dependencies** — minimal approach:
   - Rule-only mode: `pandas`, `re` (already available)
   - Replace NLTK SnowballStemmer with simple substring matching (the `token_contains` function already does this)
   - Optional: `sentence_transformers`, `scikit-learn` for `--use-embeddings`

3. **Update smoke test** to cover normalization step

4. **Do NOT touch**:
   - `src/analytics/` — no changes to existing modules
   - `src/pipeline.py` — no new CLI subcommands (this is a script, not a pipeline stage)
   - LOC filtering — separate concern, not in scope

### Files Changed

| File | Action |
|------|--------|
| `scripts/association_mining/event_barrier_normalization.py` | CREATE — new clean CLI |
| `scripts/association_mining/smoke_test.py` | MODIFY — add normalization validation |
| `requirements.txt` | NO CHANGE for rule-only mode |

---

## 7. Column Contract: normalized_df.csv

| Column | Source | Notes |
|--------|--------|-------|
| `incident_id` | Pass-through from controls CSV | |
| `control_id` | Pass-through | |
| `control_name_raw` | `name` column from input | Original barrier name |
| `control_name_norm` | Computed | Lowercase, abbreviations expanded, punctuation removed |
| `barrier_role_raw` | `barrier_role` from input | |
| `barrier_role_norm` | Computed | Same normalization as control_name |
| `family_match_text_norm` | Computed | `control_name_norm + " " + barrier_role_norm` |
| `barrier_level` | Derived from `side` | prevention (left) / mitigation (right) |
| `barrier_type` | Pass-through | administrative / engineering |
| `barrier_family` | **Computed — core output** | One of ~45 family labels |
| `line_of_defense` | Pass-through | |
| `lod_basis` | Pass-through | |
| `barrier_status` | Pass-through | |
| `barrier_failed` | Pass-through | |
| `human_contribution_value` | Pass-through | |
| `barrier_failed_human` | Pass-through | |
| `confidence` | Pass-through | |
| `supporting_text_count` | Pass-through | |
| `source_agency` | Pass-through | |
| `provider_bucket` | Pass-through | |
| `json_path` | Pass-through | |

---

*Report generated: 2026-03-03*
*Status: Investigation only — no code changes made*
