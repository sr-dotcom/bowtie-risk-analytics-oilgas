# Diagnosis: /predict-cascading silent failure for user-built scenarios

**Date:** 2026-04-27  
**Severity:** Critical (May 16 demo path broken)  
**Status:** Diagnosed, not yet patched

---

## Root Cause (one sentence)

`useAnalyzeBarriers.ts:30` silently returns when `scenario === null`, and `scenario` is only ever set by `loadBSEEExample()` — `addBarrier()` never calls `setScenario()`, so every user-built scenario is permanently null and no API call is ever fired.

---

## Evidence

### Frontend: the guard that kills the call

**`frontend/hooks/useAnalyzeBarriers.ts:30`**
```typescript
if (barriers.length === 0 || !scenario) return
```

This early-return is hit 100% of the time for user-built scenarios because `scenario` is never populated by the form path. No error is set, no fetch fires, `isAnalyzing` never flips — the UI appears to do nothing.

### Frontend: scenario is only set by one code path

**`frontend/context/BowtieContext.tsx:156–159`** — `addBarrier()` (used by BarrierForm):
```typescript
function addBarrier(b: Omit<Barrier, 'id' | 'riskLevel'>): void {
  const newBarrier: Barrier = { ...b, id: crypto.randomUUID(), riskLevel: 'unanalyzed' }
  setBarriers((prev) => [...prev, newBarrier])
  // ← setScenario() is NEVER called here
}
```

**`frontend/context/BowtieContext.tsx:202–217`** — `loadBSEEExample()` (the only working path):
```typescript
function loadBSEEExample(): void {
  if (barriers.length > 0) return
  setEventDescription(BSEE_DEMO_SCENARIO.top_event)
  BSEE_DEMO_SCENARIO.barriers.forEach((sb: ScenarioBarrier) => {
    addBarrierWithId({ id: sb.control_id, ... })
  })
  setScenario(BSEE_DEMO_SCENARIO)   // ← only place setScenario is called outside Provider props
}
```

`setScenario` is also exposed as a context method but is only invoked from `loadBSEEExample()` and test setup — never from the user's form submission path.

### Frontend: the hook uses b.id as conditioning_barrier_id

**`frontend/hooks/useAnalyzeBarriers.ts:43–46`**
```typescript
barriers.map((b) =>
  predictCascading({ scenario, conditioning_barrier_id: b.id })
```

For demo barriers, `b.id` was set from `sb.control_id` via `addBarrierWithId`, so it matches `scenario.barriers[].control_id`. For user barriers, `b.id` is a UUID from `crypto.randomUUID()` that has no counterpart in any scenario.

### Backend: what the API actually looks for

**`src/modeling/cascading/predict.py:248–255`**
```python
for barrier in scenario.get("barriers", []):
    if barrier.get("control_id") == conditioning_barrier_id:
        continue
    ...
    predictions.append(BarrierPrediction(
        target_barrier_id=barrier["control_id"],
        ...
    ))
```

**`src/modeling/cascading/predict.py:159–163`** (`_build_pair_features`):
```python
barrier_ids = [b.get("control_id") for b in barriers]
target_id = target.get("control_id")
cond_id = conditioning.get("control_id")
target_idx = barrier_ids.index(target_id) if target_id in barrier_ids else 0
```

**`src/modeling/cascading/predict.py:155`** (for scenario-level stats):
```python
prev_count = sum(1 for b in barriers if b.get("barrier_level") == "prevention")
```

The API reads `control_id` and `barrier_level` from scenario barrier dicts. It does NOT read `id` or `side`. The `Barrier` type in the frontend uses `id` and `side` — these are the wrong keys for the API's scenario contract.

### API schema

**`src/api/schemas.py:244–250`**
```python
class CascadingRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    scenario: dict  # full bowtie config per data/demo_scenarios/*.json shape
    conditioning_barrier_id: str
```

`scenario` is a required non-nullable `dict`. If `null` were sent, FastAPI would return HTTP 422.

---

## Two-layer bug summary

| Layer | What the broken path does | What the working (BSEE demo) path does |
|-------|--------------------------|---------------------------------------|
| `scenario` state | Always `null` after `addBarrier()` | Set to `BSEE_DEMO_SCENARIO` by `loadBSEEExample()` |
| `analyzeAll()` guard | `!scenario` → returns immediately, no fetch | `scenario` is populated, guard passes |
| `conditioning_barrier_id` | `b.id` (UUID) — no scenario to look it up in | `b.id` === `control_id` set by `addBarrierWithId` |
| Scenario barrier field | Would need `control_id` and `barrier_level` | `control_id` and `barrier_level` present in `BSEE_DEMO_SCENARIO` |

The primary failure is Layer 1 (null guard). Layer 2 (field names) would surface as a backend 500 only after Layer 1 is fixed, because the synthetic scenario built from `Barrier[]` must map `id→control_id` and `side→barrier_level`.

---

## Proposed minimal patch (unified diff — DO NOT APPLY)

The patch is in `frontend/hooks/useAnalyzeBarriers.ts`. When `scenario` is null, build a synthetic `Scenario` from the current `barriers` array and `eventDescription` rather than aborting. The synthetic scenario uses `barrier.id` as `control_id` and maps `side` → `barrier_level`, which keeps `conditioning_barrier_id: b.id` aligned with `scenario.barriers[].control_id`.

