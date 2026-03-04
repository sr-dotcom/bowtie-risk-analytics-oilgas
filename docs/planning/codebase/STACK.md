# Technology Stack

**Analysis Date:** 2026-02-27

## Languages

**Primary:**
- Python 3.9+ - All application code, CLI, analytics, and pipeline
- YAML - Configuration files (model policy ladder)

**Secondary:**
- JSON - Data persistence format for incidents and manifests
- CSV - Manifest tracking and flat export format

## Runtime

**Environment:**
- Python 3.12.3 (verified running; pyproject.toml requires >=3.9)

**Package Manager:**
- pip (via venv)
- Lockfile: Not present (requirements.txt pinned to minimum versions only)

## Frameworks

**Core:**
- Streamlit >=1.30.0 - Web UI dashboard (`src/app/main.py`)
- Pydantic >=2.0.0 - Data validation and serialization for all data models

**CLI/Build:**
- argparse (Python stdlib) - Command-line interface
- setuptools (via pyproject.toml) - Package building

**Testing:**
- pytest >=7.0.0 - Unit and integration tests
- Config: `pyproject.toml` [tool.pytest.ini_options]
  - Test path: `tests/`
  - Test files: `test_*.py`
  - Test functions: `test_*`

**Data Processing:**
- pandas >=2.0.0 - DataFrame operations, analytics, CSV manipulation
- BeautifulSoup4 >=4.12.0 - HTML/XML parsing for web scraping

## Key Dependencies

**Critical:**
- requests >=2.28.0 - HTTP client for web scraping (CSB, BSEE, TSB, PHMSA sources) and Anthropic Messages API calls
- pdfplumber >=0.10.0 - PDF text extraction
- PyMuPDF >=1.23.0 - PDF manipulation and text extraction (alternative/supplemental to pdfplumber)
- pdfminer.six >=20221105 - Advanced PDF text analysis

**Infrastructure:**
- python-dateutil >=2.8.0 - Date parsing and manipulation for incident date normalization
- python-dotenv >=1.0.0 - Environment variable loading from `.env` files for local development
- PyYAML (imported by model_policy.py) - YAML configuration parsing for model ladder

## Configuration

**Environment:**
- `.env` file (not committed) - Contains sensitive API keys
  - Loading: `python-dotenv` via `load_dotenv()` in `src/pipeline.py`
  - Location: Project root

**Build:**
- `pyproject.toml` - Project metadata, dependencies, and pytest configuration
- `configs/model_policy.yaml` - Claude model ladder configuration
  - Defines provider, default model, fallback models, retry strategy
  - Location: `configs/model_policy.yaml`
- `configs/sources/` - Source-specific URL lists and metadata CSVs
  - CSB, BSEE, PHMSA, TSB source configurations

## Platform Requirements

**Development:**
- Python 3.9+
- Virtual environment (venv)
- Local filesystem access for data and config directories
- Network access for:
  - Anthropic Messages API (https://api.anthropic.com/v1/messages)
  - CSB website (https://www.csb.gov)
  - BSEE website (https://www.bsee.gov)
  - TSB website (https://www.tsb.gc.ca)
  - PHMSA sources

**Production:**
- Python 3.9+
- Streamlit runtime for dashboard
- Local filesystem for data persistence (no remote database)
- Network access to:
  - Anthropic Messages API (required for LLM extraction)
  - Public incident databases (CSB, BSEE, TSB, PHMSA) for discovery/ingestion

**Deployment Target:**
- Standalone Streamlit application or CLI tool
- No containerization configured (no Dockerfile/docker-compose)
- No cloud-native frameworks (no FastAPI, no serverless)

---

*Stack analysis: 2026-02-27*
