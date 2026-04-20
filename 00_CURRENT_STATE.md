# M003 Current State

Milestone: **M003-z2jh4m** — Cascading Pair-Feature Model + Scenario-Builder UI

## Slice Status

| Slice | Status | Commit |
|-------|--------|--------|
| S01 | ✓ | (prior milestone work) |
| S02 | ✓ | (prior milestone work) |
| S02b | ✓ | bb912c2 |
| S04 | ✓ | 9cd3a86 |
| **S03** | **✓** | 363dfdf (T01), c5cb13b (T02+T03), see T04 commit below |
| S05a | NEXT | — |

## S03 — Cascading API Endpoints

**T01** (`363dfdf`) — `src/modeling/cascading/predict.py`: CascadingPredictor with predict/rank/explain.  
**T02+T03** (`c5cb13b`) — Three new endpoints (POST /predict-cascading, /rank-targets, /explain-cascading) + 410 Gone for legacy /predict and /explain.  
**T04** — Integration test + API contract doc.

### What shipped in S03

- `CascadingPredictor` inference module: derives 18 cascade-pair features from demo-scenario JSON, runs the trained `xgb_cascade_y_fail_pipeline.joblib`, computes SHAP via `shap_probe.compute_shap_for_record`. Sorted predictions, risk bands from `configs/risk_thresholds.json` (p60=0.45, p80=0.70).
- Three new FastAPI endpoints loaded from RAGAgent v2 + CascadingPredictor (lifespan, graceful degradation).
- `/predict` and `/explain` converted to GET → HTTP 410 Gone with `migrate_to` hints.
- 44 new tests (13 T01 + 11 T02 + 9 T03 + 2 integration).
- `docs/api_contract.md` with curl examples, graceful degradation contract, error codes.
- D016 Branch C enforced: `y_hf_fail_probability` absent from all public API surfaces.

## Key Artifacts

| Artifact | Path |
|----------|------|
| Cascading pipeline | `data/models/artifacts/xgb_cascade_y_fail_pipeline.joblib` |
| Cascade metadata | `data/models/artifacts/xgb_cascade_y_fail_metadata.json` |
| Risk thresholds | `configs/risk_thresholds.json` |
| RAG v2 corpus | `data/rag/v2/` |
| API contract | `docs/api_contract.md` |

---

## T1–T2a Soul Pass (2026-04-20 session)

### Current slice
**T2b — narrative hero Haiku synthesis (pending fresh chat)**

### Soul pass status
| Pass | Status | Commits |
|------|--------|---------|
| Phase cleanup | ✓ | 469bc93, 0231177, 6c7b784, b49c1a7 |
| T1 foundation (tokens + CSS vars) | ✓ | 9ec071a |
| T1 palette swap (16 components) | ✓ | b62fc54 |
| T1c island patch (§7 visual island) | ✓ | 5fcb2c3 |
| T2a narrative hero template | ✓ | d0be94f |
| T2b Haiku synthesis button | pending | — |

### What T1 shipped (b62fc54)
- `frontend/lib/design-tokens.ts` — `TOKENS` const with full palette as literals
- `frontend/app/globals.css` — CSS custom properties (`--bg-base`, `--risk-high`, etc.)
- 15 components + 2 test files: all ad-hoc hex values replaced with T1 design tokens
- Risk badges + pills: refactored from Tailwind class strings → `CSSProperties` objects using `bg.accent + border + risk.*Text` pattern (UI-CONTEXT.md §6)
- Test count: 171/171 maintained throughout
- UI-CONTEXT.md bumped v2.2 → v2.3

### What T1c shipped (5fcb2c3)
- Defect 1 fixed: wrapped `<BowtieSVG>` in `<div className="h-full w-full bg-[#0F1419] p-3">` in `BowtieApp.tsx`
- Root cause was BowtieSVG's own wrapper filling `<main>` edge-to-edge with `background: '#E8E8E8'`; the 12px dark frame now creates the visual island per §7
- Defect 2 deferred: sidebar auto-collapse (§8) logged to `docs/tech-debt.md` for T5

### What T2a shipped (d0be94f)
- New component: `frontend/components/dashboard/NarrativeHero.tsx`
- Placement: top of Executive Summary tab, above KPI cards (§9)
- Template composition only — no LLM, no server call, no new tokens
- Props: `hasAnalyzed`, `totalBarriers`, `highRiskCount`, `topBarrier`, `similarIncidentsCount`, `totalRetrievedIncidents`
- `similarIncidentsCount` = `explanation?.evidence_snippets?.length ?? 0` (from `/explain-cascading` response already in BowtieContext)
- `totalRetrievedIncidents` = 156 (fixed RAG corpus constant per §10)
- 4 edge cases handled in `composeNarrative`: no analysis, zero barriers, no high-risk, no similar incidents, empty topEvent
- 11 new tests; total: **182/182**
- UI-CONTEXT.md bumped v2.3 → v2.4; §9 amended with T2a/T2b composition split

### T2a wiring check (2026-04-20, same session)
**No bug.** `explanation?.evidence_snippets?.length ?? 0` is correct for T2a scope. The 0-count when no barrier is selected is intentional — `explanation` only fetches when `selectedTargetBarrierId` is set (user clicks a barrier). The "no comparable incidents" edge-case clause fires correctly until then. T2b will add a dedicated top-barrier RAG call.

### Deferred items
| Item | Location | Resolve when |
|------|----------|-------------|
| Sidebar auto-collapse to 48px strip (§8) | `docs/tech-debt.md` | T5 polish pass |
| 19 pytest ImportErrors (shap/xgboost env) | `docs/tech-debt.md` | pre-defense via `pip install -e .` |

### Decisions locked this session
- Hero placement: Analytics view → Executive Summary tab only (not persistent across all tabs — intentional, team ruling)
- `similarIncidentsCount` denominator: fixed at 156 (RAG corpus) not `evidence_snippets.length` — "X of 156" is more informative than "X of X"
- T2b design: opt-in "Summarize with AI" button, not auto-trigger; replaces template body with Haiku synthesis

### Branch state
- Branch: `milestone/M003-z2jh4m`
- All commits pushed to origin
- Tree clean
- Test count: **182/182** (Vitest) · Python pytest: 352 passing (19 pre-existing ImportErrors, not regressions)
