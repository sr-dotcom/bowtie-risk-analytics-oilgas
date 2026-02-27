# Coding Conventions

**Analysis Date:** 2025-02-27

## Naming Patterns

**Files:**
- `snake_case` for all Python files
- Test files: `test_*.py` (not `*_test.py`)
- Modules match functionality: `engine.py` for analytics engine, `structured.py` for LLM extraction orchestration
- Feature modules in feature-named directories: `extraction/`, `ingestion/`, `analytics/`, `llm/`, `nlp/`, `corpus/`, `models/`, `validation/`

**Functions:**
- `snake_case` for all function names
- Private helper functions prefix with `_`: `_calc_coverage()` in `src/analytics/engine.py`, `_try_pymupdf()` in `src/extraction/extractor.py`
- Class methods and static methods follow `snake_case`
- Example patterns from codebase:
  - `calculate_barrier_coverage()` — public analytics function
  - `load_bowtie()` — data loading function
  - `_parse_llm_json()` — internal JSON parsing with fallback strategies
  - `extract_text()` — public text extraction function

**Variables:**
- `snake_case` for local and module-level variables
- Constants: `UPPERCASE` with underscores: `_DEFAULT_MODEL`, `_API_URL`, `_RETRYABLE_STATUS_CODES` in `src/llm/anthropic_provider.py`
- List/dict containers use descriptive plural nouns: `incident_barriers`, `prevented_barriers`, `merged_manifests`
- Type-hinted counters and accumulators: `total`, `present_count`, `attempts`, `depth`
- Temporary loop variables: `i`, `row`, `file_path` (descriptive, not single letters for complex iterations)

**Types:**
- Use modern `list[...]` and `dict[...]` (Python 3.9+) instead of `List[...]` and `Dict[...]` where possible
- Both styles coexist in codebase; `List`, `Dict` from `typing` still used in some older modules like `src/analytics/engine.py`
- Optional fields use `Optional[T]` or `T | None`
- Literal types for enums: `Literal["prevention", "mitigation"]` in `src/models/bowtie.py` for barrier types
- Type hints required on all function signatures (enforced)

**Pydantic Models:**
- Class names use `PascalCase`: `Incident`, `Bowtie`, `Barrier`, `IncidentV23`, `SourceInfo`, `ContextInfo`, `EventInfo`
- Field names use `snake_case`: `incident_id`, `top_event`, `date_published`, `barrier_status`
- ConfigDict pattern for validation settings: `ConfigDict(strict=False)` standard in v2.3 models for flexible parsing

## Code Style

**Formatting:**
- No linter or formatter (black, flake8, isort) configured
- Follows PEP 8 conventions loosely (implied by codebase)
- Line length: variable, some lines exceed 100 characters
- Indentation: 4 spaces (not tabs)
- Imports: 2-3 blank lines between major import sections not enforced (mixed style in codebase)

**Linting:**
- Not configured; no `.eslintrc`, `.flake8`, or `pyproject.toml [tool.flake8]` section
- Code review is manual/ad-hoc

## Import Organization

**Order:**
1. Standard library imports (`os`, `json`, `logging`, `re`, `csv`, `sys`, `time`, `argparse`, `datetime`, `pathlib`, `abc`, `dataclasses`, `unicodedata`, `statistics`)
2. Third-party imports (`requests`, `pydantic`, `pandas`, `yaml`, `pytest`, `beautifulsoup4`)
3. Local application imports (`from src...`)

**Pattern from `src/pipeline.py`:**
```python
import argparse
import json
import logging
from pathlib import Path

from typing import List, Optional

import requests

from src.ingestion.loader import load_incident_from_text
from src.models.incident import Incident
```

**Path Aliases:**
- No path aliases configured; all imports use fully qualified `from src.X import Y` style
- Module root is project root; `src/` is always explicit

**Relative vs Absolute:**
- Always use absolute imports from project root: `from src.models.incident import Incident` (not relative imports with dots)

## Error Handling

**Patterns:**

1. **Validation-first approach:** Pydantic models used for runtime validation; errors caught at model instantiation
   - `from pydantic import ValidationError`
   - Example in `src/validation/incident_validator.py`: returns tuple `(bool, list[str])` with error messages
   - Function: `validate_incident_v23(payload: dict) -> tuple[bool, list[str]]`

2. **Explicit exceptions over silent failures:**
   - Raise `RuntimeError` for configuration errors: `raise RuntimeError("AnthropicProvider requires ANTHROPIC_API_KEY...")`
   - Raise `json.JSONDecodeError` when JSON parsing fails (after 3 fallback strategies in `_parse_llm_json()`)
   - Raise validation errors from Pydantic naturally

3. **Graceful degradation in extraction pipelines:**
   - Multi-pass extraction with fallback: try `pymupdf` → `pdfminer` → `ocr`
   - Return `ExtractionResult` dataclass with error field: `ExtractionResult(text="", error="Non-existent PDF")`
   - Log errors but continue: `logger.error(f"Failed to load Bowtie: {e}"); return None`

