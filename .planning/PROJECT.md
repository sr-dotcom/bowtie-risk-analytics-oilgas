# Bowtie Risk Analytics

## What This Is

A Python pipeline and Streamlit dashboard for analyzing oil & gas incidents using Bowtie risk methodology. Ingests incident narratives from public databases (CSB, BSEE, PHMSA, TSB), extracts risk factors and barriers via LLM, calculates barrier coverage metrics, and visualizes findings. Currently scoped to "Loss of Containment" scenarios.

## Core Value

Reliable, validated incident data flowing from raw PDFs through structured extraction to analytics — every stage producing trustworthy output that downstream consumers can depend on.

## Current Milestone: v1.0 Repo-Architecture-Stabilization

**Goal:** Stabilize the full pipeline — models, ingestion, extraction, analytics, exports — before building new dashboard and analytics features.

**Target features:**
- Remove all V2.2 legacy code (aliases, backwards-compat shims, misnamed files)
- Fix silent failures across the pipeline (bare excepts, unvalidated fallbacks)
- Enforce BOM encoding consistency (utf-8-sig everywhere V2.3 JSON is read)
- Clean naming across all modules (schema versions, function names, file names)
- Ensure all tests pass and cover critical paths

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- V2.3 schema models and extraction pipeline (147 incidents extracted)
- Multi-source ingestion (CSB, BSEE, PHMSA, TSB adapters)
- Combined flat exports (flat_incidents_combined.csv, controls_combined.csv)
- Policy-driven LLM model ladder (haiku-first with escalation)
- Manifest-based pipeline resumability

### Active

<!-- Current scope. Building toward these. -->

- [ ] Remove V2.2 legacy aliases and backwards-compat code
- [ ] Fix silent failure patterns across pipeline
- [ ] Enforce consistent BOM encoding for V2.3 JSON reads
- [ ] Clean naming inconsistencies (files, functions, models)
- [ ] Test coverage for critical paths (schema migration, agency inference, LLM parsing)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Handoff data integration — separate workflow, not part of stabilization
- New analytics features — stabilization first, features after
- Dashboard rebuild — depends on stable analytics layer
- Scaling optimizations — premature until feature direction is clear
- Multi-provider LLM support — Claude-only is intentional

## Context

- corpus_v1 complete: 147 incidents (100 BSEE + 48 CSB), V2.2 schema JSONs
- Codebase map produced 2026-02-27 with architecture, concerns, and test analysis
- Concerns audit identified: schema naming confusion, silent failures, BOM inconsistency, fragile source agency inference, test coverage gaps
- Two previous milestone attempts deleted — starting fresh with clearer scope
- Preparing for: dashboard rebuild + analytics expansion as next milestone

## Constraints

- **Tech stack**: Python 3.10+, Pydantic v2, Streamlit — no changes
- **Schema**: V2.3 is canonical — all V2.2 code can be removed
- **Data**: Existing 147 incidents must remain loadable after changes
- **Tests**: 325 existing tests must continue to pass

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Remove V2.2 completely | V2.3 is canonical, aliases cause confusion | — Pending |
| Full pipeline scope | Analytics path depends on clean ingestion path | — Pending |
| Ignore handoff data | Separate workflow, would expand scope | — Pending |

---
*Last updated: 2026-03-01 after milestone v1.0 initialization*
