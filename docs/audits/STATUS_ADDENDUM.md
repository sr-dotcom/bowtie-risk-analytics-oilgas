# Audit Status Addendum

**Created:** 2026-05-01
**Purpose:** Map findings from `HOSTED_DEMO_AUDIT_2026-04-24.md` and `LIVE_AUDIT_CHROME_2026-04-24.md` to current resolution state for the Bowtiefy handoff package.

The two audit reports in this folder capture the system as it stood on 2026-04-24. Several findings flagged DEMO-BLOCKING or HIGH at that time have since been triaged. This document is the single source of truth for current status.

---

## Hosted Demo Audit (Playwright) — Tech Debt Inventory

| # | Severity | Finding | Current status | Resolution |
|---|---|---|---|---|
| 1 | 🔴 CRITICAL | Mobile layout broken at 390px | 🔴 Open | Documented in tech-debt; M005+ scope (multi-hour responsive rebuild) |
| 2 | 🔴 CRITICAL | Apriori rules table empty in hosted deployment | ✅ Resolved | Fixed in `bc10668 fix(deploy): ship apriori rules data file in API image`. Verified live: `/apriori-rules` returns populated rules array. |
| 3 | 🟠 HIGH | Drivers & HF charts empty after analyzeAll() | ✅ Resolved | Fixed in `dcae9ec fix(ui): populate global cascade views from analyzeAll(), label SHAP axes` |
| 4 | 🟠 HIGH | Evidence tab renders raw markdown | ✅ Resolved | Fixed in `ae41364 fix(ui): render RAG narrative as markdown in DetailPanel and EvidenceView` |
| 5 | 🟠 HIGH | "0 analyzed" badge doesn't update | ✅ Resolved | Fixed in `dcae9ec` |
| 6 | 🟠 HIGH | "Top Barriers by Avg Cascade Risk" empty | ✅ Resolved | Fixed in `dcae9ec` |
| 7 | 🟠 HIGH | SHAP waterfall missing y-axis labels | ✅ Resolved | Fixed in `dcae9ec`. Cosmetic follow-up (label wrap to 3 lines) tracked separately as M-6 below. |
| 8 | 🟡 MEDIUM | Network capture missed API calls (audit script env mismatch) | N/A | Audit-script artifact, not product behavior |
| 9 | 🟡 MEDIUM | analyzeAll() 502ms — verify calls fire | ✅ Resolved | Confirmed end-to-end in subsequent live Chrome audit |
| 10 | 🟡 MEDIUM | Evidence load 796ms — verify LLM synthesis active | ✅ Resolved | Confirmed via narrative content in live audit |
| 11 | 🟢 LOW | No `<h1>` on page | ✅ Resolved | Fixed in `ef37526 a11y: sr-only h1, aria-labels on target tab icon buttons, htmlFor labels` |
| 12 | 🟢 LOW | Icon-only buttons missing aria-labels | ✅ Resolved | Fixed in `ef37526` |

---

## Live Chrome Audit — Findings

### DEMO-BLOCKING
| ID | Finding | Status | Resolution |
|---|---|---|---|
| DB-1 | Apriori Co-failure Rules table always empty | ✅ Resolved | Same as item 2 above (`bc10668`) |

### HIGH
| ID | Finding | Status | Resolution |
|---|---|---|---|
| H-A | Evidence tab ANALYSIS block raw markdown | ✅ Resolved | Same as item 4 above (`ae41364`) |
| H-B | PIF chips display raw dot-notation keys | ✅ Resolved | Fixed in `a22c866 fix(ui): resolve PIF display names and disambiguate condition labels` |
| H-C | Pathway View mode toggle overlaps heading | ✅ Resolved | Fixed in `6952df3 polish: h4/hr markdown, pathway overlap, SHAP axis, tab persistence, provenance strip` |

### MEDIUM
| ID | Finding | Status | Resolution |
|---|---|---|---|
| M-1 | Provenance strip absent from Diagram and Pathway views | ✅ Resolved | Fixed in `6952df3` |
| M-2 | PIF Prevalence chart absent from Drivers & HF | 🟡 Open | Q2 below — intentionally deferred per scope |
| M-3 | Condition label mismatch between tabs | ✅ Resolved | Fixed in `a22c866` |
| M-4 | SVG container aspect ratio mismatch | 🟡 Open | Cosmetic; documented in tech-debt |
| M-5 | Analytics sub-tab selection resets on view switch | ✅ Resolved | Fixed in `6952df3` |
| M-6 | SHAP y-axis labels wrap to 3 lines | 🟢 Cosmetic | Labels readable; further polish in tech-debt |

### LOW
L-1 through L-10 are cosmetic / accessibility / spec-conformance items. All catalogued in `docs/tech-debt.md` for future iteration. None are user-blocking. Items partially addressed in `ef37526` (a11y) and `ea016ef fix(accuracy): align provenance counts, cascade vs RAG corpus label, barrier role rename`.

---

## Outstanding Questions from Live Chrome Audit

| Q | Question | Resolution |
|---|---|---|
| Q1 | Provenance strip count discrepancy (UI-CONTEXT vs live) | Resolved — UI-CONTEXT and provenance strip aligned to "113 BSEE · 19 CSB · 24 UNK" in `ea016ef` |
| Q2 | PIF Prevalence chart intentional removal? | Intentional for M003 scope; reinstatement deferred to M005+ |
| Q3 | Global Feature Importance top-N (3 vs 18 features) | Top-3 by design — keeps audience-facing chart legible |
| Q4 | RAG corpus scope (oil/gas only vs full CSB) | Resolved — domain filter added in `e182f53 fix(rag): domain filter + composite barrier-meta key to eliminate cross-domain evidence` |
| Q5 | Pathway View mode toggle overlap at narrow viewport | Resolved by H-C fix |

---

## Cascade Payload Bug — Separate Track

A critical bug not surfaced by either audit (because both audits used the BSEE pre-loaded scenario, not user-built scenarios) was diagnosed on 2026-04-27 and resolved in 2026-05-01. See `docs/diagnosis/2026-04-27_cascade_payload_bug.md` for the full root cause analysis. The fix, `frontend/hooks/useAnalyzeBarriers.ts` synthesising a scenario from user-entered barriers when none was preloaded, ships with a regression test (`frontend/__tests__/hooks/useAnalyzeBarriers.test.tsx`) that prevents the same null-guard from regressing.

---

## Items still open (consolidated)

For Bowtiefy planning, the open items remaining as of handoff:

1. **Mobile layout** — multi-hour responsive rebuild, M005+ scope
2. **PIF Prevalence chart** — intentionally deferred from M003 scope
3. **SVG container aspect ratio** — cosmetic, optional polish
4. **SHAP label wrap** — cosmetic, optional polish
5. **L-1 through L-10 (Live Chrome audit)** — design-spec conformance, cosmetic

All five are catalogued with priority and effort estimates in `docs/tech-debt.md`.