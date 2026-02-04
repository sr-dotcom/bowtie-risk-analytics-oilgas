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

- `src/models`: Data definitions.
- `src/analytics`: Core business logic.
- `src/app`: Dashboard implementation.

## Workflow

- Create a feature branch for changes.
- Ensure tests pass locally.
- Update `docs/DEVLOG.md` with significant progress.
