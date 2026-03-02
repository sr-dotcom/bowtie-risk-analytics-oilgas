# Bowtie Risk Analytics

## What This Is

A Python pipeline and Streamlit dashboard for analyzing oil & gas incidents using Bowtie risk methodology. Ingests incident narratives from CSB, BSEE, PHMSA, and TSB public databases, extracts risk factors and barriers via LLM, calculates barrier coverage metrics, and visualizes findings. Currently scoped to "Loss of Containment" scenarios.

## Core Value

Reliable, validated extraction of incident data into canonical V2.3 schema — everything downstream (analytics, dashboard, exports) depends on this being correct and consistent.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Multi-source ingestion pipeline (CSB, BSEE, PHMSA, TSB) with PDF download and text extraction
- ✓ LLM-driven structured extraction with policy-driven model ladder (haiku → sonnet)
- ✓ V2.3 canonical schema with Pydantic v2 validation
- ✓ V2.2 → V2.3 schema conversion (`normalize_v23_payload`)
- ✓ Manifest-based resumability across all pipeline stages
- ✓ Barrier coverage calculation and gap identification (pure functions)
- ✓ Fleet-level metric aggregation
- ✓ Combined flat CSV exports (incidents + controls)
- ✓ corpus_v1: 147 extracted incidents (100 BSEE + 48 CSB, minus 1 scanned-image skip)
- ✓ 325+ passing tests

### Active

<!-- Current scope. Building toward these. -->

- [ ] Fix BOM encoding inconsistency (utf-8 vs utf-8-sig) across all incident JSON reads
- [ ] Create shared `read_incident_json()` helper to centralize encoding handling
- [ ] Remove V2.2 backward-compatibility aliases (IncidentV2_2, validate_incident_v2_2)
- [ ] Rename legacy prompt template from `incident_v2_2_template.json` to `incident_v2_3_template.json`
- [ ] Unify all code references to use canonical V2.3 names
- [ ] Add test coverage for V2.2 → V2.3 migration round-trip on real data patterns
- [ ] Add test coverage for source agency inference logic
- [ ] Add test coverage for CSV manifest serialization round-trip
- [ ] Add test coverage for LLM response parsing edge cases

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Error handling refactoring (bare except clauses) — works, not causing issues yet
- Performance optimization (rglob scanning, sync I/O, manifest merge) — not a bottleneck at current scale
- CI/CD setup — future milestone
- Dashboard overhaul — future milestone
- Corpus scaling / new sources — future milestone
- Incident deduplication — future milestone

## Context

- corpus_v1 has 147 incidents in V2.2 schema; V2.3 is canonical going forward
- BOM encoding bug in `build_combined_exports.py` (lines 158, 221) reads with utf-8 instead of utf-8-sig
- V2.2 aliases (`IncidentV2_2 = IncidentV23`, `validate_incident_v2_2 = validate_incident_v23`) create naming confusion
- Prompt template file still named `incident_v2_2_template.json` despite containing V2.3 schema
- Test gaps flagged in `.planning/codebase/CONCERNS.md`: migration round-trip, source agency inference, manifest round-trip, parsing edge cases

## Constraints

- **Tech stack**: Python 3.10+, Pydantic v2, pytest — no new dependencies for this milestone
- **Backward compat**: Existing 325+ tests must continue to pass throughout
- **Data safety**: No changes to stored corpus_v1 JSON files — only code changes

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Shared `read_incident_json()` helper | Centralizes utf-8-sig encoding to prevent recurring BOM bugs | — Pending |
| Remove V2.2 aliases entirely | One canonical name per model/validator eliminates confusion | — Pending |
| Rename prompt template file | Filename should match schema version it contains | — Pending |

## Current Milestone: v1.0 Stabilization

**Goal:** Harden the foundation — fix encoding bugs, unify V2.3 naming, close test coverage gaps.

**Target features:**
- Encoding consistency (BOM/utf-8-sig everywhere)
- Schema naming cleanup (remove V2.2 aliases, rename template)
- Test coverage for flagged gaps (migration, agency inference, manifests, parsing)

---
*Last updated: 2026-03-01 after milestone v1.0 initialization*
