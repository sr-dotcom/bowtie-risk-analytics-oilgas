# Deploy Guide

This document describes the actual deployment topology for Bowtie Risk Analytics. It reflects the state at handover (v1.0, HEAD `e499697`).

---

## Production deploy (current working path)

```bash
ssh gmk './deploy.sh'
```

`deploy.sh` lives at `/opt/projects/bowtie-analytics/deploy.sh` on the GMK server (self-hosted Ubuntu 24.04 mini-PC). It pulls `ghcr.io/sr-dotcom/bowtie-risk-analytics-oilgas:latest`, restarts via `docker compose -f deploy/docker-compose.server.yml up -d`, and runs a health check.

**Requirements:** SSH access to the GMK server. The live `.env` at `/opt/projects/bowtie-analytics/.env` (mode 600) holds the real `ANTHROPIC_API_KEY`.

`deploy.sh` and the webhook compose (`/opt/projects/webhook-bowtie/docker-compose.yml`) live on the server, not in this repo. Recreating them on a fresh server: follow `deploy/README.md` (server bootstrap section).

---

## CI/CD — image build (working)

`.github/workflows/deploy.yml` builds and pushes two Docker images on every push to `main` (paths filter: `src/**`, `frontend/**`, `configs/**`, `data/models/artifacts/**`, `requirements*.txt`, Dockerfiles).

| Image | Tag |
|---|---|
| `ghcr.io/sr-dotcom/bowtie-risk-analytics-oilgas-api` | `:latest` + `:<sha>` |
| `ghcr.io/sr-dotcom/bowtie-risk-analytics-oilgas-frontend` | `:latest` + `:<sha>` |

These images are built by `deploy/Dockerfile.api` and `deploy/Dockerfile.frontend`. They are pushed reliably on every qualifying push and are available for any receiver standing up their own infrastructure.

**Note:** the production server (`deploy/docker-compose.server.yml`) pulls a *combined* single-container image (`ghcr.io/sr-dotcom/bowtie-risk-analytics-oilgas:latest`) built from the root `Dockerfile` — not the per-service images above. The GHA-built per-service images are unused by the current production stack. This asymmetry is documented in `KNOWN_ISSUES.md §2.1` and `docs/journey/07-deployment.md`.

---

## CI/CD — auto-deploy (non-functional, documented)

The `trigger-deploy` job in `deploy.yml` POSTs to `https://bowtie-deploy.gnsr.dev/hooks/bowtie-analytics` after both images build. This webhook is designed to trigger `deploy.sh` on the server automatically.

**Current state:** the Cloudflare Tunnel route for `bowtie-deploy.gnsr.dev` has not been added, and the webhook listener on the server is not registered. The `curl` POST fails silently because the job runs with `continue-on-error: true`. Auto-deploy is therefore inoperative; `ssh gmk './deploy.sh'` is the reliable path.

**To fix (15-minute task):** add the `bowtie-deploy.gnsr.dev` route in the Cloudflare Tunnel dashboard, ensure the webhook listener compose (`/opt/projects/webhook-bowtie/`) is running, and set the `DEPLOY_WEBHOOK_SECRET` GitHub Actions secret.

---

## Local development

```bash
# First time only
cp .env.example .env        # add ANTHROPIC_API_KEY if using LLM features

# Option A — three-service Docker Compose stack (recommended for full-stack)
docker compose up --build   # API + frontend + nginx on localhost:80

# Option B — bare processes (fastest iteration)
uvicorn src.api.main:app --reload --port 8000   # FastAPI on :8000
cd frontend && npm run dev                       # Next.js on :3000
```

See `README.md` for the full local setup including Python venv, model artifact bootstrap, and test commands.

---

## nginx config files

Two nginx configs are committed, each self-labeling its role:

| File | Used by | Purpose |
|---|---|---|
| `nginx/nginx.conf` | Root `docker-compose.yml` (local dev stack) | DEV / HISTORICAL — rate-limiting, security headers, WebSocket support |
| `deploy/nginx.conf` | GMK server host nginx | PRODUCTION CANONICAL — listens on 8080, proxies to localhost:8000 (API) and localhost:3000 (frontend) |

Neither is baked into a Docker image — both are mounted as volumes at runtime or referenced by the host nginx process.

---

## Deploy targets supported

| Target | Status | Notes |
|---|---|---|
| Self-hosted Docker Compose (GMK server) | **Current production** | `ssh gmk './deploy.sh'` |
| `docker compose up --build` (any host) | Working fallback | Three-service stack; port 80 |
| `docker compose -f deploy/docker-compose.server.yml up` | Working | Single-container path; port 8080 |
| AWS ECS / EKS | Suitable with minor work | Container images are stateless; secrets via env; `data/` volume replaceable with EFS or S3-backed storage |
| Render / Railway / Fly.io | Suitable | FastAPI and Next.js are standard containerized services |

The stack has no host-mount dependencies beyond the writable `data/` volume (model artifacts, processed CSVs). All configuration is via environment variables. The `ANTHROPIC_API_KEY` is the only secret required for full LLM functionality; the system degrades gracefully (predictions work, RAG narrative skipped) when the key is absent.
