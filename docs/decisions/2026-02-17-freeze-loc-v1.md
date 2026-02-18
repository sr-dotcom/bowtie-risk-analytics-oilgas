# ADR-004: Freeze LOC_v1 as Extraction-Aware Keyword-Tier Scoring

**Date:** 2026-02-17
**Status:** Accepted

## Context

The pipeline needs a stable, documented definition for Loss of Containment (LOC) classification before downstream analytics and labeling can proceed. The current implementation in `src/nlp/loc_scoring.py` uses deterministic keyword matching with an extraction-awareness gate. This definition has been validated against CSB reports and is working reliably for the MVP scope.

A cosine-similarity approach was also evaluated but showed low recall on this corpus and was set aside.

## Decision

Freeze the current LOC scoring logic as **LOC_v1**. The frozen definition includes:

1. **Three keyword tiers:** primary (8 terms), secondary (2 terms), hazardous context (10 terms).
2. **Extraction gate:** documents with `extraction_status != "OK"` are labelled `EXTRACTION_FAILED`, never `LOC=False`.
3. **Flag rule:** `(primary >= 1 AND hazardous >= 1) OR (secondary >= 1 AND hazardous >= 2)`.
4. **Audit score:** `loc_score = (primary * 2) + (secondary * 1) + hazardous` — informational only, not authoritative.

The full definition is documented in `docs/loc_definition_v1.md`.

## Consequences

- **Stability:** Downstream consumers (flatten, analytics, dashboard) can rely on a fixed LOC definition.
- **Versioning:** Any changes to keyword lists, flag rule, or extraction gate require a new version (LOC_v2) and a new ADR.
- **Limitation:** Keyword matching may miss LOC incidents described with unusual phrasing. This is accepted for MVP; a future version could incorporate NLP models if recall needs improvement.
