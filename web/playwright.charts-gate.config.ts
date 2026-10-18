import { defineConfig } from "@playwright/test";

export default defineConfig({
  // Deliberately outside e2e/: the enabled and disabled servers run sequentially.
  testDir: "./e2e-charts-gate",
  timeout: 30_000,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:3101", browserName: "chromium" },
  webServer: {
    command: "CFB_CHARTS_ENABLED=0 CFB_UI_TEST_MODE=1 CFB_PUBLICATION_MODE=predictions npm run start -- --hostname 127.0.0.1 --port 3101",
    url: "http://127.0.0.1:3101",
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
