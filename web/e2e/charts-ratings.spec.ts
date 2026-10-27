import fs from "node:fs";
import { expect, test } from "@playwright/test";
import { gotoHydrated, openTable } from "./helpers";

// Fixture: `current` V5 rating snapshots for weeks 0-3 of 16 teams (Wyoming has none);
// Tulane has no week 2 snapshot, so its line breaks into weeks 0-1 and a lone week-3 dot.
// See chartsRatingSnapshotsFixture in src/test/fixtures/charts.ts.
const PLOTTED = 16;

function pngSize(path: string): { width: number; height: number } {
  const bytes = fs.readFileSync(path);
  expect(bytes.subarray(1, 4).toString("ascii")).toBe("PNG");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

// Skipped: `rating-trajectory` is hidden from /stats (`ready: false` in src/lib/chart-config.ts).
test.describe.skip("V5 rating trajectory chart", () => {
  test("renders every team from Through Week 0 with the weekly FBS mean and no week selector", async ({ page }) => {
    await page.goto("/stats?chart=rating-trajectory");
    await expect(page.getByRole("heading", { name: "V5 rating trajectory" })).toBeVisible();
    await expect(page.getByTestId("chart-subtitle")).toHaveText("Overall · 2026 · FBS teams · Through Weeks 0–3");
    const chart = page.getByTestId("trajectory-chart");
    await expect(chart).toHaveAttribute("data-invert-y", "false");
    await expect(chart.locator("g[data-team]")).toHaveCount(PLOTTED);
    await expect(chart.locator("g[data-team='Wyoming']")).toHaveCount(0);
    await expect(page.getByTestId("unavailable-teams")).toContainText("Wyoming");
    const tulane = chart.locator("g[data-team='Tulane']");
    await expect(tulane.getByTestId("trajectory-line")).toHaveAttribute("data-weeks", "0,1");
    await expect(tulane.getByTestId("trajectory-dot")).toHaveAttribute("data-week", "3");
    await expect(page.getByTestId("trajectory-average").locator("path")).toHaveCount(1);
    await expect(page.getByTestId("trajectory-average")).toContainText("FBS mean");
    await expect(page.locator("#week-select")).toHaveCount(0);
    await expect(page.getByText("not centered at zero", { exact: false }).first()).toBeVisible();
    await expect(page.getByText("V5 overall rating", { exact: true })).toBeVisible();

    const overall = await page.getByTestId("trajectory-average").getAttribute("data-average");
    await page.getByTestId("rating-metric-defense").click();
    await expect(page.getByTestId("rating-metric-defense")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("chart-subtitle")).toHaveText("Defense · 2026 · FBS teams · Through Weeks 0–3");
    await expect(page.getByText("V5 defense rating", { exact: true })).toBeVisible();
    // Defense ratings are higher-is-better, so the axis stays upright.
    await expect(chart).toHaveAttribute("data-invert-y", "false");
    await expect(page.getByTestId("trajectory-average")).not.toHaveAttribute("data-average", overall ?? "");
  });

  test("a URL metric seeds the switcher", async ({ page }) => {
    await page.goto("/stats?chart=rating-trajectory&metric=offense");
    await expect(page.getByTestId("rating-metric-offense")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("V5 offense rating", { exact: true })).toBeVisible();
  });

  test("the table lists each week's rating ± standard deviation and follows the group filter", async ({ page }) => {
    await page.goto("/stats?chart=rating-trajectory");
    await openTable(page);
    const table = page.getByTestId("chart-table");
    await expect(table.locator("tbody tr")).toHaveCount(PLOTTED);
    await expect(table.getByRole("columnheader", { name: "Through Week 0" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Through Week 3" })).toBeVisible();
    await expect(table.locator("tbody tr", { hasText: "Alabama" })).toContainText(/-?\d\.\d\d ± \d\.\d\d/);
    await page.getByTestId("conference-filter").selectOption("American Athletic");
    await expect(table.locator("tbody tr")).toHaveCount(1);
    await expect(table.locator("tbody tr").first()).toContainText("n/a");
  });

  test("lines are keyboard reachable with a rating ± sd and rank tooltip, and Enter highlights", async ({ page }) => {
    await page.goto("/stats?chart=rating-trajectory");
    const first = page.getByTestId("trajectory-chart").locator("g[data-team]").first();
    const tooltip = page.getByTestId("chart-tooltip");
    await expect(async () => {
      await first.blur();
      await first.focus();
      await expect(tooltip).toBeVisible({ timeout: 500 });
    }).toPass();
    const firstTeam = await first.getAttribute("data-team");
    await expect(tooltip).toContainText(`${firstTeam} (`);
    await expect(tooltip).toContainText("Through Week 3");
    await expect(tooltip).toContainText(/V5 overall rating -?\d\.\d\d ± \d\.\d\d, \d+(st|nd|rd|th) of 16/);
    await page.keyboard.press("ArrowRight");
    const focused = await page.evaluate(() => document.activeElement?.getAttribute("data-team"));
    expect(focused).not.toBe(firstTeam);
    await expect(tooltip).toContainText(focused ?? "");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(new RegExp(`team=${encodeURIComponent(focused ?? "").replace(/%20/g, "(\\+|%20)")}`));
    await expect(page.locator(`g[data-team='${focused}']`)).toHaveAttribute("data-state", "highlight");
    await expect(page.getByTestId("highlight-label")).toHaveText(focused ?? "");
    await page.keyboard.press("Escape");
    await expect(tooltip).toHaveCount(0);
  });

  test("PNG export is 2000x1125, named for the metric, with the highlighted logo decoded", async ({ page }) => {
        await gotoHydrated(page, "/stats?chart=rating-trajectory&metric=defense&team=Alabama");
    const download = page.waitForEvent("download");
    await page.getByTestId("chart-download").click();
    expect((await download).suggestedFilename()).toBe("stratum-rating-trajectory-defense-2026.png");
    expect(pngSize(await (await download).path())).toEqual({ width: 2000, height: 1125 });
    const report = JSON.parse((await page.getByTestId("chart-export").getAttribute("data-last-export")) ?? "{}");
    expect(report.logos).toBeGreaterThan(0);
    expect(report.decoded).toBe(report.logos);
  });

  test("the highlighted team persists into and out of the rating trajectory", async ({ page }) => {
    await page.goto("/stats?chart=trajectory&team=Michigan");
    const picker = page.getByRole("navigation", { name: "Chart type" });
    await picker.getByRole("link", { name: "V5 ratings", exact: true }).click();
    await expect(page).toHaveURL(/chart=rating-trajectory/);
    await expect(page).toHaveURL(/team=Michigan/);
    await expect(page.locator("g[data-team='Michigan']")).toHaveAttribute("data-state", "highlight");
    await expect(page.getByTestId("highlight-status")).toContainText("Highlight: Michigan");

    await page.getByRole("combobox", { name: "Highlight a team" }).fill("Oregon");
    await page.getByRole("option", { name: /^Oregon/ }).click();
    await expect(page).toHaveURL(/team=Oregon/);
    await picker.getByRole("link", { name: "Possession efficiency", exact: true }).click();
    await expect(page).toHaveURL(/chart=possession/);
    await expect(page).toHaveURL(/team=Oregon/);
    await expect(page.locator("g[data-team='Oregon']")).toHaveAttribute("data-state", "searched");
  });

  test("a failing snapshot query shows the unavailable notice under the picker", async ({ page }) => {
    await page.goto("/stats?chart=rating-trajectory&fixture=adjusted-error");
    await expect(page.getByTestId("charts-notice")).toHaveText("Charts are temporarily unavailable.");
    await expect(page.getByTestId("chart-picker")).toBeVisible();
  });
});

// Skipped: `rating-trajectory` is hidden from /stats (`ready: false` in src/lib/chart-config.ts).
test.skip("rating trajectory stays horizontally scrollable with a readable table at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto("/stats?chart=rating-trajectory&team=Alabama");
  const scroll = page.getByTestId("trajectory-scroll");
  await expect(scroll).toBeVisible();
  await expect.poll(() => scroll.evaluate((node) => node.scrollWidth > node.clientWidth)).toBe(true);
  await openTable(page);
  await expect(page.getByTestId("chart-table").locator("tbody tr")).toHaveCount(PLOTTED);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
