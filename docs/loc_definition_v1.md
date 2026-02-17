# LOC_v1: Loss of Containment Scoring Definition

**Version:** 1.0 (Frozen)
**Date:** 2026-02-17
**Implementation:** `src/nlp/loc_scoring.py`

## Overview

LOC_v1 is a deterministic, keyword-tier scoring system that classifies incident documents as LOC-relevant or not. It is extraction-aware: documents that failed text extraction are labelled `EXTRACTION_FAILED` rather than `LOC=False`, avoiding silent false negatives.

## Keyword Tiers

### Primary LOC Terms (weight: 2)

Direct indicators of loss of containment:

| Term |
|------|
| release |
| spill |
| leak |
| loss of containment |
| discharge |
| escape |
| rupture |
| blowout |

### Secondary LOC Terms (weight: 1)

Consequence indicators that suggest LOC when paired with hazardous context:

| Term |
|------|
| explosion |
| fire |

### Hazardous Context Terms (weight: 1)

Domain terms that establish a hazardous-material context:

| Term |
|------|
| chemical |
| ammonia |
| gas |
| vapor |
| hydrogen |
| oil |
| refinery |
| toxic |
| explosion |
| fire |

## Extraction Gate

Before scoring, check the document's extraction status:

```
IF extraction_status != "OK" THEN
    final_label = "EXTRACTION_FAILED"
    (do not score; do not label as LOC=False)
```

This is implemented in `run_with_extraction_manifest()`. Documents with missing text files are also routed to `EXTRACTION_FAILED` with `fail_reason=TEXT_FILE_MISSING`.

## LOC Flag Rule (Frozen)

A document is flagged as LOC-relevant when:

```
loc_flag = (primary_count >= 1 AND hazardous_count >= 1)
           OR
           (secondary_count >= 1 AND hazardous_count >= 2)
```

- **Clause 1:** At least one primary LOC term AND at least one hazardous context term.
- **Clause 2:** At least one secondary term AND at least two hazardous context terms (higher bar because secondary terms are less specific).

Matching uses word-boundary, case-insensitive regex (`\b<term>\b`, `re.IGNORECASE`).

## LOC Score (Audit-Only)

```
loc_score = (primary_count * 2) + (secondary_count * 1) + hazardous_count
```

The numeric `loc_score` is computed for audit and debugging purposes. It is **not authoritative** for classification; only `loc_flag` determines the LOC label.

## Final Label Mapping

| Condition | `final_label` |
|-----------|---------------|
| `extraction_status != "OK"` | `EXTRACTION_FAILED` |
| `loc_flag == True` | `TRUE` |
| `loc_flag == False` | `FALSE` |

## Rationale

- **Reproducible:** Fully deterministic, no model weights or thresholds to drift.
- **Extraction-aware:** Failed extractions are surfaced explicitly rather than silently labelled as non-LOC.
- **Avoids silent false negatives:** The extraction gate prevents bad text from producing misleading `FALSE` labels.
- **Cosine similarity not used:** Evaluated during development but showed low recall on this corpus. Keyword-tier approach selected for MVP.

## Frozen Status

This definition is frozen as of 2026-02-17. Any changes to the keyword lists, flag rule, or extraction gate logic require a new version (LOC_v2) and a corresponding ADR.
