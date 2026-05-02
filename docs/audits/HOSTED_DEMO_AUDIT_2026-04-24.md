# Hosted Demo Audit — 2026-04-24

> **Status update (2026-05-01):** This audit captures the system state on 2026-04-24. Items flagged DEMO-BLOCKING and HIGH below have since been triaged. See `docs/audits/STATUS_ADDENDUM.md` for current resolution state of each finding.

**Auditor:** Playwright automated audit (Phase 7)  
**Run timestamp:** 2026-04-24T01:36:18Z → 2026-04-24T01:38:12Z (1m 54s wall clock)  
**Audit script:** `frontend/tests-e2e/audit-2026-04-24.spec.ts`  
**Screenshots:** `docs/audits/screenshots/2026-04-24/`

---

## 1. Executive Summary

| | |
|---|---|
| **Demo readiness** | 🟡 YELLOW |
| **Rationale** | Core prediction and cascade ranking flow works end-to-end on desktop. Three content gaps (Apriori rules empty, Drivers & HF charts unpopulated, Evidence tab renders raw markdown) are audience-visible and would confuse domain experts without narration. Mobile is completely broken. |
| **Critical blockers** | 4 |
| **Notable issues** | 4 |
| **Cosmetic issues** | 4 |

**One-line demo verdict:** Safe to demo the core path (Diagram → barrier click → Analyze → Ranked Barriers → SHAP); avoid Drivers & HF, mobile, and deep Evidence drill-down.

---

## 2. Environment Verified

| Property | Value |
|---|---|
| Frontend URL | `https://bowtie.gnsr.dev` — HTTP 200 |
| API URL | `https://bowtie-api.gnsr.dev/health` — HTTP 200 |
| API status | `{"status":"ok","models":{"cascading":{"loaded":true},"rag_v2":{"loaded":true}},"rag":{"corpus_size":1161}}` |
| API uptime at audit | 906s (15 min since container start) |
| Desktop viewport | 1920×1080 |
| Mobile viewport | 390×844 |
| Playwright version | 1.59.1 (Chromium) |
| Page title | "Bowtie Risk Analytics" |
| Desktop initial load | 798ms (domcontentloaded) |
| Console errors | **0** |
| API network calls captured | 0 (see §7 — listener covered wrong host) |

---

## 3. Per-Tab Findings

### 3.1 Diagram View (default landing state)

**Screenshot:** `01a_desktop_cold_load.png`, `03a_diagram_view.png`

✅ **Loads correctly.** The bowtie SVG renders immediately on cold load with all 7 barriers plus 3 threat nodes, 1 top event, and 3 consequence nodes. Barrier boxes are labelled and truncated appropriately. The sidebar (left) shows scenario text, Add Barrier form, barrier list, Human Factors checkboxes. Buttons present: Prevention, Mitigation, Add Prevention Barrier, Analyze Barriers, New Scenario, Diagram View, Pathway View, Analytics.

After `analyzeAll()` runs (502ms), barriers receive risk-colored overlays on the SVG — visually distinguishes high/low risk on the diagram.

**Issues:**
- No `<h1>` element on page — heading hierarchy starts at `<h2>` (accessibility gap, minor)
- 7 icon-only buttons with empty label strings captured (e.g., Remove barrier buttons) — no `aria-label`

### 3.2 Executive Summary tab

**Screenshot:** `02a_tab_executive_summary.png`

✅ Loads immediately after clicking Analytics. Key elements present:
- System narrative text (auto-generated): "This scenario has 7 barriers defending against Fire from overpressurization and rupture of fuel gas filter vessel. 6 are high-risk. The weakest link is Vessel structural integrity and corrosion management…"
- TOP EVENT / SCENARIO label and heading: "Fire from overpressurization and rupture of fuel gas filter vessel"
- Scenario Risk Posture card: "High Risk" badge, "6 high · 0 medium · 1 low risk barriers"
- Analysis Overview: 7 barriers, 6/1 Prevention/Mitigation, 156 corpus, 530 training rows
- Barrier Risk Distribution bar chart renders correctly: 6 High (red), 1 Low (green)
- Assessment Basis: M003 model details correct (156 BSEE+CSB incidents, AUC 0.76 ± 0.07)

**Issues:**
- **"7 barriers | 0 analyzed" badge** — after `analyzeAll()` completes, the "analyzed" count stays at 0. Audience sees this in the header. Expected: "7 analyzed." (`⚠️ Notable`)
- **"Top Barriers by Avg Cascade Risk" section empty** — shows "Run Analyze Barriers to compute Average Cascading Risk" even after analysis. This section requires `conditioningBarrierId` to be set (barrier must be clicked first), but the label implies `analyzeAll()` should populate it. (`⚠️ Notable`)

