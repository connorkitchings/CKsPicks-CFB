import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 568 }]) {
  test.describe(`phone model page at ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport, hasTouch: true });

    test("the first KPI card sits near the top, with a summary and no duplicate headings", async ({ page }) => {
      await gotoHydrated(page, "/model");
      const spread = page.getByRole("button", { name: /^Spread/ });
      await expect(spread).toBeVisible();
      expect((await spread.boundingBox())!.y).toBeLessThan(330);
      await expect(page.getByTestId("model-summary")).toHaveText(/^2026 · V5 · \d+ graded weeks?$/);
      // The hand-rolled eyebrow is hidden; the summary line carries "2026 · V5".
      await expect(page.getByText("2026 · V5", { exact: true }).filter({ visible: true })).toHaveCount(0);
      await expect(page.getByRole("region", { name: "Forecast accuracy summary", exact: true })).toBeVisible();
      await expect(page.locator("details[open]")).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test("the Record / How it works tabs stay directly under the app bar after an 800px scroll", async ({ page }) => {
      await gotoHydrated(page, "/model");
      const tabs = page.getByRole("navigation", { name: "Model sections" });
      await page.mouse.wheel(0, 800);
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
      const bar = (await page.getByTestId("app-bar").boundingBox())!;
      await expect.poll(async () => Math.abs((await tabs.boundingBox())!.y - (bar.y + bar.height))).toBeLessThanOrEqual(1);
    });

    test("the Spread and Totals cards are the only filter and narrow the weekly cards", async ({ page }) => {
      await gotoHydrated(page, "/model");
      await expect(page.getByRole("group", { name: "Pick target" })).toHaveCount(0);
      await expect(page.getByRole("button", { name: "All Picks" })).toHaveCount(0);
      const weekly = page.getByRole("region", { name: "Weekly accuracy breakdown" });
      const spread = page.getByRole("button", { name: /^Spread/ });
      const totals = page.getByRole("button", { name: /^Totals/ });
      await expect(weekly.getByText("Total", { exact: true }).first()).toBeVisible();
      await spread.click();
      await expect(spread).toHaveAttribute("aria-pressed", "true");
      await expect(weekly.getByText("Spread", { exact: true }).first()).toBeVisible();
      await expect(weekly.getByText("Total", { exact: true })).toHaveCount(0);
      await totals.click();
      await expect(spread).toHaveAttribute("aria-pressed", "false");
      await expect(weekly.getByText("Spread", { exact: true })).toHaveCount(0);
      await totals.click();
      await expect(totals).toHaveAttribute("aria-pressed", "false");
      await expect(weekly.getByText("Spread", { exact: true }).first()).toBeVisible();
      await expect(weekly.getByText("Total", { exact: true }).first()).toBeVisible();
    });

    test("the explainers live in one collapsed disclosure", async ({ page }) => {
      await gotoHydrated(page, "/model");
      const explainer = page.getByText(/Win rate excludes pushes/).filter({ visible: true });
      await expect(explainer).toHaveCount(0);
      await page.getByText("About this record", { exact: true }).click();
      await expect(explainer).toHaveCount(1);
    });
  });
}
