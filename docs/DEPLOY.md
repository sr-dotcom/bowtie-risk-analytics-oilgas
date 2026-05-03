# Deploy Guide

This document describes the deployment topologies for Bowtie Risk Analytics at handover (v1.0, HEAD `e499697`).

---

## Deployment topologies at a glance

| Topology | Entry point | nginx | Ports | Status |
|---|---|---|---|---|
| **T1** — three-service Compose | `docker compose up` | `nginx/nginx.conf` (container) | host:80 | Local dev / self-hosted |
| **T2** — single-container | `docker compose -f deploy/docker-compose.server.yml up` | `deploy/nginx.conf` (inside container) | host:8080 | Server bootstrap reference |
| **T3** — Cloudflare Tunnel | Per-service containers + Cloudflare routing | None | internal | Live demo (`bowtie.gnsr.dev`) |

---

## T1 — Three-service Docker Compose (local dev / self-hosted)

```bash
cp .env.example .env        # first time only — add ANTHROPIC_API_KEY if needed
docker compose up --build   # starts api:8000 + frontend:3000 + nginx:80
```

**How it works:** `docker-compose.yml` (repo root) spins up three named containers. nginx (`nginx/nginx.conf`) listens on host port 80, proxies `/api/*` to `http://api:8000` and `/` to `http://frontend:3000`. Rate-limiting and security headers are applied at the nginx layer.

**Config:** `nginx/nginx.conf` — labelled "DEV / HISTORICAL". Upstreams use Docker service names (`api`, `frontend`), so this topology only works inside the Compose network.

**Use for:** local full-stack development, or any host where you want the three-container stack.

---

## T2 — Single-container (server bootstrap reference)

```bash
docker compose -f deploy/docker-compose.server.yml up -d
```

**How it works:** Root `Dockerfile` builds a single image containing both the FastAPI backend and the Next.js frontend. `deploy/start.sh` (the container entrypoint) starts FastAPI on `127.0.0.1:8000`, then Next.js, then brings nginx to the foreground. `deploy/nginx.conf` listens on port 8080, proxying `/api/*` to `:8000` and `/` to `:3000` over localhost.

**Config:** `deploy/nginx.conf` — labelled "PRODUCTION CANONICAL". Upstreams use `127.0.0.1` (all processes share a network namespace inside the single container). The container exposes `8080:8080`.

**Image:** `ghcr.io/sr-dotcom/bowtie-risk-analytics-oilgas:latest` (built from root `Dockerfile`).

**Use for:** bootstrapping a fresh server. `deploy/docker-compose.server.yml` is the reference compose file for this topology.

---

## T3 — Cloudflare Tunnel / per-service (live demo)

**Live demo:** `https://bowtie.gnsr.dev`

**How it works:** The GMK server (Ubuntu 24.04 mini-PC) runs per-service containers. The Cloudflare Tunnel routes `bowtie.gnsr.dev` directly to the appropriate service container — there is no nginx in this topology. Cloudflare handles TLS termination and acts as the reverse proxy.

**Images:** built by `deploy/Dockerfile.api` and `deploy/Dockerfile.frontend` (pushed via GHA `deploy.yml`).

**Note on the GHA-built images:** GHA builds and pushes `ghcr.io/sr-dotcom/bowtie-risk-analytics-oilgas-api:latest` and `-frontend:latest` on every qualifying push to `main`. These per-service images are what T3 uses. The root-Dockerfile combined image (used by T2) is a separate artifact.

---

## Production deploy — current working path

```bash
ssh gmk './deploy.sh'
```