### 3.3 Drivers & HF tab

**Screenshot:** `02b_tab_drivers_hf.png`, `05b_scenario_c_drivers_hf_full.png`

⚠️ **Partially broken.** The tab renders with three named sections, but two of three have no content and the third has zero rows:

| Section | Status | Detail |
|---|---|---|
| Global Feature Importance | ❌ Empty | "Run Analyze Barriers to see feature importance" |
| PIF Prevalence in Top Drivers | ❌ Empty | "Run Analyze Barriers to see PIF prevalence" |
| Co-failure Association Rules | ❌ 0 rows | Table header renders; body empty. Caption: "Based on Apriori analysis of 0 incident investigations." |

The Global Feature Importance and PIF Prevalence charts are gated on `conditioningBarrierId`, which is only set when a user clicks a barrier. They do not populate from `analyzeAll()`. This is a design/UX gap — the tab feels broken on arrival.

The Apriori rules table is the more serious issue: even after barrier click and cascade mode is active, the table contains **0 rows**. The `/apriori-rules` endpoint appears to return empty results on the hosted instance. This data was present in prior local runs — likely a startup or data-file issue on the container.

**Verdict for demo:** ❌ **Do not show Drivers & HF tab.** Audience will see three empty sections.

### 3.4 Ranked Barriers tab — cold state

**Screenshot:** `02c_ranked_barriers_cold.png`

⚠️ **Known tech debt, confirmed.** Cold state shows:
> "No analyzed barriers yet — click Analyze Barriers to compute Average Cascading Risk."

The placeholder message is clear and actionable. After `analyzeAll()` + barrier click → cascade mode, the table populates correctly with 6 of 6 barriers (see §4). The cold state itself is not a blocker if the demo starts with diagram interaction.

### 3.5 Evidence tab — cold state

**Screenshot:** `02d_evidence_cold.png`

The Evidence tab renders a barrier selector dropdown ("Select target barrier") in cold state. No placeholder narrative or instruction text is visible — the page is mostly empty below the dropdown. The dropdown shows all 7 barriers with their risk labels (HIGH/LOW).

---

## 4. Bowtie Diagram Interaction Findings

**Screenshots:** `03b_barrier_1_hover.png` through `03c_barrier_3_clicked.png`, `04a_cascade_barrier_selected.png`

**Barrier count:** 7 SVG interactive elements confirmed.

**Hover behavior:** All 3 tested barriers respond to hover correctly. No tooltip visible on hover (native `title` attribute not rendered by headless Chromium — same known limitation as handoff spec).

**Click behavior:** All 3 barriers respond to click and open a detail panel on the right. The panel is rich:
- Barrier name heading
- "Conditioning address" / risk level badge ("High reliability concern")
- "Cascade Risk Factors" section with a horizontal SHAP bar chart (red = positive risk, blue = negative)
- PIF tags rendered (e.g., `people_situational_awareness`, `procedures`, `management_of_change`)
- RAG evidence section with "Similar Barrier Failures" — results 1–4 with RRF scores, parent incident IDs, evidence quotes

The detail panel in diagram view renders evidence from AB Specialty Silicones incident (correctly retrieved from RAG corpus). Content is clean and well-formatted in the panel context.

**Note on panel selector:** The audit CSS selector `[class*="DetailPanel"], [class*="DrawerPanel"]` did not match the actual class names in production build (Next.js minifies class names). Panel content was captured via the probability_texts scraper instead. This is an audit script limitation, not an app bug.

**Cascade mode setup:**
- After clicking barrier 1 ("Pressure Safety Valve on MBF-V940 Fuel Gas Scrubber"), pressing Escape, and navigating to Analytics, cascade mode activates correctly
- `conditioningBarrierId` = "Vessel structural integrity and corrosion management" (3rd barrier clicked in sequence, per fallback logic)
- Cascade header appears: "Cascading analysis: assuming **Vessel structural integrity and corrosion management** has failed"

---

## 5. User Journey Scenario Walk-Throughs

### Scenario A — "Domain expert evaluates a known barrier"

