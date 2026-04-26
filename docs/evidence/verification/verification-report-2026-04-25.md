# Final Verification Report — 2026-04-25

**Branch:** milestone/M003-z2jh4m  
**Deployed at:** https://bowtie.gnsr.dev  
**Auditor:** Claude Code (automated browser + accessibility tree inspection)  
**Viewports tested:** 1268×800 · 1440×900 · 1920×1080  
**Hard cap:** 2 hours  
**Date:** 2026-04-25

---

## Summary

| Surface | Verdict | Notes |
|---------|---------|-------|
| Landing / Demo Load | PASS | Scenario loads, 7 barriers, SVG rendered |
| Executive Summary | PASS | All counts correct, risk posture correct |
| Drivers & HF | PASS | Global SHAP + Context Factors + Apriori table |
| Ranked Barriers (cold) | MINOR | Empty on cold load — requires barrier click |
| Ranked Barriers (populated) | PASS | 6/6 barriers, all columns, "What if fails?" works |
| Evidence Tab | PASS | Content loads, dropdown works, bold formatting |
| Diagram View | PASS | Risk coloring, SHAP annotations, layout correct |
| Pathway View | PASS | 6 prevention + 1 mitigation cards, risk badges |
| Detail Panel | PASS | SHAP waterfall + degradation chips + PIFs + RAG |
| ProvenanceStrip | PASS | All counts correct |
| Tab Persistence | PASS | Drivers & HF tab survives Diagram View round-trip |
| Console (fresh load) | PASS | 0 errors, 0 warnings |
| Performance | PASS | FCP 88ms, DOM complete 100ms |

**BLOCKER count:** 0  
**MINOR count:** 4  

---

## Phase 2 — Surface Walkthrough

### S1 — Landing / Demo Load
**Verdict: PASS**  
The BSEE demo scenario auto-loads on all three viewports. All 7 barriers appear in the sidebar list (6 prevention, 1 mitigation). The BowtieSVG renders with threat/consequence/top-event nodes. ProvenanceStrip visible at bottom.  
**Screenshot:** `00-phase1-landing-1440x900.png`

---

### S2 — Executive Summary
**Verdict: PASS**

- System narrative generates correctly ("7 barriers… 6 are high-risk… weakest link is Vessel structural integrity…")
- KPI cards: 7 barriers, 7 analyzed, High Risk posture (6H/0M/1L)
- Analysis Overview: `156` cascade training corpus, `113 BSEE · 19 CSB · 24 UNK` ✓
- Bar chart: 6 High, 1 Low ✓
- Top-3 at-risk list: "Barrier position in sequence" label visible (FA-4 confirmed ✓)
- Assessment Basis paragraph: 156 incidents, 813 pair-feature rows, AUC 0.76 ± 0.07 ✓

**Screenshots:** `01-exec-summary-{1268x800,1440x900,1920x1080}.png`

---

### S3 — Drivers & HF
**Verdict: PASS** (with MINOR)

- Global Feature Importance chart: "Target LoD tier" (2.171) > "Prevention barriers in incident" (0.763) > "Barrier position in sequence" (0.755) — FA-4 label fix confirmed ✓
- Degradation Context section: shows target barrier name, PIF chips, recommendations from similar incidents
- Co-failure Association Rules (Apriori): 16 rows ✓, "Based on Apriori analysis of 723 incident investigations" ✓

**MINOR:** "100%" label on Context Factors bar clips visually at 1440×900 and 1268×800, appearing as "100'" (text overflow into adjacent space). Cosmetic only.

**Screenshots:** `02-drivers-hf-{1268x800,1440x900,1920x1080}.png`

---

### S4 — Ranked Barriers
**Verdict: PASS** (MINOR for cold-load state)

**Cold-load state (before barrier click):**  
Table is empty. The explanatory text explaining that a barrier click is needed appears as a prompt. This is by design — `cascadingPredictions` only populates after `conditioningBarrierId` is set via a barrier click. The empty state is not labelled with a visible call-to-action header, which may confuse first-time presenters.  
**MINOR:** CTA guidance is present in the table placeholder but not prominently surfaced; demo presenter must know to click a barrier in Diagram View first.

