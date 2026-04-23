# Deploy infrastructure

This directory holds infrastructure files for server-side deployment.
Populated across Phases 2–6 of server onboarding.

Target production environment:
- Frontend: https://bowtie.gnsr.dev
- Backend:  https://api.bowtie.gnsr.dev
- Host:     Self-hosted mini-PC, Ubuntu 24.04
- Registry: ghcr.io
- CI/CD:    GitHub Actions → dedicated webhook → deploy.sh
