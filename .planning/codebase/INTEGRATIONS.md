# External Integrations

**Analysis Date:** 2026-02-27

## APIs & External Services

**LLM Extraction:**
- Anthropic Claude (Messages API) - Structured extraction of risk factors from incident narratives
  - SDK/Client: `requests` library (HTTP calls, no official SDK)
  - API URL: `https://api.anthropic.com/v1/messages`
  - Auth: `ANTHROPIC_API_KEY` environment variable (required)
  - Implementation: `src/llm/anthropic_provider.py`
  - Models: Configurable via `configs/model_policy.yaml` (default: claude-haiku-4-5-20251001, fallback ladder to claude-sonnet-4-6)
  - Retries: Exponential backoff on 429/5xx errors (default 2 retries per model)
  - Max tokens: Default 4096, configurable per extraction

**Public Data Sources (Discovery & Ingestion):**
- CSB (Chemical Safety Board) - https://www.csb.gov
  - Discovery: `src/ingestion/sources/csb_discover.py`
  - Completed investigations listing: `https://www.csb.gov/investigations/completed-investigations/`
  - Method: HTTP GET + HTML parsing with BeautifulSoup4
  - Auth: None (public website)
  - Rate limiting: Polite delay between requests

- BSEE (Bureau of Safety and Environmental Enforcement) - https://www.bsee.gov
  - Discovery: `src/ingestion/sources/bsee_discover.py`
  - District reports: `https://www.bsee.gov/what-we-do/incident-investigations/offshore-incident-investigations/district-investigation-reports`
  - Panel reports: `https://www.bsee.gov/what-we-do/incident-investigations/offshore-incident-investigations/panel-investigation-reports`
  - Method: HTTP GET + HTML parsing with BeautifulSoup4
  - Auth: None (public website)

- PHMSA (Pipeline and Hazardous Materials Safety Administration) - Multiple sources
  - Discovery: `src/ingestion/sources/phmsa_discover.py`
  - Ingestion: `src/ingestion/sources/phmsa_ingest.py`
  - Method: CSV parsing (public datasets)
  - Auth: None

- TSB (Transportation Safety Board, Canada) - https://www.tsb.gc.ca
  - Discovery: `src/ingestion/sources/tsb_discover.py`
  - Ingestion: `src/ingestion/sources/tsb_ingest.py`
  - Pipeline reports: `https://www.tsb.gc.ca/eng/reports/pipeline/index.html`
  - Method: HTTP GET + HTML parsing with BeautifulSoup4
  - Auth: None (public website)

## Data Storage

**Databases:**
- None - No database engine (SQL or NoSQL)
- Data persisted as JSON files in local filesystem

**File Storage:**
- Local filesystem only
  - `data/raw/` — Downloaded PDFs and raw text
  - `data/structured/` — LLM extraction outputs and manifests
  - `data/processed/` — Final JSON incidents and analytics results
  - `configs/` — Configuration and source URL lists

**Data Formats:**
- JSON - Incident records (V2.2 and V2.3 schemas with BOM: `encoding="utf-8-sig"`)
- CSV - Manifests for tracking pipeline state (incident, text, structured, converted)
- CSV - Flat exports (incidents and controls)

**Caching:**
- None - No caching layer (Redis, Memcached, etc.)

## Authentication & Identity

**Auth Provider:**
- Custom/None - No user authentication system
- API access via environment variables only:
  - `ANTHROPIC_API_KEY` (required)
  - `OPENAI_API_KEY` (optional, not actively used in current codebase)
  - `GEMINI_API_KEY` (optional, not actively used in current codebase)

**Implementation:**
- `src/llm/registry.py` - Provider registry with environment variable checks
- `src/llm/anthropic_provider.py` - Reads `ANTHROPIC_API_KEY` from env
- `.env` file loaded by `python-dotenv` in `src/pipeline.py`

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service (Sentry, Rollbar, etc.)

**Logs:**
- Python logging to console (via `logging.basicConfig()` in `src/pipeline.py`)
- Log level: INFO
- Format: `%(asctime)s - %(levelname)s - %(message)s`
- Per-module loggers created with `logging.getLogger(__name__)`
- Latency and usage metadata captured in AnthropicProvider.last_meta after each LLM call

## CI/CD & Deployment

**Hosting:**
- Not deployed - Standalone CLI tool and Streamlit dashboard
- No cloud hosting configured

**CI Pipeline:**
- None configured (no GitHub Actions, GitLab CI, etc.)
- Tests run locally via `pytest`

## Environment Configuration

**Required env vars:**
- `ANTHROPIC_API_KEY` - Anthropic Messages API key (required for LLM extraction; pipeline fails if missing)

**Optional env vars (fallback providers, not currently implemented):**
- `OPENAI_API_KEY` - OpenAI API key (defined in .env.example but not used)
- `GEMINI_API_KEY` - Google Gemini API key (defined in .env.example but not used)

**Secrets location:**
- `.env` file in project root (git-ignored)
- Never committed to version control
- Template: `.env.example`

## Webhooks & Callbacks

**Incoming:**
- None - No webhook endpoints exposed

**Outgoing:**
- None - No callbacks to external services

## Network Configuration

**HTTP Requests:**
- User-Agent header: `"BowtieRiskAnalytics/0.1 (academic research)"` in web scrapers
- Timeouts: Default 120 seconds in AnthropicProvider
- Retries: Automatic retry with exponential backoff (1s, 2s, 4s) on transient errors (429, 5xx)
- Connection pooling: Requests session reuse in source discovery modules

**DNS/URLs:**
- All public URLs resolved at runtime (no hardcoded IPs)
- Base URLs defined as module constants in source modules:
  - CSB_BASE_URL, BSEE_BASE_URL, TSB_BASE_URL, etc.

---

*Integration audit: 2026-02-27*
