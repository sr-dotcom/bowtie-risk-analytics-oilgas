# Agent Team Plan: PDF → LLM JSON → Analytics Pipeline

## Overview

Four teammates, each owning separate directories/modules, building the end-to-end pipeline:
**PDFs → extracted text → LLM JSON (incident schema) → flatten to barrier-level rows → analytics**

All work builds on existing CLI (`src/pipeline.py`), models (`src/models/`), and tests (`tests/`).

---

## Teammate 1: Schema Engineer

**Objective:** Create a canonical, machine-usable incident schema under `assets/schema/` and a Pydantic-based validator utility.

### Files to create/touch
- `assets/schema/incident_v2.schema.json` — JSON Schema for LLM-output validation
- `assets/schema/incident_template.json` — Example/template JSON showing expected structure with field descriptions
- `assets/schema/README.md` — Brief field-level documentation
- `src/validation/__init__.py`
- `src/validation/schema_validator.py` — Validator utility: loads JSON Schema, validates dicts, returns structured errors
- `tests/test_schema_validator.py` — Unit tests for validator

### Schema design (based on existing models + team v2.2/v2.3 conventions)
The schema will cover:
- `incident_id`, `source` (csb/bsee), `title`, `date_occurred`, `location`
- `facility_type`, `incident_type`, `severity`
- `narrative_summary` (LLM-generated concise summary)
- `hazard`, `top_event`
- `causes[]` — each with `id`, `name`, `description`, `mentioned` (bool)
- `consequences[]` — each with `id`, `name`, `severity`, `mentioned` (bool)
- `prevention_barriers[]` — each with `id`, `name`, `description`, `effectiveness` (high/medium/low/unknown), `mentioned` (bool)
- `mitigation_barriers[]` — same structure
- `injuries`, `fatalities`, `environmental_impact`
- `confidence_score` (LLM self-assessment 0.0–1.0)
- `extraction_notes` (free text for LLM caveats)

### Definition of done
- JSON Schema validates correct documents and rejects malformed ones
- Template JSON passes validation
- `schema_validator.validate(doc)` returns `(is_valid: bool, errors: list[str])`
- All tests pass

### How to test
```bash
pytest tests/test_schema_validator.py -v
```

---

## Teammate 2: Prompt Engineer

**Objective:** Create a production-quality extraction prompt under `assets/prompts/` and a helper to assemble it at runtime.

### Files to create/touch
- `assets/prompts/extract_incident.md` — The system/user prompt template with placeholders
- `assets/prompts/README.md` — Prompt design rationale and usage notes
- `src/prompts/__init__.py`
- `src/prompts/loader.py` — Helper: loads prompt template, injects schema template + incident text, returns final prompt string
- `tests/test_prompt_loader.py` — Unit tests

### Prompt design principles
- Output must be **JSON only** (no markdown fences, no commentary)
- `*_mentioned` fields: barrier/cause/consequence `mentioned` must be `true` only if explicitly discussed in the text
- Applicability rules: if information is not available, use `null` not invented values
- Confidence score: LLM must self-rate extraction confidence
- Schema template is injected verbatim so LLM sees exact expected structure
- Prompt sections: Role → Task → Schema → Rules → Input Text → Output format

### `loader.py` API
```python
def load_prompt(
    incident_text: str,
    schema_template_path: str = "assets/schema/incident_template.json",
    prompt_template_path: str = "assets/prompts/extract_incident.md",
) -> str:
    """Returns fully assembled prompt string ready to send to LLM."""
```

### Definition of done
- Prompt template is well-structured with clear sections
- `load_prompt("some text")` returns a string containing both the schema and the incident text
- Template placeholders (`{{SCHEMA_TEMPLATE}}`, `{{INCIDENT_TEXT}}`) are fully resolved
- Tests cover: loading, placeholder injection, missing file errors

### How to test
```bash
pytest tests/test_prompt_loader.py -v
```

---

## Teammate 3: Pipeline Engineer

**Objective:** Add `extract-structured` CLI command and LLM provider interface to the pipeline.

### Files to create/touch
- `src/llm/__init__.py`
- `src/llm/base.py` — Abstract `LLMProvider` interface
- `src/llm/stub.py` — `StubProvider` returning a fixed valid JSON (for testing without API keys)
- `src/pipeline.py` — Add `extract-structured` subcommand (extend existing argparse)
- `src/ingestion/structured.py` — Orchestrator: reads text files, calls prompt loader + LLM + validator, writes JSON
- `tests/test_extract_structured.py` — Unit tests for the new command
- `tests/test_llm_provider.py` — Tests for provider interface and stub

### `extract-structured` command design
```bash
python -m src.pipeline extract-structured \
    --text-dir data/interim/text \
    --out-dir data/structured/incidents \
    --provider stub \
    --manifest data/manifests/structured_manifest.csv
```

