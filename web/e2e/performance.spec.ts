import { expect, test } from "@playwright/test";

// Runs against the UI-test fixture: one graded game, spread win (1-0-0) and total loss (0-1-0).
test.describe("performance page is accuracy-only", () => {
  test("shows records, win rates and forecast accuracy with no financial copy", async ({ page }) => {
    await page.goto("/performance");
    await expect(page.getByRole("heading", { name: "Season record & performance" })).toBeVisible();

    const summary = page.getByRole("region", { name: "Forecast accuracy summary", exact: true });
    await expect(summary.getByText("1–0–0")).toBeVisible();
    await expect(summary.getByText("0–1–0")).toBeVisible();
    await expect(summary.getByText("100.0%")).toBeVisible();

    const accuracy = page.getByRole("region", { name: "Forecast accuracy", exact: true });
    await expect(accuracy.getByText(/Spread MAE/)).toBeVisible();
    await expect(accuracy.getByText(/Total 95% interval/)).toBeVisible();

    const body = page.locator("body");
    for (const banned of [/\bROI\b/, /profit/i, /\bunits?\b/i, /net return/i, /closing line/i, /-110/, /\d\.\d+u\b/]) {
      await expect(body.getByText(banned)).toHaveCount(0);
    }
  });

  test("target filter narrows the weekly table and audit list", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/performance");
    await page.getByRole("tab", { name: "Totals" }).click();
    await expect(page.getByRole("columnheader", { name: "Total (W-L-P)" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Spread (W-L-P)" })).toHaveCount(0);
    await expect(page.getByText(/Total · captured line/)).toBeVisible();
    await expect(page.getByText(/Spread · captured line/)).toHaveCount(0);
  });

  test("audit shows price provenance as an audit fact", async ({ page }) => {
    await page.goto("/performance");
    await expect(page.getByText(/Price: unavailable/).first()).toBeVisible();
  });

  for (const width of [375, 420]) {
    test(`stays bounded at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/performance");
      await expect(page.getByRole("heading", { name: "Season record & performance" })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    });
  }
});
