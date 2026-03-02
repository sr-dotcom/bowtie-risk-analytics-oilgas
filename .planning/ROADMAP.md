# Roadmap: Bowtie Risk Analytics — v1.0 Stabilization

## Overview

Three phases that harden the foundation before expanding the corpus. Phase 1 fixes the concrete encoding bug by introducing a shared helper. Phase 2 removes the V2.2 naming layer entirely, leaving one canonical name per concept. Phase 3 fills the test gaps that were flagged during codebase mapping, giving confidence that the fixes in Phases 1 and 2 are correct and won't regress.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Encoding Fix** - Create shared `read_incident_json()` helper and apply it everywhere
- [ ] **Phase 2: Schema Cleanup** - Remove V2.2 aliases, rename prompt template, unify all references to V2.3 names
- [ ] **Phase 3: Test Coverage** - Fill flagged test gaps: migration round-trip, agency inference, manifests, parsing edge cases

## Phase Details

### Phase 1: Encoding Fix
**Goal**: All incident JSON reads consistently use utf-8-sig so BOM bytes never surface as data corruption
**Depends on**: Nothing (first phase)
**Requirements**: ENC-01, ENC-02, ENC-03
**Success Criteria** (what must be TRUE):
  1. A single `read_incident_json()` function exists in a shared module and is the only place utf-8-sig is specified
  2. Every code path that opens an incident JSON file calls `read_incident_json()` instead of raw `open()`
  3. `build_combined_exports.py` reads both incident and controls JSON through `read_incident_json()` with no direct utf-8 opens remaining
  4. Running the combined-exports pipeline on corpus_v1 produces no BOM-related parse errors
**Plans**: TBD

### Phase 2: Schema Cleanup
**Goal**: The codebase has exactly one name for each V2.3 concept — no V2.2 aliases, no mismatched filenames
**Depends on**: Phase 1
**Requirements**: SCH-01, SCH-02, SCH-03, SCH-04, SCH-05
**Success Criteria** (what must be TRUE):
  1. `IncidentV2_2` and `validate_incident_v2_2` identifiers do not exist anywhere in the codebase
  2. All import sites use `IncidentV23` and `validate_incident_v23` directly
  3. The prompt template file on disk is named `incident_v2_3_template.json` and the old name is gone
  4. `src/prompts/loader.py` default path references `incident_v2_3_template.json` with no fallback to the old name
  5. All 325+ existing tests continue to pass after the rename and alias removal
**Plans**: TBD

### Phase 3: Test Coverage
**Goal**: The four flagged test gaps are closed, giving automated confidence that encoding, schema, migration, and parsing are correct
**Depends on**: Phase 2
**Requirements**: TST-01, TST-02, TST-03, TST-04
**Success Criteria** (what must be TRUE):
  1. Tests exist that exercise V2.2 → V2.3 field transformations (side, barrier_status, line_of_defense, IDs) and assert correct output values
  2. Tests exist that exercise source agency inference for CSB, BSEE, PHMSA, and TSB using realistic fixture data
  3. Tests exist that serialize a manifest row to CSV and deserialize it back, asserting booleans and datetimes round-trip without loss
  4. Tests exist that exercise LLM response parsing for truncated JSON, nested braces, markdown fences, and empty responses
  5. `pytest` passes with all new tests included and zero regressions

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Encoding Fix | 0/TBD | Not started | - |
| 2. Schema Cleanup | 0/TBD | Not started | - |
| 3. Test Coverage | 0/TBD | Not started | - |
