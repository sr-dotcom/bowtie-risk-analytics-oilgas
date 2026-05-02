/**
 * Phase 7 — Comprehensive Playwright audit of hosted Bowtie demo.
 *
 * Target:  https://bowtie.gnsr.dev
 * API:     https://bowtie-api.gnsr.dev
 *
 * READ-ONLY AUDIT — no application changes.
 *
 * Outputs (all written at end of test):
 *   docs/audits/screenshots/2026-04-24/*.png
 *   docs/audits/screenshots/2026-04-24/network-trace.json
 *   docs/audits/screenshots/2026-04-24/console-log.json
 *   docs/audits/screenshots/2026-04-24/meta.json
 */

import { test, Browser, BrowserContext, Page } from '@playwright/test'
import fs from 'fs'
import path from 'path'

// ── Constants ──────────────────────────────────────────────────────────────

const FRONTEND = 'https://bowtie.gnsr.dev'
const API_HOST = 'bowtie-api.gnsr.dev'
const OUT = path.resolve(__dirname, '../../docs/audits/screenshots/2026-04-24')
const AUDIT_START = new Date().toISOString()

// ── Types ──────────────────────────────────────────────────────────────────

interface NetworkEntry {
  seq: number
  url: string
  method: string
  status: number | null
  duration_ms: number | null
  content_length: string | null
  flagged: boolean
  flag_reason: string | null
  response_preview: string | null
  timestamp: string
}

interface ConsoleEntry {
  type: string
  text: string
  page_url: string
  timestamp: string
}

// ── Module-level collectors (single-worker run) ───────────────────────────

const networkLog: NetworkEntry[] = []
const consoleLog: ConsoleEntry[] = []
let networkSeq = 0

// ── Helpers ────────────────────────────────────────────────────────────────

function shot(name: string): string {
  return path.join(OUT, name)
}

async function safeClick(page: Page, selector: string, timeout = 8_000): Promise<boolean> {
  try {
    await page.click(selector, { timeout })
    return true
  } catch {
    return false
  }
}

async function safeWait(
  page: Page,
  selector: string,
  timeout = 10_000,
): Promise<boolean> {
  try {
    await page.waitForSelector(selector, { timeout })
    return true
  } catch {
    return false
  }
}

function attachListeners(page: Page): void {
  // Use WeakMap so GC can collect request objects after they're done
  const requestStartTimes = new WeakMap<object, number>()

  page.on('request', (req) => {
    if (!req.url().includes(API_HOST)) return
    requestStartTimes.set(req, Date.now())
  })

  page.on('requestfailed', (req) => {
    if (!req.url().includes(API_HOST)) return
    const failure = req.failure()
    networkLog.push({
      seq: ++networkSeq,
      url: req.url(),
      method: req.method(),
      status: null,
      duration_ms: null,
      content_length: null,
      flagged: true,
      flag_reason: `Request failed: ${failure?.errorText ?? 'unknown'}`,
      response_preview: null,
      timestamp: new Date().toISOString(),
    })
  })

  page.on('response', async (res) => {
    if (!res.url().includes(API_HOST)) return

    const req = res.request()
    const startMs = requestStartTimes.get(req)
    const duration_ms = startMs !== undefined ? Date.now() - startMs : null
    requestStartTimes.delete(req)

    const status = res.status()
    const content_length = res.headers()['content-length'] ?? null

    const flagReasons: string[] = []
    if (status >= 400) flagReasons.push(`HTTP ${status}`)
    if (duration_ms !== null && duration_ms > 5000)
      flagReasons.push(`slow (${(duration_ms / 1000).toFixed(1)}s)`)

    let response_preview: string | null = null
    if (status >= 400) {
      try {
        response_preview = (await res.text()).slice(0, 500)
      } catch {
        response_preview = '[body unreadable]'
      }
    }

    networkLog.push({
      seq: ++networkSeq,
      url: res.url(),
      method: req.method(),
      status,
      duration_ms,
      content_length,
      flagged: flagReasons.length > 0,
      flag_reason: flagReasons.join(', ') || null,
      response_preview,
      timestamp: new Date().toISOString(),
    })
  })

  page.on('console', (msg) => {
    const type = msg.type()
    const text = msg.text()
    const interesting =
      type === 'error' ||
      type === 'warning' ||
      (/\b(error|fail|undefined|NaN)\b/i.test(text) && text.length > 30)
    if (!interesting) return
    consoleLog.push({
      type,
      text: text.slice(0, 600),
      page_url: page.url(),
      timestamp: new Date().toISOString(),
    })
  })
}

