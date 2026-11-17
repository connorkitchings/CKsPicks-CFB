import { expect, test } from "@playwright/test";
import { gotoHydrated, openTable } from "./helpers";

test.describe("bar chart tabs: toolbar, table, outlier cap", () => {
  test("table toggle shares a row with the conference filter at desktop width", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await gotoHydrated(page, "/stats?chart=efficiency&week=3");
    const toggle = await page.getByTestId("table-toggle").boundingBox();
    const filter = await page.getByTestId("conference-filter").boundingBox();
    expect(toggle && filter).toBeTruthy();
    // Actions stay on the first row, top-aligned with the first control.
    expect(Math.abs(toggle!.y - filter!.y)).toBeLessThanOrEqual(2);
  });

  test("net success offers a table with one row per game and a key under the summary", async ({ page }) => {
    await gotoHydrated(page, "/stats?chart=net-success&week=3");
    await expect(page.getByTestId("net-success-key")).toBeVisible();
    await expect(page.getByTestId("net-success-key")).toHaveText("Logo past the bar end: winner · logo across the zero line: loser");
    await expect(page.getByTestId("table-toggle")).toHaveCount(1);
    const games = await page.getByTestId("net-success-chart").locator("g[data-game]").count();
    await openTable(page);
    await expect(page.getByTestId("chart-table")).toBeVisible();
    await expect(page.getByTestId("chart-table").locator("tbody tr")).toHaveCount(games);
  });

  test("an outlier bar is cut at the cap with a break mark and its true value", async ({ page }) => {
    await gotoHydrated(page, "/stats?chart=net-success&week=3");
    const chart = page.getByTestId("net-success-chart");
    const breaks = chart.locator("[data-bar-break]");
    await expect(breaks.first()).toBeAttached();
    const bar = chart.locator("g[data-game]").filter({ has: page.locator("[data-bar-break]") }).first();
    const label = (await bar.getAttribute("aria-label"))!;
    const magnitude = label.match(/([\d.]+) percentage points/)![1];
    const trueValue = label.includes("disadvantage") ? `-${magnitude}` : magnitude;
    await expect(bar.locator("[data-break-value]")).toHaveText(trueValue);
  });
});
