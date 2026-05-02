# Live Browser Audit — Chrome DevTools — 2026-04-24

> **Status update (2026-05-01):** This audit captures the system state on 2026-04-24. Items flagged DEMO-BLOCKING and HIGH below have since been triaged. See `docs/audits/STATUS_ADDENDUM.md` for current resolution state of each finding.

**Branch under test:** `milestone/M003-z2jh4m`  
**Frontend commit:** `dcae9ec` · **API commit:** `11304f5`  
**Live URL:** `https://bowtie.gnsr.dev`  
**Auditor:** chrome-devtools-mcp interactive live audit (phases 0–13)  
**Run timestamp:** 2026-04-24 (multi-session, context-resumed)  
**Effective viewport:** 1268×500 (target 1440×900; DevTools panel consumed ~172px height — audit-environment constraint, not product bug)  
**Scenario tested:** Fire from overpressurization and rupture of fuel gas filter vessel (7 barriers, all pre-loaded)

---

## DEMO-BLOCKING

### DB-1 · Apriori Co-failure Rules table always empty

**Tab:** Analytics → Drivers & HF → Co-failure Association Rules  
**Symptom:** Table headers (ANTECEDENT / CONSEQUENT / CONFIDENCE / SUPPORT / LIFT / COUNT) rendered but zero rows. Banner reads "Based on Apriori analysis of **0** incident investigations."  
**API confirmation:** `GET /api/apriori-rules` → HTTP 200, body `{"rules":[],"n_incidents":0,"generated_at":""}`.  
**Root cause (ultrareview bug_015):** `apriori_rules.json` is not copied into the Docker API image at runtime. The file exists on the build host but is excluded from the `Dockerfile.api` COPY stage. The endpoint returns an empty structure rather than 404.  
**Same section appears in:** Drivers & HF tab → Co-failure Association Rules (also 0 rows).  
**Fix required before demo:** Add `apriori_rules.json` to the `Dockerfile.api` COPY step and rebuild.

---

## HIGH

### H-A · Evidence tab: ANALYSIS block renders raw markdown

**Tab:** Analytics → Evidence  
**Symptom:** The ANALYSIS section displays unrendered markdown: `## Conditioning Barrier — Similar Failures`, `**Barrier:** Hazard Analysis Program`, `---` separator lines, `**Role:** ...` all visible as literal characters. The block is populated (scrollHeight 3097px of content) but no markdown→HTML rendering occurs.  
**Impact:** In a live demo to domain experts, raw markup immediately signals a rendering defect. The evidence narrative is the primary proof-of-concept for the RAG pipeline.  
**Fix required:** Pipe the ANALYSIS string through a markdown renderer (e.g. `react-markdown`) before display.

### H-B · PIF chips display raw dot-notation keys

**Tabs:** Analytics → Drivers & HF (Degradation Context) and Analytics → Evidence  
**Symptom:** Performance-Influencing Factor chips show internal key paths:
- `people.situational_awareness`
- `work.procedures`
- `work.tools_equipment`
- `organisation.safety_culture`
- `organisation.management_of_change`

instead of human-readable display names ("Situational Awareness", "Procedures", etc.).  
**Impact:** Domain audience sees Python dict-path syntax; immediate credibility gap.  
**Fix required:** Map dot-notation keys to display labels before rendering (mapping table likely already exists in `configs/` or `src/api/mapping_loader.py`).

### H-C · Pathway View: mode toggle overlaps heading

**Tab:** Pathway View (after analyzeAll)  
**Symptom:** The mode-toggle button (`position: absolute; top: 0.75rem; right: 0.75rem; z-index: 20`) visually overlaps the "MITIGATION PATHWAY" column heading at the current viewport width in the two-column layout.  
**Impact:** Heading text is partially obscured; toggle affordance is ambiguous.  
**Fix required:** Reserve heading-right space for the toggle, or position toggle outside the heading row.

---

## MEDIUM

### M-1 · Provenance strip absent from Diagram and Pathway views

