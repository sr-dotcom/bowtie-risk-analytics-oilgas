# Codebase Concerns

**Analysis Date:** 2025-02-27

## Tech Debt

**Schema Version Duplication:**
- Issue: Backwards-compatibility aliases create naming confusion and maintenance burden
- Files: `src/models/incident_v23.py` (line 429: `IncidentV2_2 = IncidentV23`), `src/validation/incident_validator.py` (line 28: `validate_incident_v2_2 = validate_incident_v23`)
- Impact: Developers may inadvertently use the wrong name; future code cleanup requires finding and updating all alias references
- Fix approach: Remove aliases once fully migrated; update all references to use canonical names (IncidentV23, validate_incident_v23)

**Legacy Prompt Template Path:**
- Issue: Default schema path references obsolete v2.2 filename despite schema being v2.3
- Files: `src/prompts/loader.py` (line 8: `incident_v2_2_template.json`)
- Impact: Misleading file naming creates confusion during maintenance; path mismatch between schema version and filename
- Fix approach: Rename template file to `incident_v2_3_template.json` and update default path reference

**Bare except Clauses in Error Recovery:**
- Issue: Multiple bare `except:` and `except Exception:` blocks swallow unexpected errors silently
- Files: `src/ingestion/structured.py` (lines 307, 347, 358), `src/ingestion/loader.py` (line 56), `src/ingestion/sources/csb.py` (lines 42-43), `src/ingestion/sources/phmsa_ingest.py` (line 89)
- Impact: Debugging difficult when unexpected errors occur; unpredictable fallback behavior; errors logged at WARNING level only
- Fix approach: Use specific exception types; log stack traces at ERROR level for unexpected failures; preserve context for debugging

## Known Bugs

**Truncated LLM Responses Not Detected Consistently:**
- Symptoms: Long incident texts may produce incomplete JSON when LLM hits max_tokens
- Files: `src/corpus/extract.py` (line 152: "response incomplete"), `src/llm/anthropic_provider.py` (line 92: `stop_reason` tracking)
- Trigger: Incidents with very long narratives (>50k chars) when text_limit not applied
- Workaround: Use `--text-limit` parameter in corpus-extract; monitor provider `last_meta['stop_reason']` for "max_tokens"
- Root cause: JSON truncation produces incomplete objects that fail parsing; no automatic requery with shorter text

**Source Agency Resolution Race Condition:**
- Symptoms: Duplicate or conflicting source_agency values when multiple inference tiers apply
- Files: `src/analytics/build_combined_exports.py` (lines 92-137: four-tier resolve_source_agency logic)
- Trigger: Incidents with both doc_type keywords AND URL domain clues from different sources
- Example: File with "BSEE" in doc_type but "csb.gov" in URL → returns BSEE only
- Workaround: No workaround; tier 2 (doc_type) wins over tier 3 (URL domain); can create incorrect agency assignments if doc_type field is corrupted

**CSV Manifest Parsing Fragile:**
- Symptoms: Boolean string conversion and datetime parsing depend on exact string formatting
- Files: `src/ingestion/manifests.py` (lines 64-65, 73-78), `src/ingestion/structured.py` (lines 48-62)
- Trigger: Manual edits of manifest CSV or unexpected locale changes; `datetime.fromisoformat()` fails on non-ISO strings
- Risk: Pipeline breaks silently if manifest rows have malformed boolean strings ("True" vs "true" case-sensitive) or dates not in ISO-8601 format

## Security Considerations

**API Key Handling:**
- Risk: ANTHROPIC_API_KEY passed as plain env var with no encryption at rest
- Files: `src/llm/anthropic_provider.py` (lines 39-43)
- Current mitigation: Provider requires env var to be set; raises RuntimeError if missing
- Recommendations: Use secure credential store (AWS Secrets Manager, HashiCorp Vault) for production; rotate API keys regularly; audit API call logs

**BOM Encoding Requirement Not Enforced:**
- Risk: V2.3 JSON files must be read with `encoding="utf-8-sig"` due to BOM, but this is inconsistently applied
- Files: `src/pipeline.py` (line 328: correct), `src/ingestion/structured.py` (line 437: correct), `src/analytics/build_combined_exports.py` (lines 158, 221: INCORRECT — uses utf-8)
- Impact: Reading BOM-prefixed files with utf-8 causes JSON decode failures or invisible character issues
- Recommendations: Create read helper function that always uses utf-8-sig; apply consistently across all incident JSON reads

**External API Dependency — No Rate Limiting Strategy:**
- Risk: CSB and BSEE scrapers issue unthrottled HTTP requests
- Files: `src/ingestion/sources/csb.py`, `src/ingestion/sources/bsee.py`, `src/ingestion/sources/bsee_discover.py` (line 126: basic retry)
- Impact: Risk of IP blocking or service disruption if discovery runs on many incidents
- Recommendations: Add configurable delay between requests; implement exponential backoff for 429 status; add request rate limiting

