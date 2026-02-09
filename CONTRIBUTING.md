# Contributing

## Development Setup

1.  **Environment**: Python 3.10+ required.
2.  **Dependencies**:
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Testing**: Run `pytest` before pushing changes.

## Code Style

- **Type Hints**: Required for all function definitions.
- **Models**: Use Pydantic v2 for data structures.
- **Formatting**: Follow PEP 8.

## Directory Structure

- `src/models/` -- Pydantic v2 data models (Incident, Bowtie, Schema v2.3).
- `src/ingestion/` -- Data acquisition, PDF text extraction, structured LLM extraction.
- `src/llm/` -- LLM provider abstraction (Stub, OpenAI, Anthropic, Gemini).
- `src/prompts/` -- Extraction prompt templates and loader.
- `src/validation/` -- Pydantic-based schema validation.
- `src/analytics/` -- Coverage calculation, gap analysis, flattening, baseline analytics.
- `src/app/` -- Streamlit dashboard.
- `assets/schema/` -- Schema v2.3 JSON schema and template.
- `assets/prompts/` -- Extraction prompt markdown.
- `docs/` -- ADRs, devlog, step tracker, meeting notes, handoff docs.
- `scripts/` -- Standalone analytics CLI.
- `tests/` -- Unit tests (`pytest`).

## Workflow

- Create a feature branch for changes.
- Ensure tests pass locally.
- Update `docs/devlog/DEVLOG.md` with significant progress.
