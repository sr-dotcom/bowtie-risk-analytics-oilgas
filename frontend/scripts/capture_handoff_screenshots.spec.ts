/**
 * M004 UI handoff screenshot capture.
 *
 * Runs 6 deterministic shots against the live dev stack (backend :8000, frontend :3000).
 * Output: docs/evidence/uat/screenshots/handoff-2026-04-23/*.png
 *
 * Run:
 *   npx playwright test scripts/capture_handoff_screenshots.spec.ts \
 *     --config frontend/playwright.config.ts --reporter=list
 *
 * Flow overview
 * ─────────────
 * Phase A — initial load + analyzeAll():
 *   1. goto('/') — demo scenario auto-loads via BowtieApp useEffect
 *   2. click "Analyze Barriers" → analyzeAll() fires N parallel /predict-cascading calls
 *   3. click "Analytics" → enter dashboard (no SVG barrier clicked, no DetailDrawer open)
 *   4. wait for skeleton hidden (analyzeAll complete)
 *
 * Phase B — shots 1–3 (no cascading mode needed):
 *   Shot 1  Executive Summary KPIs
 *   Shot 2  Provenance strip (footer)
 *   Shot 3  Drivers & HF — Apriori co-failure rules
 *
 * Phase C — bootstrap cascading mode:
 *   5. click "Diagram View" → back to SVG (no barrier selected, no DrawerPanel)
 *   6. click first SVG barrier → handleBarrierClick() sets conditioningBarrierId +
 *      selectedTargetBarrierId, opens DetailDrawer, triggers analyze()
 *   7. press Escape → DetailDrawer closes (conditioningBarrierId stays set)
 *   8. click "Analytics" → back to dashboard
 *   9. click "Ranked Barriers" tab
 *  10. wait for "Cascading analysis: assuming …" → analyze() complete, table populated
 *
 * Phase D — shots 4–6 (cascading mode):
 *   Shot 4  Ranked Barriers with ranking-criteria tooltip overlay
 *   Shot 5  Evidence tab — RAG snippets loaded
 *   Shot 6  Drill-down SHAP waterfall (expanded row)
 *
 * NOTE — Shot 4 tooltip:
 *   The tooltip is a native HTML `title` attribute, which headless Chromium does not render
 *   visually. A programmatic overlay matching the app's dark theme is injected for the
 *   screenshot and removed immediately after.
 *
 * NOTE — Non-cascading table is always empty in M003:
 *   buildRankedRows() checks `predictions[b.id] !== undefined` where predictions is the
 *   M002-style prediction map — always empty because /predict returns 410 Gone.
 *   The table only populates after conditioningBarrierId is set (cascading mode).
 *   Therefore cascading setup must happen via the SVG barrier click path, not via
 *   "What if fails?" buttons that only appear after the table has rows.
 */

import { test } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const OUTPUT = path.resolve(__dirname, '../../docs/evidence/uat/screenshots/handoff-2026-04-23')