**Spec ref:** UI-CONTEXT §10 — "persistent footer strip on all views"  
**Symptom:** The `<footer>` element is not in the DOM at all in Diagram View or Pathway View (conditional render, not CSS-hidden). It only mounts inside the Analytics sub-tree.  
**Impact:** Audience cannot verify data provenance while looking at the diagram or pathway — the primary interaction surfaces.  
**Fix required:** Move the provenance strip into the root layout so it renders on all views.

### M-2 · PIF Prevalence chart absent from Drivers & HF

**Spec ref:** CLAUDE.md `DriversHF.tsx` — "Global SHAP chart, PIF prevalence chart, Apriori rules table"  
**Symptom:** The Drivers & HF tab contains only: Global Feature Importance + Degradation Context + Co-failure Association Rules. No PIF Prevalence chart section exists in the DOM.  
**Impact:** Fleet-level PIF frequency is a key stakeholder metric listed in the component spec but not surfaced.  
**Question for user:** Intentionally removed in M003, or a regression? (See Questions section.)

### M-3 · Condition label mismatch between Ranked Barriers and Drivers & HF

**Symptom:** For "Single-stage pressure reduction system":
- Ranked Barriers table → Condition column: **degraded**  
- Drivers & HF → Degradation Context banner: **condition: ineffective**

Both views label the field "condition" with no disambiguation.  
**Root cause:** Ranked Barriers shows the cascade model's predicted condition class; Drivers & HF shows the `barrier_status` field from the bowtie JSON. These are different data sources using the same label.  
**Impact:** Contradictory condition information shown in the same session without explanation.  
**Fix required:** Label disambiguation ("predicted condition" vs. "reported condition") or use a single source.

### M-4 · SVG container aspect ratio mismatch (large blank bands)

**Tab:** Diagram View  
**Symptom:** BowtieSVG renders 936×231px content inside a 936×476px container due to `xMidYMid meet` with mismatched container aspect ratio. Approximately 245px of blank space split above/below the diagram.  
**Impact:** The diagram appears to float in a large void; wastes vertical space in a 500px-tall effective viewport.  
**Fix:** Set container height to match intrinsic SVG aspect ratio (1800:444 ≈ 4.05:1), or switch to `xMidYMid slice`/`preserveAspectRatio="none"` with appropriate padding.

### M-5 · Analytics sub-tab selection resets on view switch

**Symptom:** Navigating Analytics → Drivers & HF → Diagram View → Analytics returns to Executive Summary, losing the previously selected sub-tab. Evidence content is preserved (correct) but the sub-tab pointer resets to default.  
**Impact:** Minor friction in demo flows that revisit the diagram mid-presentation.  
**Fix:** Persist the last active analytics sub-tab in context state alongside the view toggle.

### M-6 · SHAP y-axis labels wrap to 3 lines

**Tab:** Ranked Barriers (expanded row) and Detail Panel  
**Symptom:** Feature labels like "Prevention barriers in incident" render as three stacked lines ("Prevention / barriers in / incident") due to narrow label area. All labels are technically present (H-3 is fixed) but cramped.  
**Impact:** Readable but not polished; label area may need 20–30px additional width.

---

## LOW

### L-1 · Font-weight violations (multiple headings and labels)

**Spec:** UI-CONTEXT — only font-weight 400 and 500 permitted.  
**Observed `font-semibold` (600):**
- "ANALYSIS" section label in Evidence tab
- "Similar Incidents (10)" heading in Evidence tab
- "Global Feature Importance" heading in Drivers & HF
- "Degradation Context (from similar incidents)" heading in Drivers & HF
- "Co-failure Association Rules" heading in Drivers & HF
- Additional instances likely throughout (scan limited to visible view)

### L-2 · Cold SVG barrier risk-band color

**Spec:** `risk.unknown = #4A5568`  
**Observed:** `#CCC` (light gray) on barrier risk-band fill in the pre-analyze cold state.  
**Visible:** Phase 0–2 cold load; replaced by risk colors after analyzeAll().

### L-3 · Footer border uses `border.default` instead of `border.subtle`

**Spec:** `border.subtle = #1F2937`  
**Observed:** `border-top: 1px solid #2A3442` (`border.default`) on provenance strip.

