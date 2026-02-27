# Testing Patterns

**Analysis Date:** 2025-02-27

## Test Framework

**Runner:**
- pytest 7.0.0+
- Config: `pyproject.toml [tool.pytest.ini_options]`

**Assertion Library:**
- Built-in pytest assertions (no external assertion library; uses `assert` keyword)

**Run Commands:**
```bash
pytest                              # Run all tests (5520 lines, 325+ tests across 36 test files)
pytest tests/test_analytics.py      # Run single test file
pytest tests/test_analytics.py::TestAnalytics::test_calculate_barrier_coverage  # Single test function
pytest -v                           # Verbose output (show all test names)
pytest -s                           # Show print/logging output
pytest -x                           # Stop on first failure
pytest tests/test_*.py -k "filter"  # Run tests matching pattern "filter"
```

## Test File Organization

**Location:**
- Co-located in `tests/` directory at project root (not alongside source files)
- Parallel structure to `src/` but all tests in single `tests/` directory

**Naming:**
- Test files: `test_*.py` (e.g., `test_analytics.py`, `test_llm_provider.py`, `test_extraction_extractor.py`)
- Test classes: `Test<FunctionName>` or `Test<FeatureName>` (PascalCase with Test prefix)
- Test functions: `test_<scenario>` (e.g., `test_calculate_barrier_coverage`, `test_stub_returns_valid_json`)

**Structure:**
```
tests/
├── test_analytics.py               # Tests for src/analytics/engine.py
├── test_flatten.py                 # Tests for src/analytics/flatten.py
├── test_anthropic_provider.py      # Tests for src/llm/anthropic_provider.py
├── test_extraction_extractor.py    # Tests for src/extraction/extractor.py
├── test_extract_structured.py      # Tests for src/ingestion/structured.py
├── test_models.py                  # Tests for src/models/
├── test_incident_validator.py      # Tests for src/validation/incident_validator.py
├── fixtures/                       # Not present; test data inline or via factories
└── conftest.py                     # Not present; fixtures defined per test file
```

## Test Structure

**Suite Organization:**
```python
import pytest
from src.models.bowtie import Bowtie, Barrier
from src.models.incident import Incident
from src.analytics.engine import calculate_barrier_coverage, identify_gaps


@pytest.fixture
def sample_bowtie():
    return Bowtie(
        hazard="Hydrocarbon",
        top_event="Loss of Containment",
        threats=[Threat(id="T1", name="Corrosion")],
        consequences=[Consequence(id="C1", name="Fire")],
        barriers=[
            Barrier(id="B1", name="Coating", type="prevention"),
            Barrier(id="B2", name="Sprinkler", type="mitigation")
        ]
    )


@pytest.fixture
def sample_incident():
    return Incident(
        incident_id="INC-1",
        description="Leak due to corrosion. Coating was present.",
        prevention_barriers=["Coating"],
        mitigation_barriers=[]
    )


class TestAnalytics:
    """Test cases for Bowtie analytics engine."""

    def test_calculate_barrier_coverage(self, sample_bowtie, sample_incident):
        """Test calculation of barrier coverage percentages."""
        metrics = calculate_barrier_coverage(sample_incident, sample_bowtie)

        assert metrics["prevention_coverage"] == 1.0
        assert metrics["mitigation_coverage"] == 0.0
        assert metrics["overall_coverage"] == 0.5
```

**Patterns:**
- **Setup:** `@pytest.fixture` functions (not setUp/tearDown methods)
- **Teardown:** Implicit via fixture scope (function-level default); `tempfile.TemporaryDirectory()` used for I/O tests
- **Assertion:** Direct `assert` statements with optional comparison messages: `assert len(gaps) == 1`

## Mocking

**Framework:** `unittest.mock` (stdlib) — `patch`, `MagicMock`, `spec`

**Patterns:**
```python
from unittest.mock import patch, MagicMock
import pytest

def _mock_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = json.dumps(json_data or {})
    resp.json.return_value = json_data or {}
    return resp


class TestAnthropicProviderInit:
    def test_missing_key_raises_runtime_error(self):
        env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                AnthropicProvider(api_key="")
        finally:
            if env_backup is not None:
                os.environ["ANTHROPIC_API_KEY"] = env_backup
```

**Mock HTTP Responses:**
Used in `test_anthropic_provider.py` — mocks `requests.post()` to avoid real API calls:
```python
with patch("requests.post") as mock_post:
    mock_post.return_value = _mock_response(200, {"content": [{"text": "..."}]})
    provider = AnthropicProvider(api_key="test-key")
    result = provider.extract("test prompt")
```

**What to Mock:**
- External APIs (HTTP calls via `requests`)
- File system I/O in unit tests (use `tempfile.TemporaryDirectory()` instead)
- Environment variables (save/restore via `os.environ.pop()` pattern)
- `open()` calls when testing pure logic independent of file I/O

**What NOT to Mock:**
- Pydantic models (instantiate real instances for validation testing)
- Core business logic functions (test directly)
- Dataclass instances (create real instances)
- Local path operations (use temp directories)

## Fixtures and Factories

**Test Data:**
```python
def _make_incident(incident_id: str = "TEST-001", n_controls: int = 2) -> dict:
    """Build a minimal Schema v2.3 incident dict with controls."""
    controls = []
    for i in range(n_controls):
        controls.append({
            "control_id": f"C-{i+1:03d}",
            "name": f"Control {i+1}",
            "side": "prevention" if i % 2 == 0 else "mitigation",
            "barrier_role": "detect",
            # ... more fields
        })
    return {
        "incident_id": incident_id,
        "bowtie": {"hazards": [], "threats": [], "consequences": [], "controls": controls},
    }


class TestFlattenControls:
    def test_basic_flatten(self):
        incident = _make_incident(n_controls=2)
        rows = flatten_controls(incident)
        assert len(rows) == 2
```