## Performance Bottlenecks

**Recursive File Scanning for Large Corpuses:**
- Problem: `rglob("*.json")` on large incidents directories scans entire tree without pagination
- Files: `src/ingestion/structured.py` (line 192: txt_files), `src/analytics/build_combined_exports.py` (lines 156, 219)
- Impact: Memory usage and latency grow linearly with file count; corpus_v1 (147 JSONs) is manageable but corpus_v2+ could degrade
- Improvement path: Batch process files in chunks; add streaming CSV writer for large exports; consider directory sharding strategy

**Synchronous I/O in Extraction Loop:**
- Problem: `extract_structured()` processes files sequentially with blocking I/O on LLM calls
- Files: `src/ingestion/structured.py` (lines 200-360)
- Impact: Extraction of 100 PDFs takes hours (one API call per file, no parallelism); pipeline throughput ~5-10 files/hour
- Improvement path: Use asyncio or ThreadPoolExecutor for concurrent API calls; batch prompts if API supports it; implement worker pool pattern

**Manifest Merge Operations O(n²):**
- Problem: Deduplication in merge operations iterates all existing + new rows to build dict keys
- Files: `src/ingestion/manifests.py` (lines 334-352), `src/ingestion/structured.py` (lines 71-81)
- Impact: Negligible for small manifests (<1000 rows) but degrades with corpus growth
- Improvement path: Pre-sort rows by key; use set-based deduplication; or switch to SQLite-backed manifest

**Validation Errors Aggregated as Strings:**
- Problem: Validation errors capped at 5 errors and truncated to 60 chars per message for storage
- Files: `src/ingestion/structured.py` (lines 339, 394)
- Impact: Debugging difficult when incidents have many validation failures; full error context lost
- Improvement path: Write full errors to separate error report files; use structured error format (JSON)

## Fragile Areas

**LLM Response Parsing with Three Fallback Strategies:**
- Files: `src/ingestion/structured.py` (lines 102-142)
- Why fragile: Brace-matching fallback assumes valid JSON will eventually appear in response; no upper bound on search attempts
- Risk: Malformed LLM responses could trigger infinite loops or memory exhaustion if response is very large with mismatched braces
- Safe modification: Always validate response length before parsing; set maximum search depth; add timeout
- Test coverage: Unit tests exist for `_parse_llm_json()` but no fuzz testing for pathological inputs

**Silent Fallback on Model Validation Failure:**
- Files: `src/ingestion/structured.py` (lines 344-349: exception caught and falls back to raw payload)
- Why fragile: If IncidentV23.model_validate() fails but json.loads() succeeds, output is unvalidated dict
- Risk: Invalid incident data written to disk without validation; downstream queries may fail silently
- Safe modification: Log at ERROR if fallback triggered; track as extraction failure in manifest; never silently output unvalidated data

**Source Agency Inference with Multiple Fallbacks:**
- Files: `src/analytics/build_combined_exports.py` (lines 74-137)
- Why fragile: Five-tier priority system means agency assignment depends on which tier matches first; no deduplication if multiple tiers match
- Risk: Refactoring any tier (e.g., improving doc_type rules) could silently change agency assignments for existing incidents
- Safe modification: Pre-compute agency for all incidents during extraction, not at export time; store agency in incident JSON; only infer for legacy data

**Hardcoded Provider Bucket Name Inference:**
- Files: `src/analytics/build_combined_exports.py` (line 175: `jf.parent.name`)
- Why fragile: Assumes all incidents live under exactly one directory level with meaningful bucket name
- Risk: If directory structure changes (e.g., deeper nesting), bucket names become incorrect or unhelpful ("json" or "data")
- Safe modification: Store provider_bucket in incident JSON metadata during extraction; remove assumption about directory structure

## Scaling Limits

**Manifest Files Grow Linearly with Incident Count:**
- Current capacity: corpus_v1 manifest ~5KB (147 rows); corpus_v2+ could reach 10-50MB (10k-100k rows)
- Limit: CSV parsing/writing becomes slow at >10k rows; in-memory deduplication (merge operations) becomes memory-bound
- Scaling path: Switch to SQLite backend for manifests; add index on (incident_id, provider); implement pagination for CSV export

**JSON File Storage Without Deduplication:**
- Current capacity: 147 incidents × 3 providers = 441 JSON files (~50MB); larger corpus would be ~500MB-2GB
- Limit: Directory traversal with rglob becomes slow at >5000 files; filesystem performance degradation
- Scaling path: Use subdirectory sharding (e.g., by first 2 chars of incident_id); implement object store (S3); add compression