### L-4 · "View model card →" opacity

**Spec:** opacity 0.5 (de-emphasized external link)  
**Observed:** opacity 1.0 (same visual weight as primary content).

### L-5 · Tab letter-spacing

**Spec:** 0.8px  
**Observed:** normal (0px)

### L-6 · Border-radius deviations

**Spec:** 4px for cards/buttons; 2px for pills  
**Observed:**
- Input fields and select elements: 6px
- Mode-toggle container: 8px
- Pathway View barrier cards: 8px

### L-7 · Top SHAP positive values: split token rendering

**Symptom:** Positive SHAP values render as two adjacent text nodes `"+"` and `"0.689"` (separate spans), while negative values render unified as `"-2.219"`. Visually consistent but structurally asymmetric.

### L-8 · Pathway View barrier card colors

**Spec:** bg `#151B24` (bg.surface), `border: 1px solid #1F2937` (border.subtle), border-radius 4px  
**Observed:** bg `#1A1D27` (off-palette), no border, border-radius 8px — three violations per card.

### L-9 · No page landmark regions

**Spec / WCAG 2.1 1.3.6:** Page should have `<main>`, `<nav>` landmarks.  
**Observed:** Only `<footer>` landmark exists (only in Analytics view). No `<main>`, no `<nav>`.  
**Impact:** Screen reader users cannot jump to main content or skip to navigation.

### L-10 · Risk filter uses color-coded internal values

**Observed:** The "All Risk Levels" dropdown uses option values `"red"` / `"amber"` / `"green"` instead of `"high"` / `"medium"` / `"low"`. No user-visible impact but non-semantic for future maintenance.

---

## ALREADY-KNOWN ITEMS CONFIRMED

| ID | Description | Status |
|---|---|---|
| **C-2** | Apriori rules empty — API returns `{"rules":[],"n_incidents":0}` | ✅ Confirmed. Root cause: `apriori_rules.json` missing from Docker runtime (ultrareview bug_015) |
| **C-4** | Evidence tab renders raw markdown | ✅ Confirmed. Full ANALYSIS block populated but unrendered |
| **H-1** | "7 analyzed" count badge in Executive Summary | ✅ FIXED in dcae9ec — shows correct count |
| **H-2** | "Top Barriers by Avg Cascade Risk" section empty | ✅ FIXED in dcae9ec — populates from `averageCascadingPredictions` after analyzeAll() |
| **H-3** | SHAP y-axis labels missing | ✅ FIXED in dcae9ec — labels present (wrap to 3 lines, see M-6) |
| **H-4** | Global Feature Importance chart unpopulated | ✅ FIXED in dcae9ec — shows top 3 features (Target LoD tier 2.171, Prevention barriers in incident 0.783, Target role 0.755) |

**Ultrareview findings (bugs 003, 005, 010, 011, 013):** Identified by the code-level reviewer; details in the original task notification. Bug 009 (CSB count discrepancy — see Questions) and bug 015 (Apriori Docker gap — see DB-1) are addressed above.

---

## POSITIVE FINDINGS

1. **All API calls return 200** — zero 4xx/5xx errors across the entire audit session (48 network requests logged).
2. **Zero console errors or warnings** — clean JS execution throughout all phases.
3. **Excellent page load performance** — TTFB 58ms, DOM interactive 168ms, full load 257ms (Cloudflare CDN).
4. **analyzeAll() cascade pipeline functional** — 7 parallel `/predict-cascading` calls fire correctly; SHAP values, risk tiers, and ranked list all update.
5. **"What if fails?" conditioning switch works** — correctly re-runs cascading analysis with the clicked barrier as the conditioning barrier; excludes it from the ranked list.
6. **Ranked Barriers sort + filter functional** — all 7 sortable columns work; sort indicator moves correctly; 3 filter dropdowns filter correctly; state preserved across operations.
7. **Inline SHAP waterfall renders cleanly** — expands within table row, 10 feature labels visible, no overflow into adjacent rows.
8. **Evidence content persists across view navigation** — ANALYSIS block and barrier selector survive Analytics → Diagram View → Analytics round-trip.
9. **Detail Panel RAG content populated** — Degradation Context + Recommendations text loaded from RAG evidence.
10. **BowtieSVG risk color coding correct** — barriers correctly color-coded by risk tier post-analysis; SHAP top-2 annotations visible on diagram nodes.
11. **Provenance strip content accurate** (when visible) — "813 rows from 156 BSEE+CSB incidents · 5-fold CV AUC 0.76 ± 0.07 · 1,161 barriers · 4-stage retrieval" all match spec.
12. **risk_thresholds.json client caching** — returns 304 Not Modified on subsequent loads; D006 thresholds applied consistently.

