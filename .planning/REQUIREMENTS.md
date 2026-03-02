# Requirements: Bowtie Risk Analytics

**Defined:** 2026-03-01
**Core Value:** Reliable, validated incident data flowing through every pipeline stage

## v1 Requirements

Requirements for milestone v1.0 Repo-Architecture-Stabilization. Each maps to roadmap phases.

### Legacy Cleanup

- [ ] **LEGC-01**: All V2.2 backward-compat aliases removed (`IncidentV2_2`, `validate_incident_v2_2`)
- [ ] **LEGC-02**: Prompt template file renamed from `incident_v2_2_template.json` to `incident_v2_3_template.json`
- [ ] **LEGC-03**: All imports and references updated to use canonical V2.3 names
- [ ] **LEGC-04**: CLAUDE.md updated to remove references to V2.2 models/files that no longer exist

### Error Handling

- [ ] **ERRH-01**: All bare `except:` / `except Exception:` in `src/` replaced with specific exception types
- [ ] **ERRH-02**: Unexpected errors logged at ERROR level with stack traces (not WARNING)
- [ ] **ERRH-03**: Silent validation fallback in `structured.py` logs at ERROR and tracks failure in manifest

### Encoding

- [ ] **ENCD-01**: `build_combined_exports.py` reads V2.3 JSON with `utf-8-sig` encoding
- [ ] **ENCD-02**: `flatten.py` reads V2.3 JSON with `utf-8-sig` encoding
- [ ] **ENCD-03**: Shared helper function created for reading V2.3 incident JSON files consistently

### Source Agency

- [ ] **AGCY-01**: `resolve_source_agency()` logic simplified and documented with explicit tier priority
- [ ] **AGCY-02**: Test coverage expanded for all doc_type variants and edge cases

### Test Coverage

- [ ] **TEST-01**: Schema V2.3 validation round-trip tests (load sample JSON, validate, re-serialize, re-validate)
- [ ] **TEST-02**: LLM JSON parsing edge case tests (truncated JSON, nested braces, empty response)
- [ ] **TEST-03**: BOM encoding tests (read V2.3 JSON with and without BOM prefix)
- [ ] **TEST-04**: All existing 325 tests continue to pass after changes

## Future Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### Scaling

- **SCAL-01**: Manifest storage migrated from CSV to SQLite
- **SCAL-02**: JSON file storage uses subdirectory sharding for large corpora
- **SCAL-03**: Concurrent/async extraction for throughput improvement

### Data Quality

- **DQAL-01**: Inter-stage validation gates between pipeline steps
- **DQAL-02**: Incident deduplication across sources (CSB, BSEE, PHMSA, TSB)
- **DQAL-03**: Audit trail for data lineage (model version, prompt version, extraction date)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Handoff data integration | Separate workflow, would expand scope |
| New analytics features | Stabilization first, features after |
| Dashboard rebuild | Depends on stable analytics layer |
| Multi-provider LLM support | Claude-only is intentional design choice |
| Performance optimizations | Premature until feature direction is clear |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LEGC-01 | — | Pending |
| LEGC-02 | — | Pending |
| LEGC-03 | — | Pending |
| LEGC-04 | — | Pending |
| ERRH-01 | — | Pending |
| ERRH-02 | — | Pending |
| ERRH-03 | — | Pending |
| ENCD-01 | — | Pending |
| ENCD-02 | — | Pending |
| ENCD-03 | — | Pending |
| AGCY-01 | — | Pending |
| AGCY-02 | — | Pending |
| TEST-01 | — | Pending |
| TEST-02 | — | Pending |
| TEST-03 | — | Pending |
| TEST-04 | — | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 0
- Unmapped: 16 ⚠️

---
*Requirements defined: 2026-03-01*
*Last updated: 2026-03-01 after initial definition*
