import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 120_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:8150',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
})