| Step | Outcome | Time |
|---|---|---|
| 1. Land on bowtie.gnsr.dev | ✅ Bowtie SVG renders, sidebar shows demo scenario | 798ms |
| 2. Already in Diagram View (default) | ✅ No action needed | — |
| 3. Click first prevention barrier | ✅ Detail panel opens with SHAP chart + RAG evidence | ~1.2s |
| 4. Click "Analyze Barriers" → Analytics | ✅ Analysis completes, dashboard populates | 502ms |
| 5. Navigate to Ranked Barriers | ⚠️ Cold state (no cascade) — empty table | — |
| 6. Click barrier (cascade setup) then return | ✅ Cascade header appears, 6 rows populated | ~3s |
| 7. Click "Evidence" tab | ⚠️ Evidence renders raw markdown — see §5 finding | 796ms |

**Friction:** The ordering in this scenario (click barrier, then Analyze, then cascade) is not obvious. A cold audience would likely click "Analyze Barriers" first, then click Analytics, and be confused by the "0 analyzed" badge and empty sections before clicking a diagram barrier. The state machine is not self-documenting.

### Scenario B — "Practitioner explores ranked failure modes"

| Step | Outcome | |
|---|---|---|
| 1. Ranked Barriers (cold) | ⚠️ Empty with placeholder text | Known tech debt |
| 2. Click barrier in diagram | ✅ Cascade mode activates | ~3s wait |
| 3. Return to Ranked Barriers | ✅ Table populates: 6 rows, High/Low badges, SHAP delta | |
| 4. Click row 1 to expand | ✅ SHAP waterfall renders | |
| 5. Inspect waterfall | ⚠️ **No y-axis feature labels** — bars present but unidentifiable | See §6 |

**Cascade table quality:** All 6 rows populated correctly — barrier names, risk tiers (5 High / 1 Low), condition (degraded/ineffective/effective), Top SHAP Factor delta (+0.689 to +0.889), type, LOD, side, "What if fails?" buttons. Sortable by risk. Filters (All Sides, All Risk Levels, All Types) functional. Clean, professional layout.

### Scenario C — "Skeptic verifies a claim via Drivers & HF"

| Step | Outcome | |
|---|---|---|
| 1. Click Drivers & HF tab | ⚠️ All three sections empty or zero rows | Critical gap |
| 2. Read Apriori rules | ❌ 0 rows, table completely empty | |
| 3. View feature importance | ❌ Placeholder: "Run Analyze Barriers…" | |

**Verdict:** This scenario fails entirely. Do not attempt in the demo.

---

## 6. Console Errors (Full List)

**Total console entries captured: 0**

No JavaScript errors, warnings, or suspicious log messages recorded during the full session. The frontend is clean at the browser console level.

---

## 7. Network Issues

**API calls to `bowtie-api.gnsr.dev` captured:** 0

The audit network listener filtered by hostname `bowtie-api.gnsr.dev`. The production frontend likely calls the API via a different mechanism — either a Next.js API route proxy (`/api/...` same-origin), a different hostname set in `NEXT_PUBLIC_API_URL`, or internal Docker networking. All API functionality confirmed working via rendered output (predictions, RAG evidence, cascade rankings), so the API is reachable — the audit trace simply did not capture the calls.

**Apriori rules issue:** The Apriori rules table caption reads "Based on Apriori analysis of **0** incident investigations." The `/apriori-rules` endpoint is responding but returning empty data. This is a data-loading issue in the deployed container, not a connectivity failure.

**Evidence load time:** 796ms from Evidence tab click to "Similar Incidents" text appearing. This is fast for an LLM synthesis call — consistent with either (a) RAG-only retrieval without LLM narrative synthesis, or (b) very fast model response. The evidence content renders in raw markdown format (see §8), suggesting the LLM synthesis step may be bypassed.

**Slow requests:** None observed (no requests captured, but all content loaded within test timeouts).

**CORS errors:** None.

---

## 8. Accessibility / Layout Issues

### Desktop Layout
**No overflow detected on any tab** (Executive Summary, Drivers & HF, Ranked Barriers all pass bounding box checks). Desktop layout is clean at 1920×1080.

### Mobile Layout (390×844) — CRITICAL
**Screenshot:** `01b_mobile_cold_load.png`

The mobile layout is **completely broken**. At 390px width:
- The left sidebar (dark panel with scenario editor, barrier list, Human Factors) occupies roughly the full left 300px
- The bowtie SVG canvas renders in the remaining ~90px strip to the right — showing only the right portion (consequence nodes: "Gas release / toxic exposure", "Explosive failure of equipment", "Fire / explosion")
- The top event center circle and all prevention barriers are completely off-screen to the left of the SVG canvas, not visible at all
- Both `body.scrollWidth > innerWidth` and `main.scrollWidth > innerWidth` confirmed true