`deploy.sh` lives at `/opt/projects/bowtie-analytics/deploy.sh` on the GMK server. A copy is committed at `deploy/deploy.sh` for reference. It pulls the latest image, runs `docker compose up -d` (using the server's local `docker-compose.yml`), then polls `http://127.0.0.1:8100/health` up to five times to confirm the API is healthy.

**Requirements:** SSH access to the GMK server. The live `.env` at `/opt/projects/bowtie-analytics/.env` (mode 600) holds the real `ANTHROPIC_API_KEY`.

---

## CI/CD — image build (working)

`.github/workflows/deploy.yml` builds and pushes two Docker images on every push to `main` (paths filter: `src/**`, `frontend/**`, `configs/**`, `data/models/artifacts/**`, `requirements*.txt`, Dockerfiles).

| Image | Tag |
|---|---|
| `ghcr.io/sr-dotcom/bowtie-risk-analytics-oilgas-api` | `:latest` + `:<sha>` |
| `ghcr.io/sr-dotcom/bowtie-risk-analytics-oilgas-frontend` | `:latest` + `:<sha>` |

These are the T3 per-service images. The combined single-container image (T2) is not built by GHA — build it locally with `docker build -t bowtie .` from the repo root.

---

## CI/CD — auto-deploy (non-functional, documented)

The `trigger-deploy` job in `deploy.yml` POSTs to `https://bowtie-deploy.gnsr.dev/hooks/bowtie-analytics` after both images build. This webhook is intended to trigger `deploy.sh` on the server automatically.

**Current state:** the Cloudflare Tunnel route for `bowtie-deploy.gnsr.dev` has not been added, and the webhook listener on the server is not registered (`/opt/projects/webhook/hooks/hooks.json` has `healthz` and `policy-assistant` but not `bowtie-analytics`). The `curl` POST fails silently because the job runs with `continue-on-error: true`. Auto-deploy is therefore inoperative; `ssh gmk './deploy.sh'` is the reliable path.

**To fix (15-minute task):**
1. Add the `bowtie-deploy.gnsr.dev` route in the Cloudflare Tunnel dashboard pointing to the webhook listener container.
2. Register a `bowtie-analytics` hook in `/opt/projects/webhook/hooks/hooks.json`.
3. Set the `DEPLOY_WEBHOOK_SECRET` GitHub Actions secret.

---

## Local development (bare processes)

```bash
# First time only
cp .env.example .env        # add ANTHROPIC_API_KEY if using LLM features

# FastAPI backend
uvicorn src.api.main:app --reload --port 8000

# Next.js frontend (separate terminal)
cd frontend && npm run dev  # http://localhost:3000
```

See `README.md` for the full local setup including Python venv and model artifact bootstrap.

---

## nginx config files

| File | Used by | Purpose |
|---|---|---|
| `nginx/nginx.conf` | T1 — root `docker-compose.yml` | DEV config: Docker service-name upstreams, rate-limiting, security headers, WebSocket support |
| `deploy/nginx.conf` | T2 — single container (`deploy/start.sh`) | Production config: listens on 8080, `127.0.0.1` upstreams, tighter timeouts on `/api/explain` |

Neither is baked into a Docker image — both are mounted as volumes at runtime or bind-mounted by the container entrypoint.

---

## AWS migration guide

The stack is stateless apart from the `data/` volume. Migrating to AWS requires three steps:

**1. Push images to ECR**

```bash
aws ecr create-repository --repository-name bowtie-api
aws ecr create-repository --repository-name bowtie-frontend
aws ecr get-login-password | docker login --username AWS \
    --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker tag bowtie-api:latest <account>.dkr.ecr.<region>.amazonaws.com/bowtie-api:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/bowtie-api:latest
# repeat for bowtie-frontend
```

Or update the GHA workflow: replace the `ghcr.io` push step with an `aws-actions/amazon-ecr-login` step.

**2. Replace the `data/` volume**

Model artifacts (`data/models/artifacts/`) and the RAG FAISS indexes (`data/rag/v2/`) must be accessible at container start. Options:

- **EFS** (simplest): mount an EFS filesystem at `/app/data` in the ECS task definition. Copy artifacts once via a bootstrap task.
- **S3 + init container**: add an init container that runs `aws s3 sync s3://your-bucket/data /app/data` before the main container starts.
- **Bake into image**: acceptable for model artifacts only (not for large RAG embeddings). Add a `COPY data/models/artifacts/ /app/data/models/artifacts/` layer in the Dockerfile.

**3. Secrets**

Replace the `.env` file with AWS Secrets Manager or SSM Parameter Store:

```json
// ECS task definition — containerDefinitions.secrets
{
  "name": "ANTHROPIC_API_KEY",
  "valueFrom": "arn:aws:secretsmanager:<region>:<account>:secret:bowtie/anthropic-key"
}
```

`BOWTIE_API_KEY`, `CORS_ALLOWED_ORIGINS`, and `ENVIRONMENT` can be plain environment variables in the task definition.

**Cost estimate (us-east-1, light load):**

| Component | Service | Monthly |
|---|---|---|
| API container | ECS Fargate 0.25 vCPU / 0.5 GB | ~$9 |
| Frontend container | ECS Fargate 0.25 vCPU / 0.5 GB | ~$9 |
| Data volume | EFS 1 GB (artifacts + indexes) | ~$1 |
| Load balancer | ALB | ~$16 |
| **Total** | | **~$35/month** |

Alternatively: a single `t3.small` EC2 instance (~$15/month) running the T2 single-container image behind ALB is simpler and cheaper for low traffic.

---

## Deploy targets summary

| Target | Status | Notes |
|---|---|---|
| GMK server (T3 live demo) | **Current production** | Cloudflare Tunnel + per-service containers; `ssh gmk './deploy.sh'` |
| `docker compose up --build` (T1) | Working | Three-service stack; port 80; nginx in container |
| `docker compose -f deploy/docker-compose.server.yml up` (T2) | Working | Single-container; port 8080; nginx inside container |
| AWS ECS / EKS | Suitable with minor work | See migration guide above |
| Render / Railway / Fly.io | Suitable | FastAPI and Next.js are standard containerized services |

The `ANTHROPIC_API_KEY` is the only secret required for full LLM functionality. The system degrades gracefully (predictions work, RAG narrative skipped) when the key is absent.
