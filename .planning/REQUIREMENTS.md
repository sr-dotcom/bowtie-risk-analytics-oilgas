# Requirements: Bowtie Risk Analytics

**Defined:** 2026-03-01
**Core Value:** Reliable, validated extraction of incident data into canonical V2.3 schema

## v1.0 Requirements

Requirements for stabilization milestone. Each maps to roadmap phases.

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

### Test Coverage

- [ ] **TST-01**: V2.2 → V2.3 migration round-trip tests verify field transformations (side, barrier_status, line_of_defense, IDs)
- [ ] **TST-02**: Source agency inference tests cover CSB, BSEE, PHMSA, TSB with realistic fixtures
- [ ] **TST-03**: CSV manifest serialization round-trip tests verify boolean and datetime parsing
- [ ] **TST-04**: LLM response parsing edge case tests cover truncated JSON, nested braces, markdown fences, empty responses

## Future Requirements

Deferred to next milestone. Tracked but not in current roadmap.

### Error Handling

- **ERR-01**: Replace bare except clauses with specific exception types
- **ERR-02**: Log stack traces at ERROR level for unexpected failures

### Performance

- **PERF-01**: Batch file scanning for large directories
- **PERF-02**: Async/parallel LLM extraction calls

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

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENC-01 | Phase 1 | Pending |
| ENC-02 | Phase 1 | Pending |
| ENC-03 | Phase 1 | Pending |
| SCH-01 | Phase 2 | Pending |
| SCH-02 | Phase 2 | Pending |
| SCH-03 | Phase 2 | Pending |
| SCH-04 | Phase 2 | Pending |
| SCH-05 | Phase 2 | Pending |
| TST-01 | Phase 3 | Pending |
| TST-02 | Phase 3 | Pending |
| TST-03 | Phase 3 | Pending |
| TST-04 | Phase 3 | Pending |

**Coverage:**
- v1.0 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

---
*Requirements defined: 2026-03-01*
*Last updated: 2026-03-01 — traceability mapped after roadmap creation*