**LLM API Cost Per Incident:**
- Current capacity: ~$0.45 per 20 PDFs at 50k char limit (haiku-4-5 @ 8192 tokens)
- Limit: Full corpus_v1 (147 PDFs) = ~$3.31; scaling to 5k PDFs = ~$112 per run
- Scaling path: Implement incremental extraction (skip already-extracted); use prompt caching if API supports; optimize text truncation threshold

## Dependencies at Risk

**Pydantic v2 Major Version Dependency:**
- Risk: Tight coupling to Pydantic v2 API; ConfigDict, model_validate, model_dump methods are v2-specific
- Impact: Incompatible with Pydantic v1 or v3; migration burden if upstream introduces breaking changes
- Files: `src/models/incident_v23.py`, all validation code
- Migration plan: Pin Pydantic to ^2.0 in requirements.txt; monitor upstream releases; plan deprecation timeline for v2 before v3 adoption

**pdfplumber for PDF Text Extraction:**
- Risk: Single hard dependency; no fallback if library breaks or is abandoned
- Impact: PDF extraction becomes impossible if pdfplumber has unfixed bugs or becomes unmaintained
- Alternative options: pypdf, pdfminer.six, pymupdf (fitz)
- Recommendation: Add abstraction layer for PDF extraction; implement fallback to alternative library if primary fails

**Anthropic-Only LLM Provider Lock-In:**
- Risk: Code assumes Claude-only provider despite having registry for multiple providers
- Files: `src/corpus/extract.py` (line 54-55: "Only anthropic provider allowed")
- Impact: Cannot use other LLM providers even if needed for cost optimization or compliance
- Migration plan: Remove provider lock-in; make provider selection configurable; test with multiple providers

## Missing Critical Features

**No Data Validation Between Pipeline Stages:**
- Problem: Output of one stage (e.g., extract-structured) is not validated before being consumed by next stage (e.g., convert-schema)
- Blocks: Cannot catch corruption early; errors surface far downstream
- Recommendation: Add validation gates between stages; write schema-check output; validate during process step

**No Incident Deduplication Mechanism:**
- Problem: Same incident from different sources (e.g., CSB and BSEE) creates duplicate entries
- Blocks: Analytics queries must manually deduplicate; flat exports contain duplicates
- Recommendation: Add fuzzy matching on incident_id + date_occurred; implement merge workflow

**No Audit Trail for Data Lineage:**
- Problem: Cannot trace which version of which model processed a given incident
- Blocks: Reproducibility issues; cannot rollback specific incidents if extraction improves
- Recommendation: Store extraction metadata (model version, prompt version, extraction date) in incident JSON

## Test Coverage Gaps

**LLM Response Parsing Edge Cases:**
- What's not tested: Extremely large responses (>100MB); nested braces with special characters; responses with null bytes; truncated Unicode
- Files: `src/ingestion/structured.py` (lines 102-142)
- Risk: Unexpected LLM response format could cause silent failures or crashes
- Priority: High (critical extraction path)
- Approach: Add fuzz testing with pathological inputs; test with real truncated responses from API

**Schema Migration (V2.2 → V2.3) Round-Trip:**
- What's not tested: Full end-to-end migration of real corpus_v1 data through normalize_v23_payload(); no validation that migrated data passes IncidentV23 validation
- Files: `src/ingestion/normalize.py`, `src/pipeline.py` (convert-schema command)
- Risk: Silent data loss or transformation bugs during migration; downstream analytics use corrupted data
- Priority: High (production impact on corpus_v1 migration)
- Approach: Add integration tests that load legacy JSON, normalize, validate, and compare specific fields

**Source Agency Inference on Real Data:**
- What's not tested: Actual inference logic on real CSB/BSEE/PHMSA/TSB incidents; no golden dataset
- Files: `src/analytics/build_combined_exports.py` (lines 74-137)
- Risk: Incorrect agency assignments propagate into flat exports; analytics reports wrong source attribution
- Priority: Medium (data quality impact)
- Approach: Create test fixtures with incidents from each source; verify agency inference; add regression test

**CSV Manifest Serialization Round-Trip:**
- What's not tested: Loading manifest, modifying, saving, reloading; no validation of string-to-type conversions
- Files: `src/ingestion/manifests.py` (load/save functions)
- Risk: Boolean and datetime parsing failures due to locale or format changes
- Priority: Medium (pipeline stability)
- Approach: Test round-trip with various boolean formats and datetime representations

**Concurrent Extraction with Manifest Merge:**
- What's not tested: Two concurrent extract_structured() runs with manifest merging; potential data loss from race conditions
- Files: `src/ingestion/structured.py` (merge_structured_manifests)
- Risk: Manifest rows lost if two runs try to upsert same incident_id at same time
- Priority: Medium (concurrent operations not officially supported, but risky)
- Approach: Add file locking for manifest writes; make merge operations atomic

---

*Concerns audit: 2025-02-27*