**Populated state (after barrier click):**  
- Banner: "Cascading analysis: assuming [conditioner barrier] has failed" ✓
- Showing 6 of 6 barriers (clicked barrier excluded as conditioner) ✓
- All columns present: Barrier Name, Avg Cascade Risk, Recorded Condition, Top SHAP Factor, Type, LOD, Side, Cascade ✓
- Risk badges: 5 High, 1 Low ✓
- "What if fails?" button correctly re-runs analysis with that barrier as new conditioner ✓
- Filter dropdowns (All Sides / All Risk Levels / All Types) functional ✓

**Screenshots:** `03-ranked-barriers-*.png`, `03b-ranked-barriers-populated-*.png`, `03c-ranked-barriers-expanded-1920x1080.png`

---

### S5 — Evidence Tab
**Verdict: PASS** (with MINOR)

- Dropdown "Select target barrier" populated with 7 barriers (including risk band labels) ✓
- RAG context content loads showing conditioning-barrier section + target-barrier section ✓
- Bold formatting on "Incident Summary:", "Recommendations:", "Performance Influencing Factors (negative):" ✓
- Multiple parent incidents listed with RRF scores ✓

**MINOR:** Section headers in raw RAG context text appear as `## Conditioning Barrier — Similar Failures` with visible `##` prefix. The `SimpleMarkdown` component only handles `####` (h4) and `---` (hr); h2-level context headers are not rendered. Cosmetic — content fully readable.

**Screenshots:** `04-evidence-{1268x800,1440x900,1920x1080}.png`

---

### S6 — Diagram View
**Verdict: PASS**

- Barrier nodes color-coded by risk (red outlines = High, green outline = Low) ✓
- Top-2 SHAP factors annotated inside each barrier box (feature names + values) ✓
- "Barrier position in sequence" visible as annotation text (FA-4 confirmed ✓)
- Emergency response barrier shows "Target LoD tier" −2.17 annotation ✓
- Top event (red circle), threats (blue boxes), consequences (red boxes) all rendered ✓
- ProvenanceStrip at bottom ✓
- Large gray letterbox above diagram (known accepted AR artifact from M-4 investigation) — vertical whitespace intentionally preserved for dense scenarios

**Screenshots:** `05-diagram-{1268x800,1440x900,1920x1080}.png`

---

### S7 — Pathway View
**Verdict: PASS** (with MINOR)

- Two-column layout: PREVENTION PATHWAY (6 cards) + MITIGATION PATHWAY (1 card) ✓
- Each card: barrier name, role description, type chip, LOD chip, risk badge ✓
- Risk coloring matches Diagram View (6 High, 1 Low) ✓

**MINOR:** At 1268×800, long barrier names truncate mid-word (e.g., "Level Safety High (LSH) and Sight Ga..."). Expected at this narrow viewport — cards still fully functional.

**Screenshots:** `06-pathway-{1268x800,1440x900,1920x1080}.png`

---

### S8 — Detail Panel
**Verdict: PASS**

Triggered by clicking barrier in Diagram View. Panel opens as right-side drawer (560px wide).

- Barrier name + "Cascading analysis" subtitle ✓
- Risk badge: HIGH / "High reliability concern" / "Historical reliability assessment" ✓
- **Cascade Risk Factors (SHAP waterfall):** 10 features rendered, x-axis 0.00–2.60 ✓
  - Top feature: "Barrier position in sequence" (FA-4 fix confirmed ✓)
  - Red bars = positive risk contribution, Blue bars = negative ✓
- **DEGRADATION FACTORS:** PIF chips (situational awareness, procedures, tools equipment, safety culture, management of change) ✓
- **PERFORMANCE INFLUENCING FACTORS (NEGATIVE):** People/Work/Organisation breakdown ✓
- **ANALYSIS section:** RAG context text with bold incident refs, RRF scores, recommendations ✓
- Panel scrollable — full context text accessible ✓