4. **Optional return values:**
   - Use `Optional[T]` for functions that may return nothing: `load_bowtie() -> Optional[Bowtie]`
   - Pydantic Field defaults prevent null pointer issues: `Field(default="unknown")`, `Field(default_factory=list)`

5. **Manifest-based error tracking:**
   - Manifest rows track extraction state: `extracted: bool`, `valid: bool`, `error: Optional[str]`, `validation_errors: Optional[str]`
   - CSV manifests persist progress across runs (resumability pattern)

## Logging

**Framework:** Python `logging` module (stdlib)

**Setup pattern from `src/pipeline.py`:**
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
```

**Usage patterns:**
- `logger.info()` — progress updates, successful operations
- `logger.warning()` — missing optional files, skipped steps
- `logger.error()` — failures that prevent operation

**Locations:**
- `src/llm/anthropic_provider.py`: logs API calls, retries, errors
- `src/pipeline.py`: logs pipeline stage entry and completion
- `src/extraction/extractor.py`: logs fallback extractor attempts
- `src/ingestion/structured.py`: logs manifest loading, manifest row counts

No log files configured; logs to stdout/stderr via basicConfig.

## Comments

**When to Comment:**
- **Docstrings required** on all public functions and classes (enforced)
- **Inline comments** for complex logic: brace-matching in `_parse_llm_json()`, composite keys in manifest merging
- **No comments for obvious code** (e.g., `x = x + 1` doesn't need explanation)
- **Explain "why" not "what"**: Comments clarify intent/design decisions

**Docstring Format:**
Google-style docstrings with Args, Returns, Raises sections

**Example from `src/analytics/engine.py`:**
```python
def calculate_barrier_coverage(incident: Incident, bowtie: Bowtie) -> Dict[str, float]:
    """
    Calculates the percentage of Bowtie barriers present in the incident.

    Args:
        incident: The incident data with identified barriers.
        bowtie: The reference Bowtie diagram.

    Returns:
        Dictionary with coverage metrics (0.0 to 1.0).
    """
```

**JSDoc/TSDoc:**
Not applicable (Python codebase).

**Field Documentation:**
Pydantic Field descriptions used for schema documentation:
```python
class Barrier(BaseModel):
    id: str = Field(..., description="Unique identifier for the barrier")
    type: Literal["prevention", "mitigation"] = Field(..., description="Type of barrier (left or right side)")
```

## Function Design

**Size:**
- Typical function body: 20-50 lines
- Long functions: up to 100+ lines in orchestration code (e.g., `run_extraction_qc()`)
- Private helpers extracted when logic is complex: `_calc_coverage()` in `engine.py`

**Parameters:**
- Prefer named parameters over positional (enforced by type hints)
- Limit to 4-5 parameters; use dataclass/model for >5 related params
- Example: `extract_structured(text_dir: Path, out_dir: Path, provider: LLMProvider, provider_name: str)`

**Return Values:**
- Single return types preferred: `-> str`, `-> dict`, `-> int`
- Tuple returns for multi-value results (without dataclass): `-> tuple[bool, list[str]]` (validation results)
- Dataclass returns for structured multi-field results: `ExtractionResult` with text, extractor_used, page_count, error
- Optional returns when success is not guaranteed: `-> Optional[Bowtie]`, `-> Optional[Path]`

**Pure Functions:**
- Analytics functions are pure: `calculate_barrier_coverage()` and `identify_gaps()` take immutable inputs, return new data
- No side effects except logging
- Manifest I/O functions explicitly named for side effects: `save_structured_manifest()`, `load_structured_manifest()`

## Module Design

**Exports:**
- No explicit `__all__` in most modules
- All public classes/functions are importable
- Private symbols prefixed with `_` are conventionally private (not enforced)

**Barrel Files:**
- No barrel `__init__.py` files that re-export; each `__init__.py` is empty or minimal
- Direct imports from specific modules encouraged: `from src.analytics.engine import calculate_barrier_coverage`

**Separation of Concerns:**
- `models/` — Pydantic data models (incident, bowtie, source, validation schemas)
- `analytics/` — Barrier coverage, aggregation, flattening, exports
- `ingestion/` — PDF download, text extraction, structured LLM extraction, manifest tracking
- `extraction/` — Multi-pass PDF extraction with quality gating
- `llm/` — LLM provider abstractions (base ABC, implementations, registry, model policy)
- `validation/` — Schema validation (incident_validator.py)
- `nlp/` — Scoring and NLP utilities (LOC scoring)
- `corpus/` — Corpus-specific utilities (manifest building, cleaning, extraction)
- `app/` — Streamlit dashboard entry point

**Dependency Direction:**
- Data models (`models/`) depend only on pydantic and stdlib
- Utilities (`analytics/`, `nlp/`) depend on models and stdlib
- Pipeline orchestration (`pipeline.py`, `ingestion/`) depends on everything above
- LLM providers (`llm/`) have minimal dependencies (requests, pydantic, stdlib)

---

*Convention analysis: 2025-02-27*
