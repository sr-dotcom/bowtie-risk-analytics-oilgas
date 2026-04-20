import type {
  AprioriRule,
  CascadingRequest,
  ExplainCascadingRequest,
  ExplainCascadingResponse,
  ExplainRequest,
  ExplainResponse,
  PredictCascadingResponse,
  RankTargetsResponse,
} from './types'

/**
 * POST /api/explain — retrieve RAG evidence, LLM narrative, and recommendations for a barrier.
 *
 * @deprecated Use explainCascading instead (S05a/T01). Retained until S05a/T06.
 *
 * @param payload - Barrier description and optional SHAP context.
 * @returns Evidence narrative with similar incident citations and recommendations.
 * @throws Error if the server returns a non-OK status.
 */
export async function explain(payload: ExplainRequest): Promise<ExplainResponse> {
  const res = await fetch('/api/explain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Evidence retrieval failed: ${res.status} ${res.statusText}`)
  return res.json() as Promise<ExplainResponse>
}

/**
 * GET /api/apriori-rules — retrieve pre-computed Apriori co-failure rules.
 *
 * @returns Array of AprioriRule objects sorted by confidence descending on the server.
 * @throws Error if the server returns a non-OK status.
 */
export async function fetchAprioriRules(): Promise<AprioriRule[]> {
  const res = await fetch('/api/apriori-rules')
  if (!res.ok) throw new Error(`Failed to load rules: ${res.status}`)
  const data = await res.json() as { rules: AprioriRule[] }
  return data.rules
}

// ---------------------------------------------------------------------------
// Cascading API client (S05a/T01)
// ---------------------------------------------------------------------------

/**
 * POST /api/predict-cascading — cascading barrier failure predictions with SHAP.
 *
 * Given a scenario and a conditioning barrier (assumed failed), returns
 * predicted failure probabilities for all other barriers in the scenario.
 *
 * @param payload - Full scenario + conditioning barrier ID.
 * @returns Per-target barrier predictions with risk bands and SHAP values.
 * @throws Error if the server returns a non-OK status.
 */
export async function predictCascading(payload: CascadingRequest): Promise<PredictCascadingResponse> {
  const res = await fetch('/api/predict-cascading', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Cascading prediction failed: ${res.status} ${res.statusText}`)
  return res.json() as Promise<PredictCascadingResponse>
}

/**
 * POST /api/rank-targets — lightweight barrier ranking without SHAP computation.
 *
 * Use for fast initial ranking when SHAP detail is not needed. Parallel-call
 * with predictCascading to get composite_risk_score ordering.
 *
 * @param payload - Full scenario + conditioning barrier ID.
 * @returns Ranked barrier list ordered by composite_risk_score descending.
 * @throws Error if the server returns a non-OK status.
 */
export async function rankTargets(payload: CascadingRequest): Promise<RankTargetsResponse> {
  const res = await fetch('/api/rank-targets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Rank targets failed: ${res.status} ${res.statusText}`)
  return res.json() as Promise<RankTargetsResponse>
}

/**
 * POST /api/explain-cascading — RAG evidence + degradation context narrative.
 *
 * Accepts an optional AbortSignal to cancel in-flight requests when the
 * selected target barrier changes (useExplainCascading pattern).
 *
 * @param payload - Conditioning + target barrier IDs and full scenario.
 * @param signal  - Optional AbortController signal for cancellation.
 * @returns Narrative text, evidence snippets, and degradation context.
 * @throws Error if the server returns a non-OK status.
 */
export async function explainCascading(
  payload: ExplainCascadingRequest,
  signal?: AbortSignal,
): Promise<ExplainCascadingResponse> {
  const res = await fetch('/api/explain-cascading', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!res.ok) throw new Error(`Cascading explanation failed: ${res.status} ${res.statusText}`)
  return res.json() as Promise<ExplainCascadingResponse>
}
