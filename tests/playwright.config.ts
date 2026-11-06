import { defineConfig, devices } from '@playwright/test'
const artifacts = process.env.CHAT_TEST_ARTIFACTS || 'D:/autostack/plan-artifacts/auto-chat-tests'
export default defineConfig({
  testDir: '.', testMatch: '*.spec.ts', fullyParallel: false,
  forbidOnly: !!process.env.CI, retries: process.env.CI ? 1 : 0, workers: 1,
  reporter: [['list'], ['html', { outputFolder: `${artifacts}/playwright-report`, open: 'never' }]],
  outputDir: `${artifacts}/test-results`,
  use: {
    baseURL: process.env.CHAT_URL || 'http://localhost:17822',
    // Recovery credentials are typed into the real UI. Automatic failure
    // capture/trace must not persist them; capture public post-login states only.
    trace: 'off', screenshot: 'off', video: 'off',
    actionTimeout: 5000, navigationTimeout: 10000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
