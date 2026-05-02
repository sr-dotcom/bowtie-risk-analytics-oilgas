import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests-e2e',
  testMatch: '**/audit-2026-04-24.spec.ts',
  use: {
    viewport: { width: 1920, height: 1080 },
    screenshot: 'off',
    video: 'off',
    trace: 'off',
    ignoreHTTPSErrors: false,
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  workers: 1,
  retries: 0,
  timeout: 18 * 60 * 1000,
})