**Screenshots:** `07-detail-panel-{1268x800,1440x900,1920x1080}.png`, `07c-detail-panel-rag-narrative-1440x900.png`

---

### S9 — ProvenanceStrip
**Verdict: PASS**

Visible at bottom of Diagram, Pathway, and Analytics views.  
Content verified:
- `Predictions: XGBoost cascade · 813 rows from 156 BSEE+CSB incidents · 5-fold CV AUC 0.76 ± 0.07` ✓
- `Evidence: hybrid RAG · 1,161 barriers · 156 incidents · 4-stage retrieval` ✓
- `View model card →` link present ✓

**Screenshot:** `08-provenance-strip-1440x900.png`

---

### S10 — Tab Persistence
**Verdict: PASS**

Test sequence: Analytics (click Drivers & HF) → Diagram View → Analytics  
Result: Dashboard opens on **Drivers & HF** tab (not defaulting to Executive Summary).  
The `BowtieContext` `activeTab` state is preserved across view mode transitions. ✓

**Screenshot:** `09-tab-persistence-1440x900.png`

---

## Phase 3 — Numbers Spot-Check

| Claim | Value | Verified |
|-------|-------|---------|
| Cascade training corpus | 156 incidents | ✓ (Executive Summary + ProvenanceStrip) |
| Provenance breakdown | 113 BSEE · 19 CSB · 24 UNK | ✓ (Executive Summary Analysis Overview) |
| Cascade training rows | 813 pair-feature | ✓ (ProvenanceStrip + Assessment Basis) |
| Apriori incident basis | 723 investigations | ✓ (Apriori table sub-header) |
| Apriori rule count | 16 rows | ✓ (table row count) |
| RAG barriers | 1,161 | ✓ (ProvenanceStrip) |
| RAG incidents | 156 | ✓ (ProvenanceStrip) |
| Model AUC | 0.76 ± 0.07 | ✓ (ProvenanceStrip) |
| FA-4: "Barrier position in sequence" | label | ✓ (SHAP waterfall, Global FI chart, barrier annotations) |

---

## Phase 4 — Performance & Console

**Fresh navigation to https://bowtie.gnsr.dev (1440×900):**

| Metric | Value |
|--------|-------|
| First Contentful Paint | 88ms |
| DOM Complete | 100ms |
| Load Event End | 100ms |
| HTML Transfer Size | 7KB (cached/CDN) |
| Console Errors | 0 |
| Console Warnings | 0 |

Performance is excellent. No hydration errors, no React warnings, no network errors.

---

## MINOR Issues Summary

| # | Location | Description | Severity |
|---|----------|-------------|----------|
| M1 | Drivers & HF — Context Factors | "100%" label clips to "100'" at ≤1440px viewports | Visual, cosmetic |
| M2 | Ranked Barriers cold load | Empty state with no prominent CTA — presenter must know to click a barrier first | UX, workflow |
| M3 | Evidence tab + Detail Panel ANALYSIS | RAG context `## section headers` render as literal `##` (SimpleMarkdown only handles h4/hr) | Cosmetic, readability |
| M4 | Pathway View @ 1268px | Barrier name truncation with ellipsis mid-word | Cosmetic, expected |

**All MINORs are cosmetic or known design trade-offs. None block the demo.**

---

## Conclusion

The milestone/M003-z2jh4m branch deployed at https://bowtie.gnsr.dev is **demo-ready**. All core flows (cascading analysis, SHAP explainability, RAG evidence, apriori rules, provenance) function correctly across all three tested viewports. No BLOCKERs found. Four cosmetic MINORs noted, none affecting demo integrity.

**Recommended pre-presentation steps:**
1. Click a barrier in Diagram View before switching to Analytics — this populates Ranked Barriers with cascading predictions
2. Be aware Ranked Barriers requires the barrier-click step (M2)

---

*Report generated: 2026-04-25 · Screenshots in `verification_screenshots_2026-04-25/`*
