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

- [ ] Fix BOM encoding inconsistency — shared `read_incident_json()` helper with utf-8-sig
- [ ] Remove V2.2 backward-compatibility aliases — one canonical name per model/validator
- [ ] Rename legacy prompt template to match V2.3 schema version
- [ ] Replace bare except clauses with specific exception types and proper ERROR-level logging
- [ ] Clean module boundaries — consistent naming, remove dead code and legacy artifacts
- [ ] Add light inter-stage validation (file exists, JSON parseable) between pipeline stages
- [ ] Close test coverage gaps: migration round-trip, source agency inference, manifest round-trip, LLM parsing edge cases

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Performance optimization (sync I/O, rglob, manifest merge) — not a bottleneck at 147 incidents
- Incident deduplication — not blocking current workflows
- CI/CD setup (GitHub Actions) — future milestone
- Dashboard overhaul — separate milestone after stabilization
- Corpus scaling / new sources — needs stable foundation first
- Data lineage / audit trail — future concern when corpus grows
- Provider lock-in removal — only Anthropic in use; not blocking
- Full inter-stage schema validation — light checks sufficient for now

## Context

- corpus_v1 has 147 incidents in V2.2 schema; V2.3 is canonical going forward
- BOM encoding bug in `build_combined_exports.py` (lines 158, 221) reads with utf-8 instead of utf-8-sig
- V2.2 aliases (`IncidentV2_2 = IncidentV23`, `validate_incident_v2_2 = validate_incident_v23`) create naming confusion
- Prompt template file still named `incident_v2_2_template.json` despite containing V2.3 schema
- Bare except clauses in `structured.py`, `loader.py`, `csb.py`, `phmsa_ingest.py` swallow unexpected errors
- Fragile areas: LLM response parsing (3-strategy fallback), silent model validation fallback, source agency inference (5-tier priority)
- Test gaps flagged in `.planning/codebase/CONCERNS.md`: migration round-trip, source agency inference, manifest round-trip, parsing edge cases
- Codebase mapped via `/gsd:map-codebase` on 2026-02-27

## Constraints

- **Tech stack**: Python 3.10+, Pydantic v2, pytest — no new dependencies for this milestone
- **Backward compat**: Existing 325+ tests must continue to pass throughout
- **Data safety**: No changes to stored corpus_v1 JSON files — only code changes
- **No perf changes**: Sequential I/O and file scanning patterns stay as-is

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Shared `read_incident_json()` helper | Centralizes utf-8-sig encoding to prevent recurring BOM bugs | — Pending |
| Remove V2.2 aliases entirely | One canonical name per model/validator eliminates confusion | — Pending |
| Rename prompt template file | Filename should match schema version it contains | — Pending |
| Specific exception types | Replace bare excepts for debuggability without changing behavior | — Pending |
| Light inter-stage validation | Basic sanity checks catch corruption early without over-engineering | — Pending |

## Current Milestone: v1.0 Repo-Architecture-Stabilization

**Goal:** Make the codebase production-ready, architecturally clean, and well-tested — a foundation that's easy to extend with confidence.

**Target features:**
- Encoding consistency (BOM/utf-8-sig everywhere via shared helper)
- Schema naming cleanup (remove V2.2 aliases, rename template)
- Error handling hardening (specific exceptions, proper logging)
- Architecture cleanup (module boundaries, dead code removal)
- Inter-stage validation (light pipeline sanity checks)
- Test coverage for all flagged gaps

---
*Last updated: 2026-03-01 after milestone v1.0 initialization*