Flow:
1. Glob `text_dir` for `*.txt` files
2. For each file: load text → assemble prompt (via `src/prompts/loader`) → call LLM provider → validate output (via `src/validation/schema_validator`) → write JSON to `out_dir`
3. Track progress in a structured manifest CSV (incident_id, text_path, json_path, provider, valid, error_msg, timestamp)

### LLM Provider interface
```python
class LLMProvider(ABC):
    @abstractmethod
    def extract(self, prompt: str) -> str:
        """Send prompt, return raw LLM response string (should be JSON)."""

class StubProvider(LLMProvider):
    """Returns a pre-defined valid JSON for testing."""
```

### Definition of done
- `python -m src.pipeline extract-structured --provider stub` runs end-to-end with stub
- Manifest CSV tracks processing state
- Invalid LLM output is caught by validator and logged (not crash)
- Existing CLI commands (`acquire`, `extract-text`, `process`) still work
- All existing tests pass + new tests pass

### How to test
```bash
# Existing tests still pass
pytest tests/ -v

# New tests
pytest tests/test_extract_structured.py tests/test_llm_provider.py -v

# Integration (with stub)
python -m src.pipeline extract-structured --provider stub --help
```

---

## Teammate 4: Analytics Engineer

**Objective:** Flatten structured incidents into barrier-level rows and provide baseline analysis.

### Files to create/touch
- `src/analytics/flatten.py` — Flattener: reads incident JSONs → produces barrier-level DataFrame
- `src/analytics/baseline.py` — Baseline analysis: counts, association mining placeholder, logistic regression placeholder
- `scripts/run_analytics.py` — CLI script to run flatten + baseline in sequence
- `tests/test_flatten.py` — Unit tests for flattening logic
- `tests/test_baseline.py` — Unit tests for baseline analytics

### Flattener output schema (`data/derived/barriers.csv`)
Each row = one barrier instance from one incident:
| Column | Type | Description |
|--------|------|-------------|
| incident_id | str | Source incident ID |
| barrier_id | str | Barrier control ID (e.g., B-01) |
| barrier_name | str | Barrier name |
| barrier_type | str | prevention / mitigation |
| effectiveness | str | high/medium/low/unknown |
| mentioned | bool | Was barrier mentioned in narrative? |
| linked_threat_ids | str | Comma-separated threat IDs |
| linked_consequence_ids | str | Comma-separated consequence IDs |
| incident_date | str | Date of incident |
| facility_type | str | Facility type |
| severity | str | Incident severity |
| injuries | int | Number of injuries |
| fatalities | int | Number of fatalities |

### Baseline analysis (`data/derived/`)
- `barrier_counts.json` — Frequency of each barrier, mention rates
- `association_rules.json` — Co-occurrence of barriers (placeholder: which barriers tend to appear/fail together)
- `baseline_model_summary.json` — Logistic regression placeholder (barrier mentioned ~ severity/injuries)

### Definition of done
- `flatten.py` reads from `data/structured/incidents/*.json` and writes `data/derived/barriers.csv`
- Baseline script runs without errors and produces summary JSONs
- Works with both real data and stub-generated data
- All tests pass

### How to test
```bash
# Unit tests
pytest tests/test_flatten.py tests/test_baseline.py -v

# End-to-end
python scripts/run_analytics.py --structured-dir data/structured/incidents --out-dir data/derived
```

---

## Directory Ownership (No Conflicts)

| Teammate | Owned directories/files |
|----------|------------------------|
| Schema Engineer | `assets/schema/`, `src/validation/`, `tests/test_schema_validator.py` |
| Prompt Engineer | `assets/prompts/`, `src/prompts/`, `tests/test_prompt_loader.py` |
| Pipeline Engineer | `src/llm/`, `src/ingestion/structured.py`, `src/pipeline.py` (extend), `tests/test_extract_structured.py`, `tests/test_llm_provider.py` |
| Analytics Engineer | `src/analytics/flatten.py`, `src/analytics/baseline.py`, `scripts/`, `tests/test_flatten.py`, `tests/test_baseline.py` |

**Shared dependency chain:** Schema Engineer → Prompt Engineer → Pipeline Engineer → Analytics Engineer
(But all can be built in parallel since interfaces are defined above.)

---

## Execution order
1. **All four teammates produce plans** (this document) — awaiting approval
2. After approval, teammates 1 & 2 execute in parallel (no deps on each other)
3. Teammate 3 executes (depends on 1 & 2 outputs)
4. Teammate 4 executes (depends on 3 output format, but can use stub data)

In practice, all four can work in parallel since the interfaces are defined here and stub/sample data bridges any gaps.
