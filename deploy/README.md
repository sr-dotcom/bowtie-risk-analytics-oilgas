# Deploy infrastructure

This directory holds infrastructure files for server-side deployment.
Populated across Phases 2–6 of server onboarding.

Target production environment:
- Frontend: https://bowtie.gnsr.dev
- Backend:  https://api.bowtie.gnsr.dev
- Host:     Self-hosted mini-PC, Ubuntu 24.04
- Registry: ghcr.io
- CI/CD:    GitHub Actions → dedicated webhook → deploy.sh

## Phase 2 — Local image builds

From repo root:

    docker build -f deploy/Dockerfile.api -t bowtie-api:phase2-local .
    docker build -f deploy/Dockerfile.frontend \
      --build-arg NEXT_PUBLIC_API_URL=http://localhost:8100 \
      -t bowtie-frontend:phase2-local .

Local smoke test:

    docker run --rm -d -p 8100:8000 --name bowtie-api-smoke bowtie-api:phase2-local
    docker run --rm -d -p 8101:3000 --name bowtie-frontend-smoke bowtie-frontend:phase2-local
    curl -fsS http://localhost:8100/health | jq .
    curl -fsS -o /dev/null -w "%{http_code}\n" http://localhost:8101
    docker stop bowtie-api-smoke bowtie-frontend-smoke