**Location:**
- Inline factory functions at top of test files (not in separate `conftest.py`)
- Named `_make_<type>()` for builders
- Named with `@pytest.fixture` decorator for reusable setup

**Examples:**
- `sample_bowtie` — fixture creating Bowtie with known structure
- `sample_incident` — fixture creating Incident with known barriers
- `_make_incident()` — factory function for customizable v2.3 incident dicts
- `_mock_response()` — factory for HTTP response objects

## Coverage

**Requirements:** Not enforced; no coverage thresholds in pyproject.toml

**View Coverage:**
```bash
pytest --cov=src --cov-report=html
pytest --cov=src --cov-report=term-missing
```

**Common Coverage Gaps (observed):**
- Integration tests with real PDFs (marked with `pytest.skip()` if PDFs unavailable)
- Error paths in extraction (fallback logic not always exercised in test suite)
- Optional Bowtie loading (graceful degradation when bowtie.json missing)

## Test Types

**Unit Tests (majority):**
- Scope: Single function or class in isolation
- Approach: Direct function call with known inputs, assert outputs
- Location: Most test files (test_analytics.py, test_models.py, test_flatten.py)
- Fixtures used: Pydantic model instances, simple dicts, mocked HTTP responses
- Example: `test_calculate_barrier_coverage` — calls `calculate_barrier_coverage()`, asserts coverage metrics

**Integration Tests (secondary):**
- Scope: Multiple modules working together (e.g., structured extraction pipeline)
- Approach: Set up temp directories, invoke orchestration functions, verify file outputs
- Location: `test_extract_structured.py`, `test_manifest_merge.py`, `test_source_ingest.py`
- Fixtures used: `tempfile.TemporaryDirectory()`, real Pydantic models, CSV/JSON I/O
- Example: `test_stub_extraction_produces_json` — writes text file, runs extraction, verifies JSON output exists

**End-to-End Tests (rare):**
- Scope: Full pipeline from PDF → extraction → analytics
- Approach: Mark with `pytest.skip()` if external resources unavailable
- Location: `test_extraction_extractor.py` (skips if no BSEE PDFs)
- Example: `test_extracts_from_real_pdf` — requires actual PDF files, skips gracefully

**E2E Test Markers:**
```python
def test_extracts_from_real_pdf(self) -> None:
    """Smoke test with a real BSEE PDF if available."""
    pdf_dir = Path("data/raw/bsee/pdfs")
    if not pdf_dir.exists():
        pytest.skip("No BSEE PDFs available for smoke test")
    # ... continue with test
```

## Common Patterns

**Async Testing:**
Not used; all code is synchronous. No `async def` or `await` in codebase.

**Error Testing:**
```python
def test_validation(self):
    with pytest.raises(ValueError):
        Incident(
            incident_id="INC-005",
            description="Test",
            injuries=-1  # Constraint violation
        )

def test_missing_key_raises(self):
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider(api_key="")
```

**Parametrized Tests:**
Not extensively used; most tests are explicit (one test per scenario). Single parametrized example:
```python
# Not common pattern in this codebase; prefer explicit tests
```

**Temporary Files/Directories:**
```python
import tempfile
from pathlib import Path

def test_flatten_all_writes_csv(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        struct_dir = Path(tmpdir) / "structured"
        struct_dir.mkdir()
        out_csv = Path(tmpdir) / "controls.csv"

        # Test logic here
        assert out_csv.exists()
```

**Manifest Roundtrips:**
Common pattern in integration tests — save then load to verify serialization:
```python
def test_save_and_load_roundtrip(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_path = Path(tmpdir) / "manifest.csv"
        original = [self._make_row("INC-001"), self._make_row("INC-002")]

        save_structured_manifest(original, manifest_path)
        loaded = load_structured_manifest(manifest_path)

        assert len(loaded) == 2
        assert loaded[0].incident_id == "INC-001"
```

**Fixture Lifecycle:**
- Default scope: `function` (fresh fixture per test function)
- Reused across class methods via class-level fixture collection
- No session or module-level fixtures

**Stubbing/Mocking Strategy:**
- LLM providers stubbed with `StubProvider` (in-tree test double): `from src.llm.stub import StubProvider`
- HTTP responses mocked with `unittest.mock`
- Database queries not applicable (no DB in codebase)
- File I/O tested with real temp files (not mocked)

## Quality & Best Practices

**Test Independence:**
- Each test is isolated (no shared state between test functions)
- Fixtures created fresh per test (function scope default)
- Temp directories cleaned up automatically by context manager

**Readability:**
- Test names are descriptive: `test_calculate_barrier_coverage`, `test_missing_key_raises_runtime_error`
- Docstrings on test functions explain scenario: `"""Test calculation of barrier coverage percentages."""`
- Class docstrings explain scope: `"""Test cases for Bowtie analytics engine."""`

**Assertions:**
- One logical assertion per test (or multiple related assertions in one test)
- Clear failure messages via pytest's diff display
- Optional inline messages: `assert x == y, f"Expected {y}, got {x}"`

**Avoiding Common Pitfalls:**
- No `setUp`/`tearDown` methods (use `@pytest.fixture` instead)
- No test interdependencies (each test stands alone)
- No hardcoded file paths (use `Path()` and relative references)
- No real API calls in unit tests (always mock or use StubProvider)

---

*Testing analysis: 2025-02-27*