---

## QUESTIONS FOR USER

**Q1 — Provenance strip count discrepancy:**  
UI-CONTEXT §10 shows `"113 BSEE + 43 CSB"`. Live dashboard shows `"113 BSEE · 19 CSB · 24 UNK"`. Ultrareview bug_009 confirms the dashboard figure is correct. **Does UI-CONTEXT.md need updating to reflect 19 CSB + 24 UNK?**

**Q2 — PIF Prevalence chart:**  
CLAUDE.md lists `DriversHF.tsx` as containing a "PIF prevalence chart." The component is not rendered in the current build. **Is it intentionally removed for M003, or is it a regression that should be reinstated?**

**Q3 — Global Feature Importance top-N:**  
The GFI chart shows exactly 3 features. The cascade model has 18 features. **Is showing top-3 an intentional design decision, or should all significant features be shown?**

**Q4 — RAG corpus scope:**  
Top evidence results for oil/gas PSV barriers include incidents from AB Specialty Silicones (chemical plant, Waukegan IL) — a CSB investigation not involving oil/gas operations. **Is including the full CSB corpus (all process safety sectors) intentional, or should the RAG corpus be scoped to oil/gas incidents only?**

**Q5 — Pathway View mode toggle overlap:**  
At the current viewport width, the absolute-positioned mode toggle overlaps the "MITIGATION PATHWAY" column heading. **Is mobile/narrow-desktop support in scope for M003, or is 1440px+ the only supported viewport?**

---

## Appendix: Screenshot Index

| Phase | File | Description |
|---|---|---|
| Phase 2 | `audit-phase2-cold-load.png` | Cold load, pre-analyze |
| Phase 2 | `audit-phase2-analytics-cold.png` | Analytics view cold state |
| Phase 3 | `audit-phase3-after-analyze.png` | Post-analyzeAll diagram |
| Phase 3 | `audit-phase3-top-barriers.png` | Executive Summary top barriers |
| Phase 4 | `audit-phase4-drivers-hf.png` | Drivers & HF tab (prior session) |
| Phase 4 | `audit-phase4-global-feature-importance.png` | GFI chart |
| Phase 4 | `audit-phase4-top.png` | Analytics header KPIs |
| Phase 5 | `audit-phase5-ranked-after-click.png` | Ranked Barriers with conditioning |
| Phase 5 | `audit-phase5-ranked-barriers.png` | Ranked Barriers full view |
| Phase 5 | `audit-phase5-shap-waterfall.png` | SHAP waterfall in detail panel |
| Phase 6 | `audit-phase6-drivers-hf-reconditioned.png` | Drivers & HF reconditioned |
| Phase 7 | `audit-phase7-apriori-table.png` | Apriori 0-row table |
| Phase 7 | `audit-phase7-evidence-tab.png` | Evidence raw markdown |
| Phase 7 | `audit-phase7-ranked-expanded.png` | Ranked Barriers expanded row + SHAP |
| Phase 8 | `audit-phase8-drivers-hf.png` | Drivers & HF post-dcae9ec |
| Phase 8 | `audit-phase8-drivers-hf-full.png` | Drivers & HF full page |
| Phase 9 | `audit-phase9-evidence.png` | Evidence tab with raw markdown |

Screenshots for phases 0–7 were captured during the first session; phases 7–9 in the resumed session. All files located at project root.

---

*Audit complete. Next action: fix DB-1 (Apriori Docker), H-A (markdown render), H-B (PIF display names), H-C (toggle overlap) before the next stakeholder demo.*
