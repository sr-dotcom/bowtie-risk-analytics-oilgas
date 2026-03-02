# Requirements: Bowtie Risk Analytics

**Defined:** 2026-03-01
**Core Value:** Reliable, validated extraction of incident data into canonical V2.3 schema

## v1.0 Requirements

Requirements for Repo-Architecture-Stabilization milestone. Each maps to roadmap phases.

### Encoding

- [ ] **ENC-01**: All incident JSON reads use utf-8-sig encoding (no BOM parsing failures)
- [ ] **ENC-02**: Shared `read_incident_json()` helper exists and is used by all JSON-reading code paths
- [ ] **ENC-03**: build_combined_exports.py uses utf-8-sig for both incident and controls JSON reads

### Schema Cleanup

- [ ] **SCH-01**: V2.2 backward-compat alias `IncidentV2_2 = IncidentV23` removed from incident_v23.py
- [ ] **SCH-02**: V2.2 backward-compat alias `validate_incident_v2_2 = validate_incident_v23` removed from incident_validator.py
- [ ] **SCH-03**: All code references updated to use canonical V2.3 names (IncidentV23, validate_incident_v23)
- [ ] **SCH-04**: Prompt template file renamed from `incident_v2_2_template.json` to `incident_v2_3_template.json`
- [ ] **SCH-05**: Default template path in `src/prompts/loader.py` updated to reference v2_3 filename

### Error Handling

- [ ] **ERR-01**: Bare except clauses in `src/ingestion/structured.py` replaced with specific exception types
- [ ] **ERR-02**: Bare except clauses in `src/ingestion/loader.py` replaced with specific exception types
- [ ] **ERR-03**: Bare except clauses in `src/ingestion/sources/csb.py` replaced with specific exception types
- [ ] **ERR-04**: Bare except clauses in `src/ingestion/sources/phmsa_ingest.py` replaced with specific exception types
- [ ] **ERR-05**: All replaced exception handlers log at ERROR level with stack traces for unexpected failures

### Architecture

- [ ] **ARCH-01**: Inconsistent naming cleaned up across module boundaries
- [ ] **ARCH-02**: Unused code and dead imports removed
- [ ] **ARCH-03**: Duplicated logic consolidated (e.g., JSON reading patterns, manifest key computation)

### Validation

- [ ] **VAL-01**: Pipeline stages verify output files exist before next stage consumes them
- [ ] **VAL-02**: Pipeline stages verify output is valid JSON before next stage consumes them

### Test Coverage

- [ ] **TST-01**: V2.2 → V2.3 migration round-trip tests verify field transformations (side, barrier_status, line_of_defense, IDs)
- [ ] **TST-02**: Source agency inference tests cover CSB, BSEE, PHMSA, TSB with realistic fixtures
- [ ] **TST-03**: CSV manifest serialization round-trip tests verify boolean and datetime parsing
- [ ] **TST-04**: LLM response parsing edge case tests cover truncated JSON, nested braces, markdown fences, empty responses

## Future Requirements

Deferred to next milestone.

### Performance

- **PERF-01**: Batch file scanning for large directories
- **PERF-02**: Async/parallel LLM extraction calls
- **PERF-03**: Optimized manifest merge operations

### CI/CD

- **CI-01**: GitHub Actions workflow running pytest on push
- **CI-02**: Automated linting and type checking

## Out of Scope

| Feature | Reason |
|---------|--------|
| Dashboard overhaul | Separate milestone — stabilization first |
| Corpus scaling / new sources | Needs stable foundation before expanding |
| Incident deduplication | Not blocking current workflows |
| Data lineage / audit trail | Future concern when corpus grows |
| Provider lock-in removal | Only Anthropic in use; not blocking |
| Full inter-stage schema validation | Light checks sufficient — avoid over-engineering |
| Performance optimization | Not a bottleneck at current 147-incident scale |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENC-01 | — | Pending |
| ENC-02 | — | Pending |
| ENC-03 | — | Pending |
| SCH-01 | — | Pending |
| SCH-02 | — | Pending |
| SCH-03 | — | Pending |
| SCH-04 | — | Pending |
| SCH-05 | — | Pending |
| ERR-01 | — | Pending |
| ERR-02 | — | Pending |
| ERR-03 | — | Pending |
| ERR-04 | — | Pending |
| ERR-05 | — | Pending |
| ARCH-01 | — | Pending |
| ARCH-02 | — | Pending |
| ARCH-03 | — | Pending |
| VAL-01 | — | Pending |
| VAL-02 | — | Pending |
| TST-01 | — | Pending |
| TST-02 | — | Pending |
| TST-03 | — | Pending |
| TST-04 | — | Pending |

**Coverage:**
- v1.0 requirements: 22 total
- Mapped to phases: 0
- Unmapped: 22 ⚠️

---
*Requirements defined: 2026-03-01*
*Last updated: 2026-03-01 after initial definition*
