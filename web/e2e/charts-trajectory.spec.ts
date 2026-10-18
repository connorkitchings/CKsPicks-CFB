import fs from "node:fs";
import { expect, test } from "@playwright/test";
import { openTable } from "./helpers";

// Fixture: 17-team roster (Wyoming has no games), adjusted windows as_of_week 3 and 4
// (Through Weeks 2-3); Notre Dame has no defense row in the second window, so its net
// trajectory is a single dot. See src/test/fixtures/charts.ts.
const PLOTTED = 16;
const SEC_TEAMS = 4;

function pngSize(path: string): { width: number; height: number } {
  const bytes = fs.readFileSync(path);
  expect(bytes.subarray(1, 4).toString("ascii")).toBe("PNG");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

// Skipped: `trajectory` is hidden from /charts (`ready: false` in src/lib/chart-config.ts).
test.describe.skip("team trajectory chart", () => {
  test("renders every team across the stored windows with the FBS average and no week selector", async ({ page }) => {
    await page.goto("/charts?chart=trajectory");
    await expect(page.getByRole("heading", { name: "Team trajectory" })).toBeVisible();
    await expect(page.getByTestId("chart-subtitle")).toHaveText("Net · 2026 · FBS vs FBS · Through Weeks 2–3");
    const chart = page.getByTestId("trajectory-chart");
    await expect(chart.locator("g[data-team]")).toHaveCount(PLOTTED);
    await expect(chart.locator("g[data-team='Wyoming']")).toHaveCount(0);
    await expect(chart.locator("g[data-team][data-state='context']")).toHaveCount(PLOTTED);
    await expect(page.getByTestId("trajectory-average").locator("path")).toHaveCount(1);
    // Net needs both roles: Notre Dame's lone window is a dot, not a line.
    const notreDame = chart.locator("g[data-team='Notre Dame']");
    await expect(notreDame.getByTestId("trajectory-dot")).toHaveAttribute("data-week", "2");
    await expect(notreDame.getByTestId("trajectory-line")).toHaveCount(0);
    await expect(chart.locator("g[data-team='Alabama']").getByTestId("trajectory-line")).toHaveAttribute("data-weeks", "2,3");
    await expect(page.locator("#week-select")).toHaveCount(0);
    await expect(page.getByTestId("unavailable-teams")).toContainText("Wyoming");

    await page.getByTestId("trajectory-metric-defense").click();
    await expect(chart).toHaveAttribute("data-invert-y", "true");
    await expect(page.getByText("Axis inverted: up is better defense (less allowed).")).toBeVisible();
    await expect(page.getByText("Adjusted defense PPA/play allowed", { exact: true })).toBeVisible();
    await page.getByTestId("trajectory-metric-offense").click();
    await expect(chart).toHaveAttribute("data-invert-y", "false");
    await expect(notreDame.getByTestId("trajectory-line")).toHaveAttribute("data-weeks", "2,3");
  });

  test("a URL metric seeds the switcher", async ({ page }) => {
    await page.goto("/charts?chart=trajectory&metric=defense");
    await expect(page.getByTestId("trajectory-metric-defense")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("trajectory-chart")).toHaveAttribute("data-invert-y", "true");
  });

  test("the conference filter colors its teams with end logos, and the table lists the group", async ({ page }) => {
    await page.goto("/charts?chart=trajectory");
    await page.getByTestId("conference-filter").selectOption("SEC");
    const chart = page.getByTestId("trajectory-chart");
    await expect(chart.locator("g[data-team][data-state='group']")).toHaveCount(SEC_TEAMS);
    await expect(chart.locator("g[data-team][data-state='context']")).toHaveCount(PLOTTED - SEC_TEAMS);
    await expect(chart.locator("g[data-team='Alabama'] g[data-mark='logo']")).toHaveCount(1);
    await expect(chart.locator("g[data-team='Michigan'] g[data-mark]")).toHaveCount(0);
    // Logos can move vertically along the endpoint rail; plotted values stay put.
    const endpoints = await chart.getByTestId("trajectory-endpoint").evaluateAll((nodes) => nodes.map((node) => ({
      y: Number(node.getAttribute("data-y")), size: Number(node.getAttribute("data-size")),
    })).sort((a, b) => a.y - b.y));
    for (let i = 1; i < endpoints.length; i++) {
      expect(endpoints[i].y - endpoints[i].size / 2).toBeGreaterThanOrEqual(endpoints[i - 1].y + endpoints[i - 1].size / 2 + 3.99);
    }

    await openTable(page);
    const table = page.getByTestId("chart-table");
    await expect(table.locator("tbody tr")).toHaveCount(SEC_TEAMS);
    await expect(table.getByRole("columnheader", { name: "Through Week 3" })).toBeVisible();
    await page.getByTestId("conference-filter").selectOption("FBS Independents");
    await expect(table.locator("tbody tr")).toHaveCount(1);
    await expect(table.locator("tbody tr").first()).toContainText("n/a");
  });

  test("lines are keyboard reachable with a tooltip, and Enter highlights a team", async ({ page }) => {
    await page.goto("/charts?chart=trajectory");
    const first = page.getByTestId("trajectory-chart").locator("g[data-team]").first();
    const tooltip = page.getByTestId("chart-tooltip");
    await expect(async () => {
      await first.blur();
      await first.focus();
      await expect(tooltip).toBeVisible({ timeout: 500 });
    }).toPass();
    const firstTeam = await first.getAttribute("data-team");
    await expect(tooltip).toContainText(`${firstTeam} (`);
    await expect(tooltip).toContainText("Through Week 2");
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
    await page.keyboard.press(" ");
    await expect(page.locator(`g[data-team='${focused}']`)).toHaveAttribute("data-state", "context");
    await page.keyboard.press("End");
    await expect(page.getByTestId("trajectory-chart").locator("g[data-team]").last()).toBeFocused();
    await page.keyboard.press("Home");
    await expect(page.getByTestId("trajectory-chart").locator("g[data-team='Alabama']")).toBeFocused();
  });

  test("PNG export is 2000x1125 with the highlighted team's logo decoded", async ({ page }) => {
    await page.goto("/charts?chart=trajectory&team=Alabama");
    await page.waitForLoadState("networkidle");
    const download = page.waitForEvent("download");
    await page.getByTestId("chart-download").click();
    const file = await (await download).path();
    expect((await download).suggestedFilename()).toBe("ckspicks-trajectory-net-2026.png");
    expect(pngSize(file)).toEqual({ width: 2000, height: 1125 });
    const report = JSON.parse((await page.getByTestId("chart-export").getAttribute("data-last-export")) ?? "{}");
    expect(report.logos).toBeGreaterThan(0);
    expect(report.decoded).toBe(report.logos);
  });

  test("the highlighted team persists into and out of the trajectory chart", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3&team=Michigan");
    await page.getByRole("navigation", { name: "Chart type" }).getByRole("link", { name: "Trajectory", exact: true }).click();
    await expect(page).toHaveURL(/chart=trajectory/);
    await expect(page).toHaveURL(/team=Michigan/);
    await expect(page.locator("g[data-team='Michigan']")).toHaveAttribute("data-state", "highlight");
    await expect(page.getByTestId("highlight-status")).toContainText("Highlight: Michigan");

    await page.getByRole("combobox", { name: "Highlight a team" }).fill("Oregon");
    await page.getByRole("option", { name: /^Oregon/ }).click();
    await expect(page).toHaveURL(/team=Oregon/);
    await page.getByRole("navigation", { name: "Chart type" }).getByRole("link", { name: "Adjusted PPA/play", exact: true }).click();
    await expect(page).toHaveURL(/chart=adjusted/);
    await expect(page.locator("g[data-team='Oregon']")).toHaveAttribute("data-state", "searched");
  });
});


// Skipped: `trajectory` is hidden from /charts (`ready: false` in src/lib/chart-config.ts).
test.skip("trajectory remains horizontally scrollable with a readable table at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto("/charts?chart=trajectory&team=Alabama");
  const scroll = page.getByTestId("trajectory-scroll");
  await expect(scroll).toBeVisible();
  await expect.poll(() => scroll.evaluate((node) => node.scrollWidth > node.clientWidth)).toBe(true);
  await scroll.focus();
  await page.keyboard.press("ArrowRight");
  await expect.poll(() => scroll.evaluate((node) => node.scrollLeft)).toBeGreaterThan(0);
  await openTable(page);
  await expect(page.getByTestId("chart-table")).toBeVisible();
  await expect(page.getByTestId("chart-table").locator("tbody tr")).toHaveCount(PLOTTED);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
