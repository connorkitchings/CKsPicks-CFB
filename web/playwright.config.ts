import { defineConfig } from "@playwright/test";

const port = process.env.PLAYWRIGHT_PORT ?? "3100";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    browserName: "chromium",
  },
  webServer: {
    // Predictions mode is set here (not inherited from web/.env, which CI does not have) so the
    // slate tests run against the same fixtures locally and in CI.
    command: `CFB_CHARTS_ENABLED=1 CFB_UI_TEST_MODE=1 CFB_PUBLICATION_MODE=predictions npm run dev -- --hostname 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    // Never reuse an unrelated server whose Charts flag may be off.
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
