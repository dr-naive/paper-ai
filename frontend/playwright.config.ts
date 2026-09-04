import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e', timeout: 60_000, fullyParallel: false,
  use: { baseURL: process.env.PAPERAI_E2E_URL || 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
})