// ══════════════════════════════════════════════════════════════════════════
// AUDIT TEST — single 18-minute test collects everything
// ══════════════════════════════════════════════════════════════════════════

test.setTimeout(18 * 60 * 1000)

test('Phase 7 — Hosted demo audit 2026-04-24', async ({ page, browser }) => {
  fs.mkdirSync(OUT, { recursive: true })
  attachListeners(page)

  const meta: Record<string, unknown> = {
    audit_start: AUDIT_START,
    frontend_url: FRONTEND,
    api_host: API_HOST,
  }

  // ──────────────────────────────────────────────────────────────────────
  // §1a  DESKTOP INITIAL LOAD  1920×1080
  // ──────────────────────────────────────────────────────────────────────

  await page.setViewportSize({ width: 1920, height: 1080 })

  const loadStart = Date.now()
  await page.goto(FRONTEND, { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {})
  meta['desktop_load_ms'] = Date.now() - loadStart
  meta['page_title'] = await page.title()
  meta['h1_text'] = await page.locator('h1').first().textContent().catch(() => '(none)')

  const allButtons = await page.locator('button').allTextContents().catch(() => [] as string[])
  meta['buttons_on_cold_load'] = allButtons

  await page.screenshot({ path: shot('01a_desktop_cold_load.png'), fullPage: true })

  // ──────────────────────────────────────────────────────────────────────
  // §1b  MOBILE INITIAL LOAD  390×844
  // ──────────────────────────────────────────────────────────────────────

  const mobileCtx = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const mobilePage = await mobileCtx.newPage()
  try {
    await mobilePage.goto(FRONTEND, { waitUntil: 'domcontentloaded', timeout: 30_000 })
    await mobilePage.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await mobilePage.screenshot({ path: shot('01b_mobile_cold_load.png'), fullPage: true })
    meta['mobile_buttons'] = await mobilePage.locator('button').allTextContents().catch(() => [] as string[])
    meta['mobile_body_scrollWidth_overflow'] = await mobilePage.evaluate(
      () => document.body.scrollWidth > window.innerWidth,
    )
    meta['mobile_main_scrollWidth_overflow'] = await mobilePage.evaluate(() => {
      const main = document.querySelector('main')
      return main ? main.scrollWidth > window.innerWidth : null
    })
  } finally {
    await mobileCtx.close()
  }

  // ──────────────────────────────────────────────────────────────────────
  // §1c  PRE-ANALYZE SCREENSHOT + analyzeAll()
  // ──────────────────────────────────────────────────────────────────────

  const analyzeBtn = page.locator('button:has-text("Analyze Barriers"):not([disabled])')
  await analyzeBtn.waitFor({ timeout: 15_000 })
  await page.screenshot({ path: shot('01c_pre_analyze.png'), fullPage: true })

  const analyzeStart = Date.now()
  await analyzeBtn.click()
  await page.screenshot({ path: shot('01d_analyze_triggered.png'), fullPage: true })

  // Navigate to analytics while analysis runs in background
  await safeClick(page, 'button:has-text("Analytics")', 10_000)

  const skeletonHidden = await page
    .waitForSelector('[data-testid="analyzing-skeleton"]', { state: 'hidden', timeout: 90_000 })
    .then(() => true)
    .catch(() => false)
  meta['analyze_all_duration_ms'] = Date.now() - analyzeStart
  meta['analyzing_skeleton_found_and_hidden'] = skeletonHidden

  // ──────────────────────────────────────────────────────────────────────
  // §2a  EXECUTIVE SUMMARY TAB
  // ──────────────────────────────────────────────────────────────────────

  // Default tab after Analytics — take screenshot immediately
  await page.waitForTimeout(500)
  await page.screenshot({ path: shot('02a_tab_executive_summary.png'), fullPage: true })

  const corpusText = await safeWait(page, 'text=Cascade training corpus', 10_000)
  meta['exec_summary_corpus_text_found'] = corpusText
  meta['exec_summary_kpi_texts'] = await page.locator('[data-testid*="kpi"], .kpi, [class*="kpi"]')
    .allTextContents()
    .catch(() => [])
  // Capture chart presence
  meta['exec_summary_chart_count'] = await page.locator('[role="application"]').count()

  // ──────────────────────────────────────────────────────────────────────
  // §2b  DRIVERS & HF TAB
  // ──────────────────────────────────────────────────────────────────────

  await safeClick(page, 'button:has-text("Drivers & HF")')
  await page.waitForTimeout(2000)
  await page.screenshot({ path: shot('02b_tab_drivers_hf.png'), fullPage: true })

  meta['apriori_table_visible'] = await page
    .locator('[data-testid="apriori-rules-table"]')
    .isVisible()
    .catch(() => false)
  meta['apriori_row_count'] = await page
    .locator('[data-testid="apriori-rules-table"] table tbody tr')
    .count()
    .catch(() => 0)
  meta['drivers_chart_count'] = await page.locator('[role="application"]').count()

  // Capture first 3 Apriori rule rows for the report
  const aprioriSample = await page
    .locator('[data-testid="apriori-rules-table"] table tbody tr')
    .evaluateAll((rows) => rows.slice(0, 3).map((r) => r.textContent?.trim().slice(0, 120) ?? ''))
    .catch(() => [] as string[])
  meta['apriori_first_3_rows'] = aprioriSample

  // ──────────────────────────────────────────────────────────────────────
  // §2c  RANKED BARRIERS — COLD (known tech debt: always empty pre-cascade)
  // ──────────────────────────────────────────────────────────────────────

  await safeClick(page, 'button:has-text("Ranked Barriers")')
  await page.waitForTimeout(1000)
  await page.screenshot({ path: shot('02c_ranked_barriers_cold.png'), fullPage: true })
  meta['ranked_cold_row_count'] = await page.locator('table tbody tr').count().catch(() => 0)
  meta['ranked_cold_placeholder_text'] = await page
    .locator('main')
    .textContent()
    .then((t) => t?.trim().slice(0, 300))
    .catch(() => '(none)')

  // ──────────────────────────────────────────────────────────────────────
  // §2d  EVIDENCE TAB — COLD
  // ──────────────────────────────────────────────────────────────────────

  const evidenceTabSelector = 'button:has-text("Evidence")'
  const evidenceTabExists = await page.locator(evidenceTabSelector).isVisible().catch(() => false)
  meta['evidence_tab_exists'] = evidenceTabExists
  if (evidenceTabExists) {
    await safeClick(page, evidenceTabSelector)
    await page.waitForTimeout(1000)
    await page.screenshot({ path: shot('02d_evidence_cold.png'), fullPage: true })
    meta['evidence_cold_text'] = await page
      .locator('main')
      .textContent()
      .then((t) => t?.trim().slice(0, 300))
      .catch(() => '(none)')
  }

  // Enumerate ALL visible tabs/buttons while in dashboard mode
  meta['all_dashboard_buttons'] = await page.locator('button').allTextContents().catch(() => [] as string[])

  // ──────────────────────────────────────────────────────────────────────
  // §3a  DIAGRAM VIEW
  // ──────────────────────────────────────────────────────────────────────

  await safeClick(page, 'button:has-text("Diagram View")')
  await page.waitForTimeout(1000)
  await page.screenshot({ path: shot('03a_diagram_view.png'), fullPage: true })

  const barriers = page.locator('svg g[style*="cursor: pointer"]')
  const barrierCount = await barriers.count()
  meta['svg_barrier_count'] = barrierCount

  // ──────────────────────────────────────────────────────────────────────
  // §3b–c  HOVER + CLICK FIRST 3 BARRIERS
  // ──────────────────────────────────────────────────────────────────────

  const barrierInteractions: Record<string, unknown>[] = []

  for (let i = 0; i < Math.min(3, barrierCount); i++) {
    const barrier = barriers.nth(i)
    const interaction: Record<string, unknown> = { index: i }

    // Hover
    try {
      await barrier.hover({ timeout: 5_000 })
      await page.waitForTimeout(500)
      await page.screenshot({ path: shot(`03b_barrier_${i + 1}_hover.png`) })
      interaction['hover'] = 'ok'
    } catch (e) {
      interaction['hover'] = `error: ${(e as Error).message.slice(0, 80)}`
    }

    // Click
    try {
      await barrier.click({ timeout: 5_000 })
      await page.waitForTimeout(1500)
      await page.screenshot({ path: shot(`03c_barrier_${i + 1}_clicked.png`), fullPage: true })
      interaction['click'] = 'ok'

      // Capture detail panel / drawer content
      const panelText = await page
        .locator(
          '[class*="DetailPanel"], [class*="DrawerPanel"], [class*="detail-panel"], [class*="drawer"]',
        )
        .first()
        .textContent()
        .catch(() => null)
      interaction['panel_text_preview'] = panelText?.trim().slice(0, 300) ?? '(panel not found)'

      // Capture any probability values visible
      const probTexts = await page
        .locator('text=/\\d+\\.\\d+%|\\d+%/')
        .allTextContents()
        .catch(() => [] as string[])
      interaction['probability_texts'] = probTexts.slice(0, 10)
    } catch (e) {
      interaction['click'] = `error: ${(e as Error).message.slice(0, 80)}`
    }

    await page.keyboard.press('Escape')
    await page.waitForTimeout(400)
    barrierInteractions.push(interaction)
  }
  meta['barrier_interactions'] = barrierInteractions

  // ──────────────────────────────────────────────────────────────────────
  // §4  CASCADE MODE — barrier click → Analytics cascade flow
  // ──────────────────────────────────────────────────────────────────────

  // Click first barrier to set conditioningBarrierId
  await barriers.first().click({ timeout: 10_000 }).catch(() => {})
  await page.waitForTimeout(2000)
  await page.screenshot({ path: shot('04a_cascade_barrier_selected.png'), fullPage: true })

  // Capture what's visible in the detail drawer
  meta['cascade_detail_panel_visible'] = await page
    .locator(
      '[class*="DetailPanel"], [class*="DrawerPanel"], [class*="detail-panel"], [class*="drawer"]',
    )
    .first()
    .isVisible()
    .catch(() => false)

  // Close drawer, go to analytics (conditioningBarrierId persists)
  await page.keyboard.press('Escape')
  await page.waitForTimeout(400)
  await safeClick(page, 'button:has-text("Analytics")')

  // ──────────────────────────────────────────────────────────────────────
  // §4b  RANKED BARRIERS — CASCADE MODE
  // ──────────────────────────────────────────────────────────────────────

  await safeClick(page, 'button:has-text("Ranked Barriers")')
  const cascadeHeaderFound = await safeWait(page, 'text=Cascading analysis: assuming', 35_000)
  meta['cascade_header_found'] = cascadeHeaderFound
  await page.screenshot({ path: shot('04b_ranked_barriers_cascade.png'), fullPage: true })

  const cascadeRowCount = await page.locator('table tbody tr').count().catch(() => 0)
  meta['ranked_cascade_row_count'] = cascadeRowCount

  // Capture cascade header text (shows which barrier is conditioning)
  meta['cascade_header_text'] = await page
    .locator('text=Cascading analysis: assuming')
    .first()
    .textContent()
    .catch(() => '(not found)')

  // ──────────────────────────────────────────────────────────────────────
  // §4c  SHAP WATERFALL — expand first row
  // ──────────────────────────────────────────────────────────────────────

  const firstRow = page.locator('table tbody tr').first()
  const firstRowVisible = await firstRow.isVisible().catch(() => false)
  meta['first_cascade_row_clickable'] = firstRowVisible

  if (firstRowVisible) {
    await firstRow.click()
    const expandedFound = await safeWait(page, '[data-testid="ranked-row-expanded"]', 10_000)
    meta['shap_waterfall_expanded_found'] = expandedFound

    if (expandedFound) {
      const shapChartFound = await safeWait(
        page,
        '[data-testid="ranked-row-expanded"] [role="application"]',
        10_000,
      )
      meta['shap_chart_rendered'] = shapChartFound
      await page.screenshot({ path: shot('04c_shap_waterfall.png'), fullPage: true })

      // Capture SHAP feature texts visible
      meta['shap_feature_labels'] = await page
        .locator('[data-testid="ranked-row-expanded"] text, [data-testid="ranked-row-expanded"] tspan')
        .allTextContents()
        .then((texts) => texts.slice(0, 15))
        .catch(() => [] as string[])
    }
  }

  // ──────────────────────────────────────────────────────────────────────
  // §4d  EVIDENCE TAB — CASCADE CONTEXT (RAG + LLM narrative)
  // ──────────────────────────────────────────────────────────────────────

  if (evidenceTabExists) {
    await safeClick(page, evidenceTabSelector)
    const evidenceViewFound = await safeWait(page, '[data-testid="evidence-view"]', 10_000)
    meta['evidence_view_found_in_cascade'] = evidenceViewFound

    const evidenceStart = Date.now()
    // /explain-cascading calls RAG + LLM — can take up to 60s
    const simIncidentsFound = await safeWait(page, 'text=Similar Incidents', 65_000)
    meta['evidence_rag_similar_incidents_found'] = simIncidentsFound
    meta['evidence_load_ms'] = Date.now() - evidenceStart

    await page.screenshot({ path: shot('04d_evidence_rag_narrative.png'), fullPage: true })

    meta['evidence_text_sample'] = await page
      .locator('[data-testid="evidence-view"]')
      .textContent()
      .then((t) => t?.trim().slice(0, 600))
      .catch(() => '(not found)')

    // Look for citations, PIF tags, incident snippets
    meta['evidence_citations_present'] = await page
      .locator('[data-testid="evidence-view"] a, [data-testid="evidence-view"] cite')
      .count()
      .then((n) => n > 0)
      .catch(() => false)
    meta['evidence_pif_tags_present'] = await page
      .locator('[data-testid="evidence-view"] [class*="pif"], [data-testid="evidence-view"] [class*="tag"]')
      .count()
      .then((n) => n > 0)
      .catch(() => false)
  }

  // ──────────────────────────────────────────────────────────────────────
  // §5  SCENARIO B — Ranked Barriers full exploration
  // ──────────────────────────────────────────────────────────────────────

  await safeClick(page, 'button:has-text("Ranked Barriers")')
  await safeWait(page, 'text=Cascading analysis: assuming', 15_000)
  await page.screenshot({ path: shot('05a_scenario_b_ranked_full.png'), fullPage: true })

  // Capture full ranked table content (first 5 rows)
  const rankedRows = await page
    .locator('table tbody tr')
    .evaluateAll((rows) => rows.slice(0, 5).map((r) => r.textContent?.trim().slice(0, 100) ?? ''))
    .catch(() => [] as string[])
  meta['ranked_cascade_top5_rows'] = rankedRows

  // ──────────────────────────────────────────────────────────────────────
  // §5b  SCENARIO C — Drivers & HF Apriori exploration
  // ──────────────────────────────────────────────────────────────────────

  await safeClick(page, 'button:has-text("Drivers & HF")')
  await safeWait(page, '[data-testid="apriori-rules-table"] table', 15_000)
  await page.screenshot({ path: shot('05b_scenario_c_drivers_hf_full.png'), fullPage: true })

  // Check if Apriori rows are interactive (clickable)
  const aprioriFirstRow = page.locator('[data-testid="apriori-rules-table"] table tbody tr').first()
  const aprioriRowClickable = await aprioriFirstRow.isVisible().catch(() => false)
  if (aprioriRowClickable) {
    await aprioriFirstRow.click()
    await page.waitForTimeout(800)
    await page.screenshot({ path: shot('05c_apriori_row_clicked.png'), fullPage: true })
    meta['apriori_row_click_opened_anything'] = await page
      .locator('[class*="modal"], [class*="drawer"], [role="dialog"]')
      .isVisible()
      .catch(() => false)
  }

  // ──────────────────────────────────────────────────────────────────────
  // §6  FOOTER / PROVENANCE STRIP
  // ──────────────────────────────────────────────────────────────────────

  await safeClick(page, 'button:has-text("Ranked Barriers")')
  await page.waitForTimeout(500)
  const footer = page.locator('footer')
  const footerVisible = await footer.isVisible().catch(() => false)
  meta['footer_visible'] = footerVisible
  if (footerVisible) {
    await footer.scrollIntoViewIfNeeded()
    await page.waitForTimeout(300)
    await page.screenshot({ path: shot('06_footer_provenance.png') })
    meta['footer_text'] = await footer.textContent().then((t) => t?.trim().slice(0, 400)).catch(() => '(none)')
  }

  // ──────────────────────────────────────────────────────────────────────
  // §7  LAYOUT CHECKS (bounding box overflow)
  // ──────────────────────────────────────────────────────────────────────

  // Do layout check on each main tab
  const layoutChecks: Record<string, unknown> = {}

  for (const [tab, tabSelector] of [
    ['executive_summary', 'button:has-text("Analytics")'],
    ['drivers_hf', 'button:has-text("Drivers & HF")'],
    ['ranked_barriers', 'button:has-text("Ranked Barriers")'],
  ] as const) {
    await safeClick(page, tabSelector)
    await page.waitForTimeout(700)

    const overflowIssues = await page.evaluate(() => {
      const issues: string[] = []
      if (document.body.scrollWidth > window.innerWidth + 10) {
        issues.push(`body horizontal overflow: ${document.body.scrollWidth}px > ${window.innerWidth}px viewport`)
      }
      document.querySelectorAll<HTMLElement>('p, h1, h2, h3, span, td, th, button').forEach((el) => {
        const rect = el.getBoundingClientRect()
        const text = el.textContent?.trim() ?? ''
        if (
          rect.width > 10 &&
          rect.right > window.innerWidth + 20 &&
          text.length > 0 &&
          text.length < 80
        ) {
          issues.push(
            `"${text.slice(0, 40)}" <${el.tagName}> overflows right=${Math.round(rect.right)}px`,
          )
        }
      })
      return issues.slice(0, 15)
    })

    layoutChecks[tab] = overflowIssues
  }
  meta['layout_checks'] = layoutChecks

  // ──────────────────────────────────────────────────────────────────────
  // §8  FINAL SUMMARY SCREENSHOT (whole page after full session)
  // ──────────────────────────────────────────────────────────────────────

  await safeClick(page, 'button:has-text("Analytics")')
  await page.waitForTimeout(500)
  await page.screenshot({ path: shot('07_session_end_state.png'), fullPage: true })

  // ──────────────────────────────────────────────────────────────────────
  // WRITE JSON OUTPUTS
  // ──────────────────────────────────────────────────────────────────────

  meta['audit_end'] = new Date().toISOString()
  meta['total_api_network_calls'] = networkLog.length
  meta['flagged_network_calls'] = networkLog.filter((e) => e.flagged).length
  meta['total_console_entries'] = consoleLog.length
  meta['console_error_count'] = consoleLog.filter((e) => e.type === 'error').length
  meta['console_warning_count'] = consoleLog.filter((e) => e.type === 'warning').length
  meta['api_endpoints_hit'] = [...new Set(networkLog.map((e) => new URL(e.url).pathname))]

  fs.writeFileSync(path.join(OUT, 'network-trace.json'), JSON.stringify(networkLog, null, 2))
  fs.writeFileSync(path.join(OUT, 'console-log.json'), JSON.stringify(consoleLog, null, 2))
  fs.writeFileSync(path.join(OUT, 'meta.json'), JSON.stringify(meta, null, 2))
})
