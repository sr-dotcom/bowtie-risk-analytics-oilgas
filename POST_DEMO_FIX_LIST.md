# Post-Demo Fix List

Items deferred from the Four-Fix Sprint (2026-04-25).

---

## 1. Per-incident dedup in RAG retrieval (EB-165 Fieldwood saturation)

**Status:** Deferred. Tracked here per sprint decision to keep Phase 4 to a single concern per commit.

**Symptom:** All 7 barriers in the Fieldwood demo scenario return the same incident
(`eb-165-a-fieldwood-09-may-2015`) dominating the top-3 evidence snippets. The scenario
*is* that incident, so self-match is expected — but showing the same incident 5–7× out of 10
results reduces evidence diversity.

**Root cause:** No deduplication at the incident level in `rag_agent.explain()` or
`pair_context_builder.build_pair_context()`. Each `RetrievalResult` is a unique
*barrier-control* match; multiple barriers from the same incident all rank highly.

**File:** `src/rag/pair_context_builder.py`  
**Scope:** ~5 lines — add a seen-incident set inside `build_pair_context`, keep only the
highest-RRF result per incident_id for each of conditioning and target result sets.

**Q&A prep (for demo audience):** If asked "why does all the evidence come from the same
incident?" — the answer is that the corpus is scoped to 156 offshore incidents from the same
operational domain, and this specific event is the closest semantic match. The retrieval is
working as designed; the training generality comes from the 156-incident diversity that shaped
the model weights, while the retrieval specificity zooms in on the most operationally similar
events. A deduplication pass is on the roadmap to surface a broader sample of similar
incidents, but relevance is deliberately prioritised over variety at this stage.

---

## 2. SVG annotation overflow: "Prevention barriers in incident" (30 chars)

**Status:** Deferred. User instruction: "NOT NOW. Defer. Phase 4 first."

**Symptom:** The SHAP waterfall label "Prevention barriers in incident" (30 chars) overflows
the 22-char truncation guard in `BowtieSVG.tsx` line 683. The truncation guard was designed
for the shorter `CASCADING_FEATURE_DISPLAY_NAMES` strings; this feature name is unusually long.

**File:** `frontend/components/diagram/BowtieSVG.tsx` line 683  
**Fix:** Shorten to "Prev. barriers (incident)" (25 chars) in `shap-config.ts`
`CASCADING_FEATURE_DISPLAY_NAMES` — or raise the truncation threshold to 28 chars.

---

## 3. Evidence tab conditioning barrier absent from dropdown

**Status:** Closed as design. Documented here for stakeholder reference.

**Finding:** The Evidence tab dropdown always shows N-1 barriers (never includes the
conditioning barrier). This is by API design: `/predict-cascading` returns predictions only
for *target* barriers — a barrier cannot be conditioned on itself. The UI correctly reflects
what the API returns. No code change needed.

**If the requirement changes** to show the conditioning barrier in the dropdown (with a "this
is the known-failed barrier" label), the fix is: switch the dropdown source from
`cascadingPredictions` to `scenario.barriers`, and render a static "conditioning barrier —
assumed failed" entry for the conditioning barrier ID with no prediction data.