test('M004 handoff screenshots', async ({ page }) => {
  fs.mkdirSync(OUTPUT, { recursive: true })

  // ── PHASE A — initial load + analyzeAll() ─────────────────────────────────

  await page.goto('/')
  await page.waitForSelector('button:has-text("Analyze Barriers"):not([disabled])', {
    timeout: 15_000,
  })

  // analyzeAll() fires N parallel /predict-cascading calls, writes
  // average_cascading_probability + riskLevel to each barrier.
  await page.click('button:has-text("Analyze Barriers")')

  // Navigate to dashboard immediately — analysis continues in the background.
  // No SVG barrier has been clicked yet, so DetailDrawer is closed.
  await page.click('button:has-text("Analytics")')

  // Wait for analyzeAll() to finish — skeleton disappears when isAnalyzing → false.
  await page
    .waitForSelector('[data-testid="analyzing-skeleton"]', {
      state: 'hidden',
      timeout: 60_000,
    })
    .catch(() => {
      // Skeleton may not appear if analysis completes before the first render tick.
    })

  // ── PHASE B — shots 1–3 ───────────────────────────────────────────────────

  // ── SHOT 1 — Executive Summary KPIs ────────────────────────────────────────
  // DashboardView mounts with activeTab = 'executive-summary' by default.
  await page.waitForSelector('text=Cascade training corpus', { timeout: 10_000 })
  await page.screenshot({ path: path.join(OUTPUT, '01_executive_summary.png') })

  // ── SHOT 2 — Provenance strip ───────────────────────────────────────────────
  await page.locator('footer').scrollIntoViewIfNeeded()
  await page.waitForSelector('text=Predictions: XGBoost cascade', { timeout: 5_000 })
  await page.screenshot({ path: path.join(OUTPUT, '02_provenance_strip.png') })

  // ── SHOT 3 — Drivers & HF — Apriori co-failure rules ──────────────────────
  await page.click('button:has-text("Drivers & HF")')
  await page.waitForSelector('[data-testid="apriori-rules-table"] table', { timeout: 15_000 })
  await page.screenshot({ path: path.join(OUTPUT, '03_drivers_hf_apriori.png') })

  // ── PHASE C — bootstrap cascading mode ────────────────────────────────────

  // Return to the SVG diagram view. The view-mode toggle bar is rendered at the
  // top of the page in dashboard mode — "Diagram View" button returns to BowtieSVG.
  await page.click('button:has-text("Diagram View")')

  // Click the first SVG barrier node. handleBarrierClick() sets:
  //   • selectedBarrierId      → opens DetailDrawer
  //   • selectedTargetBarrierId
  //   • conditioningBarrierId  → first other barrier (fallback if no avg probabilities yet)
  // The conditioningBarrierId change triggers analyze() in BowtieContext.
  const firstBarrier = page.locator('svg g[style*="cursor: pointer"]').first()
  await firstBarrier.waitFor({ timeout: 10_000 })
  await firstBarrier.click()

  // Close the DetailDrawer without navigating away. setSelectedBarrierId(null) is
  // called by the Escape key listener — conditioningBarrierId is NOT reset.
  await page.keyboard.press('Escape')
  await page.waitForTimeout(300) // let React settle the state update

  // Return to dashboard. Analytics button is now accessible — DetailDrawer is hidden.
  await page.click('button:has-text("Analytics")')

  // Navigate to Ranked Barriers and wait for analyze() to populate the cascading table.
  await page.click('button:has-text("Ranked Barriers")')

  // In cascading mode the header paragraph shows "Cascading analysis: assuming <name> has failed".
  // analyze() makes N /predict-cascading calls; allow up to 30 s.
  await page.waitForSelector('text=Cascading analysis: assuming', { timeout: 30_000 })

  // ── PHASE D — shots 4–6 ───────────────────────────────────────────────────

  // ── SHOT 4 — Ranked Barriers — ranking criteria tooltip ────────────────────
  // Inject a styled overlay for the native `title` attribute (not rendered headlessly).
  await page.evaluate(() => {
    const infoIcon = document.querySelector('[aria-label="Ranking criteria"]')
    if (!infoIcon) return
    const tooltipText = infoIcon.getAttribute('title') ?? ''
    const rect = infoIcon.getBoundingClientRect()
    const el = document.createElement('div')
    el.id = 'pw-tooltip-overlay'
    Object.assign(el.style, {
      position: 'fixed',
      left: `${Math.min(rect.left, window.innerWidth - 440)}px`,
      top: `${rect.bottom + 6}px`,
      maxWidth: '420px',
      background: '#1C2430',
      border: '1px solid #2A3442',
      color: '#E8E8E8',
      fontSize: '11px',
      padding: '8px 12px',
      borderRadius: '4px',
      zIndex: '9999',
      whiteSpace: 'pre-wrap',
      lineHeight: '1.6',
      boxShadow: '0 4px 14px rgba(0,0,0,0.5)',
    })
    el.textContent = tooltipText
    document.body.appendChild(el)
  })
  await page.screenshot({ path: path.join(OUTPUT, '04_ranked_barriers_tooltip.png') })
  await page.evaluate(() => {
    document.getElementById('pw-tooltip-overlay')?.remove()
  })

  // ── SHOT 5 — Evidence tab — RAG snippets loaded ────────────────────────────
  // Click the first non-conditioning barrier row. In cascading mode the conditioning
  // barrier is excluded from the table, so the first visible row is a safe target.
  // Row click calls setSelectedTargetBarrierId(row.barrierId) in cascading mode.
  await page.locator('table tbody tr').first().click()

  await page.click('button:has-text("Evidence")')
  await page.waitForSelector('[data-testid="evidence-view"]', { timeout: 10_000 })

  // /explain-cascading runs RAG retrieval + LLM synthesis — allow up to 60 s.
  await page.waitForSelector('text=Similar Incidents', { timeout: 60_000 })
  await page.screenshot({ path: path.join(OUTPUT, '05_evidence_tab_loaded.png') })

  // ── SHOT 6 — Drill-down SHAP waterfall ────────────────────────────────────
  // RankedBarriers remounts on tab switch (conditional rendering resets expandedRowId),
  // so we must click the row again to expand the ShapWaterfall.
  await page.click('button:has-text("Ranked Barriers")')
  await page.waitForSelector('text=Cascading analysis: assuming', { timeout: 15_000 })

  // Expand the first row. cascadingPred.shap_values is already in memory from analyze(),
  // so ShapWaterfall renders synchronously without a new API call.
  await page.locator('table tbody tr').first().click()
  await page.waitForSelector('[data-testid="ranked-row-expanded"]', { timeout: 10_000 })

  // ShapWaterfall renders a Recharts SVG with role="application".
  await page.waitForSelector('[data-testid="ranked-row-expanded"] [role="application"]', {
    timeout: 10_000,
  })
  await page.screenshot({ path: path.join(OUTPUT, '06_drilldown_shap_waterfall.png') })
})
