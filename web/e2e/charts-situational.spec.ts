import fs from "node:fs";
import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

// Fixtures: `seasonStatsFor` windows as_of_week 3 and 4 (Through Weeks 2-3). The default
// fixture covers the 16 playing teams; `fixture=slate` covers all 138 logo-bearing schools
// (the dense layout). See chartsSeasonStatsFixture and chartsSlateSeasonStatsFixture in
// src/test/fixtures/charts.ts. Quadrant names are not asserted: they change with the copy.

const CHARTS = [
  { kind: "downs", title: "Situational downs" },
  { kind: "finishing-drives", title: "Finishing drives" },
] as const;

const WIDTHS = [320, 390, 800, 1280];

function pngSize(path: string): { width: number; height: number } {
  const bytes = fs.readFileSync(path);
  expect(bytes.subarray(1, 4).toString("ascii")).toBe("PNG");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

for (const { kind, title } of CHARTS) {
  test.describe(`${title} chart`, () => {
    for (const side of ["offense", "defense"] as const) {
      test(`${side} renders plotted teams and quadrant labels`, async ({ page }) => {
        await page.goto(`/stats?chart=${kind}&week=3&side=${side}`);
        await expect(page.getByRole("heading", { level: 2, name: title })).toBeVisible();
        await expect(page.getByTestId("chart-subtitle")).toContainText("Through Week 3");
        await expect(page.getByTestId("scatter-chart").locator("g[data-team]")).toHaveCount(16);
        const corners = page.locator('[data-testid="corner-labels"] [data-corner]');
        expect(await corners.count()).toBeGreaterThan(0);
        await expect(corners.first()).toBeAttached();
      });
    }

    test("the dense 138-team slate plots every school", async ({ page }) => {
      await page.goto(`/stats?chart=${kind}&week=3&fixture=slate`);
      await expect(page.getByTestId("scatter-chart").locator("g[data-team]")).toHaveCount(138);
    });

    test("a week switch changes the through-week window and the URL", async ({ page }) => {
      await page.goto(`/stats?chart=${kind}&week=3`);
      await page.getByLabel("Through Week", { exact: true }).selectOption("2");
      await expect(page).toHaveURL(/week=2/);
      await expect(page.getByTestId("chart-subtitle")).toContainText("Through Week 2");
    });

    test("the picker navigates to and from the chart", async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await gotoHydrated(page, "/stats?chart=net-success&week=3");
      await page.getByTestId("chart-picker").getByRole("link", { name: title, exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`chart=${kind}`));
      await expect(page.getByRole("heading", { level: 2, name: title })).toBeVisible();
      await expect(page.getByTestId("chart-picker").getByRole("link", { name: title, exact: true })).toHaveAttribute("aria-current", "page");
      await page.goBack();
      await expect(page).toHaveURL(/chart=net-success/);
      await expect(page.getByRole("heading", { level: 2, name: "Net success rate" })).toBeVisible();
    });

    test("PNG export is 2000x1125", async ({ page }) => {
      await gotoHydrated(page, `/stats?chart=${kind}&week=3`);
      const download = page.waitForEvent("download");
      await page.getByTestId("chart-download").click();
      const file = await (await download).path();
      expect(pngSize(file)).toEqual({ width: 2000, height: 1125 });
    });

    for (const width of WIDTHS) {
      test(`no horizontal page overflow at ${width}px on the dense slate`, async ({ page }) => {
        await page.setViewportSize({ width, height: 844 });
        await page.goto(`/stats?chart=${kind}&week=3&fixture=slate`);
        await expect(page.getByRole("heading", { level: 2, name: title })).toBeVisible();
        await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
      });
    }
  });
}

for (const chart of ["resume-quality", "market-board"]) {
  test(`hidden chart ${chart} falls back to net success`, async ({ page }) => {
    await page.goto(`/stats?chart=${chart}&week=3`);
    await expect(page.getByRole("heading", { level: 2, name: "Net success rate" })).toBeVisible();
    await expect(page.getByTestId("net-success-chart")).toBeVisible();
  });
}

for (const { kind, title } of CHARTS) {
  test(`${title} with a missing season stats window shows the unavailable notice`, async ({ page }) => {
    await page.goto(`/stats?chart=${kind}&week=3&fixture=season-stats-missing`);
    await expect(page.getByTestId("charts-notice")).toHaveText("Charts are temporarily unavailable.");
    await expect(page.getByRole("heading", { level: 2, name: title })).toHaveCount(0);
    await expect(page.getByTestId("scatter-chart")).toHaveCount(0);
    await expect(page.locator("#week-select")).toHaveCount(0);
  });
}