**Impact:** App is non-functional on mobile. Any attendee attempting to follow along on a phone during the demo will see a broken layout.

### Evidence Panel — Raw Markdown
The Evidence tab renders the RAG context text as unprocessed markdown. Visible in screenshot `04d_evidence_rag_narrative.png`:
- Section headers appear as `## Conditioning Barrier — Similar Failures`
- Bold text appears as `**Barrier:** Double Initial Procedure Program`
- Separators appear as `---`

Domain experts reading this will see formatting syntax, not a readable narrative. The diagram-view barrier click panel (same session, different code path) does NOT have this issue — the panel renders evidence as structured clean text. The inconsistency is confusing.

### SHAP Waterfall — Missing Feature Labels
**Screenshot:** `04c_shap_waterfall.png`

The SHAP waterfall chart (Recharts) renders correctly as a cascading bar chart with red (positive risk contribution) and blue (negative) bars. The x-axis (0.00, 0.75, 1.50, 2.25, 3.00) renders correctly. The **y-axis feature name labels are absent** — bars float without identifiers. An audience member cannot tell which features are driving the prediction without knowing which bar corresponds to which feature.

---

## 9. Demo Readiness Assessment

**Intended audience:** Ageenko + Fidel

### What WILL work
- Cold page load — fast (798ms), looks professional
- Bowtie SVG renders with demo scenario pre-loaded (fire / overpressurization)
- "Analyze Barriers" → risk colors appear on diagram barriers (visual, impressive)
- Clicking a prevention barrier → right-side detail panel with SHAP chart + PIF tags + RAG evidence snippets. **This is the strongest demo moment.** The panel is clean, the evidence is readable, the AI provenance is clear.
- Analytics → Executive Summary: Scenario Risk Posture (HIGH, 6/1 distribution), barrier risk bar chart, model provenance — all render.
- Analytics → Ranked Barriers (after cascade setup): The 6-row ranked table is clean and professional. "What if fails?" buttons, filter dropdowns, sortable columns, cascade conditioning header.
- SHAP waterfall expansion: visually impressive even without labels — the red/blue cascade is clear to a technical audience.
- Footer provenance strip: "XGBoost cascade · 813 rows · 156 incidents · AUC 0.76 ± 0.07 / hybrid RAG · 1,161 barriers · 156 incidents · 4-stage retrieval" — solid credibility signal.

### What MIGHT confuse the audience
- "0 analyzed" badge in Executive Summary header — looks like a bug
- Clicking "Analytics" before clicking any barrier shows three sections with placeholder text in Drivers & HF
- The sequence of interactions required (barrier click → Escape → Analytics → Ranked Barriers) is not obvious — an experienced user follows it, but a first-time observer will be confused about what triggered the cascade
- Evidence tab dense markdown — readable if you explain it; confusing if you just show it

### What COULD break mid-demo
- Apriori rules table: already 0 rows — if this is a container-restart artifact it might recover, but cannot be guaranteed
- API cold-start: the container had 906s uptime at audit time. First request after long idle may be slow
- The detail panel (barrier click) is the most impressive feature — confirm it responds within ~2s on the demo machine/network

### Recommended demo path
1. **Start:** "Here's a demo scenario — overpressurization fire at a fuel gas filter vessel."
2. **Show:** Cold bowtie SVG — explain the 7 barriers, 3 threat paths.
3. **Click "Analyze Barriers"** — wait for colors to appear on the diagram. *"The model just ran cascade predictions for all 7 barriers simultaneously."*
4. **Click a prevention barrier** (e.g., "Pressure Safety Valve on MAK-F960B") — show the right-side panel. *"SHAP attribution, PIF tags, and RAG-retrieved evidence from 156 historical incidents."*
5. **Click "Analytics" → Ranked Barriers** — navigate after the cascade context is set. *"Here's everything ranked by cascading failure risk — conditioned on that PSV failing."*
6. **Expand row 1** — show SHAP waterfall. *"The top driver is [describe visible bars]."*
7. **Evidence tab** — only if necessary; briefly describe the RAG retrieval. Do not let audience read the raw markdown text closely.
8. **Skip:** Drivers & HF tab entirely.

### Topics to volunteer vs. avoid
| Volunteer | Avoid |
|---|---|
| "156 BSEE+CSB incidents in training" | "Click Drivers & HF" |
| "SHAP TreeExplainer — no black box" | Zooming into Evidence tab text |
| "4-stage hybrid RAG retrieval" | Mobile / phone view |
| "AUC 0.76 on 5-fold GroupKFold CV" | "0 analyzed" badge explanation |
| "RAG corpus: 1,161 barriers" | Apriori rules table |

