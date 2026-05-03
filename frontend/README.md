# Bowtie Risk Analytics — Frontend

Next.js 16 + React 19 dashboard for the Bowtie barrier-failure risk analytics application. This is the user-facing layer that renders the interactive bowtie diagram, executes scenarios against the cascading XGBoost model, and surfaces SHAP factor explanations + RAG-cited evidence.

For system-wide context, architecture, and the full handover, see the root [`../README.md`](../README.md), [`../CLAUDE.md`](../CLAUDE.md), and [`../HANDOVER.md`](../HANDOVER.md).

---

## Stack

- Next.js 16.2.3 (App Router)
- React 19
- TypeScript (strict)
- Tailwind CSS
- Vitest 4.x for unit + component tests

---

## Local development

```bash
# from frontend/
npm install
npm run dev
```

Opens at [http://localhost:3000](http://localhost:3000) and proxies `/api/*` calls to the backend via the URL configured in `.env.local`.

For the full local stack (API + frontend + nginx), use the root `docker compose up` instead — see [`../HANDOVER.md`](../HANDOVER.md) "First 30 Minutes" for the canonical bootstrap sequence.

---

## Environment variables

Copy [`.env.example`](.env.example) to `.env.local` and fill in:

- `NEXT_PUBLIC_API_URL` — backend API base URL. Default `http://localhost:8000` for direct uvicorn dev; `http://localhost:80` when running behind the Docker nginx proxy.

`NEXT_PUBLIC_*` values are baked into the client bundle at `next build` time, not at runtime. For production Docker builds, pass them as build-args before `next build`.

---

## Tests

```bash
npm test           # vitest watch mode
npm test -- --run  # one-shot CI mode (250 tests, gate ≥250)
```

The frontend gate (≥250) is documented in [`../tests/README.md`](../tests/README.md) alongside the backend gate.

---

## Build

```bash
npm run build      # production build (requires NEXT_PUBLIC_API_URL set)
npm run start      # serve the built output
```

For containerised production, the canonical build is via [`../deploy/Dockerfile.frontend`](../deploy/Dockerfile.frontend) with build context `.` (project root). The root [`../docker-compose.yml`](../docker-compose.yml) delegates to that file.

---

## Component structure

```
app/                        # Next.js App Router entry (layout.tsx, page.tsx)
components/
  BowtieApp.tsx             # root application component
  diagram/                  # interactive SVG bowtie diagram (BowtieSVG.tsx)
  dashboard/                # 4-tab dashboard: Executive Summary, Drivers & HF,
                            #   Ranked Barriers, Evidence (DashboardView.tsx etc.)
  panel/                    # per-barrier detail panel: SHAP waterfall + RAG evidence
  sidebar/                  # scenario selection + barrier list sidebar
  ui/                       # shared UI primitives
context/                    # React context: bowtie state, predictions, scenario mgmt
hooks/                      # useAnalyzeCascading, useExplainCascading, useBowtieContext
__tests__/                  # Vitest unit + component tests
```

For the data flow from cascading model outputs through the API to the dashboard render, see [`../docs/journey/06-frontend-ux.md`](../docs/journey/06-frontend-ux.md).
