# Post-Demo Fix List

Items deferred from the Four-Fix Sprint (2026-04-25).

> **⚠ SECURITY ACTION REQUIRED — rotate before any public release**
> The `.env` file at repo root contains a live `ANTHROPIC_API_KEY`.
> Although gitignored, the key must be rotated at console.anthropic.com before
> this repository or any derived image is shared publicly.  Added 2026-04-26.

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

## 3. SVG barrier overlap when barriers-per-row ≥ 3 (L001)

**Status:** Deferred to M005.

**Symptom:** When 3 or more barriers are assigned to the same threat row, barrier cards
overlap horizontally. The current layout allocates a fixed `BARRIER_W = 130` regardless
of how many cards must fit in the prevention zone.

**File:** `frontend/components/diagram/BowtieSVG.tsx`  
**Fix scope:** In `computeLayout()`, derive `boxWidth = Math.min(130, spacing - 4)` per row
where `spacing = availableWidth / barriersInRow`. Alternatively, cap barriers-per-row at 2
and render an overflow indicator (e.g., "+N more") for the remainder.  
**Estimated effort:** 1–2 hr  
**Milestone:** M005

---

## 4. Consequence node "?" badges on Explosive failure / Fire explosion (C6)

**Status:** Deferred to M005.

**Symptom:** The "Explosive failure of equipment" and "Fire / explosion" consequence nodes
show a "?" badge in the diagram even when consequence data is available. The badge logic
in BowtieSVG incorrectly falls through to the unknown-consequence branch for these nodes.

**File:** `frontend/components/diagram/BowtieSVG.tsx` — consequence badge assignment logic  
**Fix scope:** Audit the consequence-to-badge mapping; confirm all DEMO_CONSEQUENCES IDs
are matched correctly in the badge render path. ~1 hr.  
**Milestone:** M005

---

## 5. Verification MINORs carried forward from df506f1

**Status:** All four deferred to M005. Noted here so they are not lost between milestones.

**M1 — Context Factors "100%" clips at ≤ 1440px**  
The "100%" label in the Context Factors section truncates or clips at viewport widths ≤ 1440px.
Fix: adjust min-width or font-size in the relevant dashboard component.

**M2 — Ranked Barriers empty on cold load (superseded by Path A, retain workflow note)**  
Ranked Barriers tab showed empty state on cold load before the BSEE example was loaded.
Superseded by the Path A demo flow (Load BSEE example → Analyze → view Analytics), but
worth retaining the note: cold-load empty state should show a helpful placeholder, not a
blank panel, for any non-Path-A entry point.

**M3 — RAG `##` section headers render literally in Evidence tab**  
Evidence narrative text contains raw `## Section Title` markdown that is not converted to
HTML headings. Investigate post-Path-A whether the SimpleMarkdown renderer covers `##`;
if not, add `##` → `<h3>` handling to `SimpleMarkdown.tsx`.

**M4 — Barrier name truncation at 1268px viewport**  
Long barrier names truncate aggressively in the sidebar barrier list at 1268px width.
Fix: review Tailwind `truncate` / `min-w` classes on the barrier list item component.

---

## 6. Evidence tab conditioning barrier absent from dropdown

**Status:** Closed as design. Documented here for stakeholder reference.

**Finding:** The Evidence tab dropdown always shows N-1 barriers (never includes the
conditioning barrier). This is by API design: `/predict-cascading` returns predictions only
for *target* barriers — a barrier cannot be conditioned on itself. The UI correctly reflects
what the API returns. No code change needed.

**If the requirement changes** to show the conditioning barrier in the dropdown (with a "this
is the known-failed barrier" label), the fix is: switch the dropdown source from
`cascadingPredictions` to `scenario.barriers`, and render a static "conditioning barrier —
assumed failed" entry for the conditioning barrier ID with no prediction data.