---

## 10. Tech Debt Inventory

| # | Severity | Description | Suggested fix |
|---|---|---|---|
| 1 | 🔴 CRITICAL | Mobile layout completely broken at 390px — sidebar and SVG overlap, bowtie invisible | Add responsive breakpoints; collapse sidebar to drawer on mobile |
| 2 | 🔴 CRITICAL | Apriori rules table empty in hosted deployment ("0 incident investigations") | Check `/apriori-rules` endpoint; verify `out/association_mining/` data file is mounted in container |
| 3 | 🟠 HIGH | Drivers & HF — Global Feature Importance + PIF Prevalence empty after analyzeAll() | These charts need `conditioningBarrierId` — either populate from analyzeAll() average or add UX guidance |
| 4 | 🟠 HIGH | Evidence tab renders raw markdown (## headings, ** bold visible as text) | Add a markdown renderer (e.g. `react-markdown`) to the Evidence tab component |
| 5 | 🟠 HIGH | "0 analyzed" badge in Executive Summary doesn't update after analyzeAll() | Tie "analyzed" count to `Object.keys(averageCascadingPredictions).length` or equivalent state |
| 6 | 🟠 HIGH | "Top Barriers by Avg Cascade Risk" section empty after analyzeAll() | Populate from `averageCascadingPredictions` state; does not require conditioningBarrierId |
| 7 | 🟠 HIGH | SHAP waterfall missing y-axis feature name labels | Add `YAxis dataKey` with barrier feature name mapping to Recharts component |
| 8 | 🟡 MEDIUM | Network capture missed all API calls — NEXT_PUBLIC_API_URL may differ from `bowtie-api.gnsr.dev` | Document actual API call pattern; verify env var in deployed container |
| 9 | 🟡 MEDIUM | analyzeAll() completes in 502ms — verify actual /predict-cascading calls fire | Add API call log on the server side; confirm client is not returning cached state |
| 10 | 🟡 MEDIUM | Evidence load in 796ms suggests LLM synthesis may be bypassed | Check BarrierExplainer wiring in /explain-cascading endpoint; verify Anthropic API key is set in container |
| 11 | 🟢 LOW | No `<h1>` on page — heading hierarchy starts at h2 | Add "Bowtie Risk Analytics" h1 (visually hidden if needed) |
| 12 | 🟢 LOW | Icon-only buttons have empty text labels — no aria-label | Add `aria-label` to Remove Barrier and other icon buttons |

---

## Appendix: Screenshot Index

| File | Content |
|---|---|
| `01a_desktop_cold_load.png` | Desktop 1920×1080 cold load — full page |
| `01b_mobile_cold_load.png` | Mobile 390×844 cold load — layout broken |
| `01c_pre_analyze.png` | Pre-analysis state with Analyze Barriers enabled |
| `01d_analyze_triggered.png` | Immediately after Analyze Barriers clicked |
| `02a_tab_executive_summary.png` | Executive Summary — post-analysis |
| `02b_tab_drivers_hf.png` | Drivers & HF — all three sections empty |
| `02c_ranked_barriers_cold.png` | Ranked Barriers — cold placeholder state |
| `02d_evidence_cold.png` | Evidence tab — cold state with barrier selector |
| `03a_diagram_view.png` | Bowtie SVG post-analysis with risk colors |
| `03b_barrier_1/2/3_hover.png` | Hover state on first three barriers |
| `03c_barrier_1/2/3_clicked.png` | Barrier click — detail panel open |
| `04a_cascade_barrier_selected.png` | Cascade mode — conditioning barrier clicked |
| `04b_ranked_barriers_cascade.png` | Ranked Barriers in cascade mode — 6 rows |
| `04c_shap_waterfall.png` | SHAP waterfall — row 1 expanded, no labels |
| `04d_evidence_rag_narrative.png` | Evidence tab — raw markdown visible |
| `05a_scenario_b_ranked_full.png` | Ranked Barriers — full table view |
| `05b_scenario_c_drivers_hf_full.png` | Drivers & HF — scenario C view |
| `06_footer_provenance.png` | Footer provenance strip |
| `07_session_end_state.png` | Session end state |

| Data file | Content |
|---|---|
| `network-trace.json` | API request/response log (0 entries — listener host mismatch) |
| `console-log.json` | Console output (0 entries — no errors) |
| `meta.json` | All structured audit metadata |
