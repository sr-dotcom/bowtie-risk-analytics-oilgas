# Bowtie Risk Analytics — API Contract (S03)

**Version:** S03 (M003-z2jh4m)  
**Base URL:** `http://localhost:8000`

---

## Authentication

All endpoints except `/health` require an API key when `BOWTIE_API_KEY` is set in the environment.

```
X-API-Key: <your-key>
```

When `BOWTIE_API_KEY` is unset, authentication is disabled (development mode).

---

## Endpoints

### POST /predict-cascading

Predict barrier failure probability for all non-conditioning barriers in a scenario.
Returns SHAP reason codes alongside each prediction.

**Request**

```bash
curl -X POST http://localhost:8000/predict-cascading \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOWTIE_API_KEY" \
  -d '{
    "scenario": {
      "barriers": [
        {
          "control_id": "C-001",
          "barrier_level": "prevention",
          "lod_industry_standard": "Process Control",
          "lod_numeric": 1,
          "barrier_condition": "ineffective",
          "linked_threat_ids": ["T-001", "T-002"]
        },
        {
          "control_id": "C-002",
          "barrier_level": "prevention",
          "lod_industry_standard": "Structural Integrity",
          "lod_numeric": 2,
          "barrier_condition": "effective",
          "linked_threat_ids": ["T-001"]
        }
      ],
      "threats": [
        {"threat_id": "T-001", "name": "Overpressurization"},
        {"threat_id": "T-002", "name": "Valve failure"}
      ],
      "pif_context": {
        "work": {"procedures": true},
        "organisation": {"safety_culture": true}
      }
    },
    "conditioning_barrier_id": "C-001"
  }'
```

**Response 200**

```json
{
  "predictions": [
    {
      "target_barrier_id": "C-002",
      "y_fail_probability": 0.67,
      "risk_band": "MEDIUM",
      "shap_values": [
        {"feature": "lod_industry_standard_target", "value": 0.12, "display_name": ""},
        {"feature": "barrier_level_target", "value": -0.08, "display_name": ""},
        "..."
      ]
    }
  ],
  "explanation_unavailable": false
}
```

**Graceful degradation:** When the cascading model artifact is not loaded, returns `{predictions: [], explanation_unavailable: true}` with HTTP 200.

---

### POST /rank-targets

Lightweight ranking of non-conditioning barriers by failure probability. No SHAP values — suitable for dashboard hover/quick-preview.

**Request** — same shape as `/predict-cascading`.

```bash
curl -X POST http://localhost:8000/rank-targets \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOWTIE_API_KEY" \
  -d '{"scenario": {...}, "conditioning_barrier_id": "C-001"}'
```

**Response 200**

```json
{
  "ranked_barriers": [
    {"target_barrier_id": "C-002", "composite_risk_score": 0.67},
    {"target_barrier_id": "C-003", "composite_risk_score": 0.41}
  ]
}
```

Barriers are sorted by `composite_risk_score` descending. Returns `[]` on model load failure.

---

### POST /explain-cascading

Build RAG evidence narrative for a specific (conditioning, target) barrier pair.
RAG-only — does not call an LLM. SHAP values come from `/predict-cascading`.

**Request**

```bash
curl -X POST http://localhost:8000/explain-cascading \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOWTIE_API_KEY" \
  -d '{
    "conditioning_barrier_id": "C-001",
    "target_barrier_id": "C-002",
    "bowtie_context": {
      "top_event": "Fire from overpressurization",
      "context": {"operating_phase": "production", "materials": ["natural gas"]},
      "barriers": [...],
      "threats": [...],
      "pif_context": {"work": {"procedures": true}}
    }
  }'
```

**Response 200**

```json
{
  "narrative_text": "## Conditioning Barrier — Similar Failures\n\n...\n\n## Target Barrier — Similar Failures\n\n...",
  "evidence_snippets": [
    {
      "incident_id": "bsee_123",
      "source_agency": "BSEE",
      "text": "Barrier family: pressure_relief (RRF score: 0.0312)",
      "score": 0.0312
    }
  ],
  "degradation_context": {
    "pif_mentions": ["work.procedures", "organisation.safety_culture"],
    "recommendations": [
      "Establish a documented mechanical integrity program.",
      "Review inspection intervals for pressure safety valves."
    ],
    "barrier_condition": "ineffective"
  },
  "narrative_unavailable": false
}
```

**Graceful degradation:** When RAG v2 corpus is not loaded, returns `narrative_unavailable: true` with empty arrays.

---

### GET /health

Service health status.

```bash
curl http://localhost:8000/health
```

**Response 200**

```json
{
  "status": "ok",
  "models": {
    "cascading": {"name": "xgb_cascade_y_fail", "loaded": true},
    "rag_v2": {"name": "rag_v2", "loaded": true}
  },
  "rag": {"corpus_size": 526},
  "uptime_seconds": 42.3
}
```

---

### GET /apriori-rules

Pre-computed Apriori barrier co-failure association rules.

```bash
curl http://localhost:8000/apriori-rules -H "X-API-Key: $BOWTIE_API_KEY"
```

**Response 200**

```json
{
  "rules": [
    {
      "antecedent": "pressure_relief",
      "consequent": "alarm",
      "support": 0.072,
      "confidence": 0.732,
      "lift": 1.42,
      "count": 52
    }
  ]
}
```

Returns `{"rules": []}` when the artifact is absent.

---

### GET /predict (410 Gone)

Permanently removed. Migrate to `/predict-cascading`.

```bash
curl http://localhost:8000/predict
# HTTP 410
# {"error": "gone", "migrate_to": "/predict-cascading"}
```

### GET /explain (410 Gone)

Permanently removed. Migrate to `/explain-cascading`.

```bash
curl http://localhost:8000/explain
# HTTP 410
# {"error": "gone", "migrate_to": "/explain-cascading"}
```

---

## Error Codes

| Code | Meaning |
|------|---------|
| 200  | Success (including graceful degradation — check `explanation_unavailable` / `narrative_unavailable`) |
| 400  | Bad request — `conditioning_barrier_id` or `target_barrier_id` not found in scenario |
| 401  | Invalid or missing API key (only when `BOWTIE_API_KEY` is set) |
| 410  | Gone — endpoint permanently removed; follow `migrate_to` |
| 422  | Validation error — missing required field in request body |
| 500  | Internal server error — unexpected exception in model or RAG layer |

---

## Graceful Degradation Contract

Both `/predict-cascading` and `/explain-cascading` degrade gracefully:

| Condition | Endpoint | Behaviour |
|-----------|----------|-----------|
| `cascading_predictor` not loaded | `/predict-cascading` | `{predictions: [], explanation_unavailable: true}` HTTP 200 |
| `cascading_predictor` not loaded | `/rank-targets` | `{ranked_barriers: []}` HTTP 200 |
| `rag_v2_agent` not loaded | `/explain-cascading` | `{narrative_unavailable: true, evidence_snippets: [], ...}` HTTP 200 |
| Empty RAG retrieval | `/explain-cascading` | `narrative_unavailable: true` (but HTTP 200) |

Callers must check `explanation_unavailable` / `narrative_unavailable` before rendering results.
