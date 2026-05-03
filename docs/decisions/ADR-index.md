# Architecture Decisions

## ADR-001: Pydantic v2 for Data Models
**Date:** 2026-02-01
**Status:** Accepted

**Context:**
The data pipeline involves a lot of nested JSON structures (incidents, bowtie definitions). I need to ensure data quality before running analytics.

**Decision:**
Use Pydantic v2 for all data models.

**Reasoning:**
- Strict type checking catches data issues early.
- Serialization/deserialization is built-in.
- It validates the schema for both the input (raw narratives) and output (analytics results).


## ADR-002: Streamlit for MVP — SUPERSEDED by D007
**Date:** 2026-02-01
**Status:** Superseded (by D007, 2026-04 — see DECISIONS.md)

> **Note:** This decision was reversed in D007 when the architecture pivoted to a self-hosted Ubuntu mini-PC + Docker + Cloudflare Tunnel stack hosting FastAPI + Next.js. Streamlit Community Cloud could not host the two-process backend + frontend stack the project ultimately required. ADR-002 is preserved for project-evolution provenance; do not infer current architecture from it.

**Context (historical):**
I need a way to visualize the pipeline outputs (coverage, gap analysis, risk scores) quickly. The main goal is a working demo for the project presentation, not a production-grade web app.

**Decision (superseded):**
I'll use Streamlit. It's Python-native and lets me build the dashboard alongside the analytics code without context switching to JS/React.

**Trade-offs (historical):**
- **Pros:** Fast to build, runs locally easily, good enough for the demo.
- **Cons:** limited UI customization compared to React, but that's acceptable for this scope.

## ADR-003: Standardize Pipeline Outputs Under data/processed
**Date:** 2026-02-04
**Status:** Accepted

**Context:**
The Streamlit app and downstream analytics need a stable, predictable location for pipeline outputs (fleet metrics and per-incident JSON).

**Decision:**
All pipeline output artifacts will be written to `data/processed/` (e.g., `fleet_metrics.json`, `INC-*.json`), and the Streamlit app will read from this directory.

**Consequences:**
- Simplifies end-to-end runs and demos (one known output location)
- Reduces path mismatches between pipeline and UI
- Makes it easy to swap ingestion sources later (PDFs) while keeping downstream stable