```diff
--- a/frontend/hooks/useAnalyzeBarriers.ts
+++ b/frontend/hooks/useAnalyzeBarriers.ts
@@ -1,7 +1,7 @@
 'use client'
 
 import { useBowtieContext } from '@/context/BowtieContext'
 import { predictCascading } from '@/lib/api'
 import { mapProbabilityToRiskLevel } from '@/lib/riskScore'
 import { getFeatureDisplayName } from '@/lib/shap-config'
-import type { BarrierPrediction, RiskThresholds } from '@/lib/types'
+import type { BarrierPrediction, RiskThresholds, Scenario } from '@/lib/types'
 
@@ -20,7 +20,7 @@ export function useAnalyzeBarriers(): { analyzeAll: () => Promise<void> } {
   const {
     barriers,
     scenario,
+    eventDescription,
     setIsAnalyzing,
     setAnalysisError,
     updateBarrierCascading,
   } = useBowtieContext()
 
   async function analyzeAll(): Promise<void> {
-    if (barriers.length === 0 || !scenario) return
+    if (barriers.length === 0) return
+
+    // Use the pre-loaded scenario (BSEE demo / any setScenario caller), or
+    // synthesise one from the user-built barrier list so the API can proceed.
+    const activeScenario: Scenario = scenario ?? {
+      scenario_id: 'user-scenario',
+      source_agency: 'UNKNOWN',
+      incident_id: 'user-scenario',
+      top_event: eventDescription || 'User-defined scenario',
+      barriers: barriers.map((b) => ({
+        control_id: b.id,
+        name: b.name,
+        barrier_level: b.side,         // 'prevention' | 'mitigation' — matches API
+        barrier_condition: 'effective', // default; API forces conditioner to 'ineffective'
+        barrier_type: b.barrier_type,
+        barrier_role: b.barrierRole,
+        line_of_defense: b.line_of_defense,
+      })),
+      threats: [],
+    }
 
     setIsAnalyzing(true)
     setAnalysisError(null)
 
     try {
       const thresholdsRes = await fetch('/risk_thresholds.json')
       const thresholds: RiskThresholds = await thresholdsRes.json()
 
       const runs = await Promise.all(
         barriers.map((b) =>
-          predictCascading({ scenario, conditioning_barrier_id: b.id })
+          predictCascading({ scenario: activeScenario, conditioning_barrier_id: b.id })
             .then((res) => ({ conditionerId: b.id, predictions: res.predictions }))
             .catch(() => ({ conditionerId: b.id, predictions: [] as BarrierPrediction[] }))
         )
       )
```

**Lines changed:** ~18 lines added/modified in `useAnalyzeBarriers.ts`.  
**Rebuild:** Next.js hot-reload in dev (instant); production needs `npm run build` + container redeploy (~3–5 min with GHA pipeline).

---

## Risk assessment: does the patch break the BSEE demo?

**Risk: LOW.**

The patch introduces:
```typescript
const activeScenario: Scenario = scenario ?? { ... synthetic ... }
```

For the BSEE demo: `scenario` is `BSEE_DEMO_SCENARIO` (truthy), so the `??` short-circuits and `activeScenario === BSEE_DEMO_SCENARIO` exactly. The rest of the function is unchanged. The demo codepath is structurally identical to today.

The only change for the demo path is the variable rename from `scenario` to `activeScenario` in the `predictCascading` call — same reference, same value.

---

## Reproducing curl: what the broken frontend would send if the guard were removed

The broken frontend never fires a request (it returns before `fetch`). To triangulate from the API side, send `scenario: null` (what would be serialized if the guard were removed and the null sent directly):

```bash
curl -s -X POST https://bowtie-api.gnsr.dev/predict-cascading \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": null,
    "conditioning_barrier_id": "550e8400-e29b-41d4-a716-446655440000"
  }' | jq .
```

Expected API response (HTTP 422 Unprocessable Entity):
```json
{
  "detail": [
    {
      "type": "dict_type",
      "loc": ["body", "scenario"],
      "msg": "Input should be a valid dictionary",
      "input": null,
      "url": "https://errors.pydantic.dev/2.x/v/dict_type"
    }
  ]
}
```

This confirms the API requires a non-null dict for `scenario`. The fact that users see **nothing** (not even an error toast) means the frontend never reaches `fetch` — the null guard at `useAnalyzeBarriers.ts:30` is the terminal failure point.

---

## Test coverage: would existing tests have caught this?

**No.**

- **`BowtieContext.test.tsx`**: Tests cascading state via `setScenario` + `setConditioningBarrierId` directly (the `SetupCascading` helper). Never exercises `addBarrier → analyzeAll`. The `analyzeAll` hook (`useAnalyzeBarriers`) is not tested at all.

- **`api.test.ts`**: Tests the wire format of `predictCascading` using a pre-built `STUB_SCENARIO`. Does not test the case where `scenario` is null or the integration between `addBarrier` and `analyzeAll`.

- **No test file exercises the path:** `addBarrier() → handleAnalyze() → analyzeAll()` with `scenario === null`.

A test that would have caught this:
```typescript
it('analyzeAll does not return early when scenario is null (user-built barriers)', async () => {
  // render BowtieProvider, call addBarrier(...), then analyzeAll()
  // assert that predictCascading was called at least once
})
```

---

## Recommendation

**Apply now (before May 16).** The patch is:
- 18 lines in a single file
- Zero risk to the BSEE demo regression boundary
- No schema changes (API contract is unchanged)
- No new dependencies
- Hot-reloads in dev; production rebuild ~3–5 min

The alternative (Path B fallback — demo-only with BSEE example) abandons the core "custom scenario" use case that the BarrierForm UI was built to support. Given patch effort is low and demo risk is low, applying now is the right call.

The one caveat: after this fix, a secondary UX gap may surface — the user-built scenario has no `threats` array, so `_flag_features_from_scenario` returns all zeros for flag features. Predictions will still be returned (the model handles this gracefully with 0-valued features), but quality may be lower than for the seeded demo. This is acceptable for the May 16 demo.
