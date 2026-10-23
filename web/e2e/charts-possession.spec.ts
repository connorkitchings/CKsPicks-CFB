import fs from "node:fs";
import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

// Fixture: possession windows as_of_week 3 and 4 (Through Weeks 2-3) for 16 teams
// (Wyoming has none). App State has no defense rows Through Week 2; Boise State's
// Through Week 3 defense points per possession has no adjusted value, while its PPA
// per possession does. See chartsPossessionFixture in src/test/fixtures/charts.ts.

function pngSize(path: string): { width: number; height: number } {
  const bytes = fs.readFileSync(path);
  expect(bytes.subarray(1, 4).toString("ascii")).toBe("PNG");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

test.describe("possession efficiency chart", () => {
  test("plots teams with both roles, counts the rest, and switches measurement and window", async ({ page }) => {
    await page.goto("/stats?chart=possession");
    await expect(page.getByRole("heading", { name: "Possession efficiency" })).toBeVisible();
    await expect(page.getByTestId("chart-subtitle")).toHaveText("2026 · FBS teams, all games · Through Week 3");
    const chart = page.getByTestId("scatter-chart");
    await expect(chart.locator("g[data-team]")).toHaveCount(15);
    await expect(page.getByTestId("unavailable-teams")).toContainText("Not plotted (2 teams)");
    await expect(page.getByTestId("unavailable-teams")).toContainText("Boise State, Wyoming");
    await expect(page.getByTestId("average-lines")).toBeVisible();
    // One caption says which way is better on every scatter; the chart has no extra axis note of its own.
    await expect(page.getByTestId("direction-caption")).toHaveText("Up and right is better ↗");
    await expect(page.getByText("Defense axis inverted")).toHaveCount(0);
    await expect(page.locator("[data-iso-net]")).toHaveCount(0);
    await expect(page.getByText("Adjusted offense points per possession", { exact: true })).toBeVisible();
    await expect(page.getByText(/^Adjusted points per possession: opponent-adjusted/).first()).toBeVisible();

    await page.getByTestId("possession-metric-epa-per-possession").click();
    await expect(page.getByTestId("possession-metric-epa-per-possession")).toHaveAttribute("aria-pressed", "true");
    await expect(chart.locator("g[data-team]")).toHaveCount(16);
    await expect(page.getByTestId("unavailable-teams")).toContainText("Not plotted (1 teams)");
    await expect(page.getByText("Adjusted defense PPA per possession allowed", { exact: true })).toBeVisible();
    await expect(page.getByText(/^Adjusted PPA per possession: opponent-adjusted/).first()).toBeVisible();

    await page.getByLabel("Through Week", { exact: true }).selectOption("2");
    await expect(page).toHaveURL(/week=2/);
    await expect(page.getByTestId("chart-subtitle")).toHaveText("2026 · FBS teams, all games · Through Week 2");
    await expect(page.getByTestId("unavailable-teams")).toContainText("App State");
    await expect(page.getByTestId("scatter-chart").locator("g[data-team='App State']")).toHaveCount(0);
  });

  test("a URL metric seeds the switcher and the window starts at Through Week 2", async ({ page }) => {
    await page.goto("/stats?chart=possession&week=0&metric=epa_per_possession");
    await expect(page.getByTestId("possession-metric-epa-per-possession")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("chart-subtitle")).toHaveText("2026 · FBS teams, all games · Through Week 2");
    await expect(page.getByLabel("Through Week", { exact: true }).locator("option")).toHaveText(["2", "3"].map((w) => new RegExp(w)));
  });

  test("points are keyboard reachable with the raw, adjusted and rank tooltip", async ({ page }) => {
    await page.goto("/stats?chart=possession&week=3");
    const first = page.getByTestId("scatter-chart").locator("g[data-team]").first();
    const tooltip = page.getByTestId("chart-tooltip");
    await expect(async () => {
      await first.blur();
      await first.focus();
      await expect(tooltip).toBeVisible({ timeout: 500 });
    }).toPass();
    const team = await first.getAttribute("data-team");
    await expect(tooltip).toContainText(`${team} (`);
    await expect(tooltip).toContainText("points per possession: offense adjusted");
    // Through Week 3 is as_of_week 4: three games behind each value.
    await expect(tooltip).toContainText(/offense adjusted \d\.\d\d \(raw \d\.\d\d, opponent adjustment -?\d\.\d\d, 3 games\), \d+(st|nd|rd|th) of 15/);
    await expect(tooltip).toContainText("defense allowed adjusted");
    await page.keyboard.press("ArrowRight");
    const focused = await page.evaluate(() => document.activeElement?.getAttribute("data-team"));
    expect(focused).not.toBe(team);
    await page.keyboard.press("Enter");
    await expect(page.locator(`g[data-team='${focused}']`)).toHaveAttribute("data-state", "searched");
    await page.keyboard.press("Escape");
    await expect(tooltip).toHaveCount(0);
  });

  test("PNG export is 2000x1125 and named for the measurement and window", async ({ page }) => {
        await gotoHydrated(page, "/stats?chart=possession&week=3&team=Alabama");
    let download = page.waitForEvent("download");
    await page.getByTestId("chart-download").click();
    expect((await download).suggestedFilename()).toBe("ckspicks-possession-ppp-2026-through-week-3.png");
    expect(pngSize(await (await download).path())).toEqual({ width: 2000, height: 1125 });
    const report = JSON.parse((await page.getByTestId("chart-export").getAttribute("data-last-export")) ?? "{}");
    expect(report.logos).toBeGreaterThan(0);
    expect(report.decoded).toBe(report.logos);

    await page.getByTestId("possession-metric-epa-per-possession").click();
    download = page.waitForEvent("download");
    await page.getByTestId("chart-download").click();
    expect((await download).suggestedFilename()).toBe("ckspicks-possession-ppa-per-possession-2026-through-week-3.png");
  });

  test("the highlighted team persists across chart switches and windows", async ({ page }) => {
    await page.goto("/stats?chart=adjusted&week=2&team=Michigan");
    await page.getByRole("navigation", { name: "Chart type" }).getByRole("link", { name: "Possession efficiency", exact: true }).click();
    await expect(page).toHaveURL(/chart=possession/);
    await expect(page).toHaveURL(/week=2/);
    await expect(page).toHaveURL(/team=Michigan/);
    await expect(page.locator("g[data-team='Michigan']")).toHaveAttribute("data-state", "searched");
    await page.getByLabel("Through Week", { exact: true }).selectOption("3");
    await expect(page).toHaveURL(/week=3/);
    await expect(page).toHaveURL(/team=Michigan/);
    await expect(page.locator("g[data-team='Michigan']")).toHaveAttribute("data-state", "searched");
  });

  test("a failing possession window shows the unavailable notice", async ({ page }) => {
    await page.goto("/stats?chart=possession&week=3&fixture=adjusted-error");
    await expect(page.getByTestId("charts-notice")).toHaveText("Charts are temporarily unavailable.");
    await expect(page.locator("#week-select")).toHaveCount(0);
  });
});

test("possession stays horizontally scrollable at 390px without page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto("/stats?chart=possession&team=Alabama");
  const scroll = page.getByTestId("scatter-scroll");
  await expect(scroll).toBeVisible();
  await expect.poll(() => scroll.evaluate((node) => node.scrollWidth > node.clientWidth)).toBe(true);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
