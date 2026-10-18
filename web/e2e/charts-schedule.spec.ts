import fs from "node:fs";
import { expect, test } from "@playwright/test";
import { openTable } from "./helpers";

// Fixture: adjusted windows Through Week 2-3 for 16 of 17 roster teams (Wyoming has no
// games; Notre Dame has no defense row Through Week 3). See src/test/fixtures/charts.ts.
const PLOTTED = 16;

function pngSize(path: string): { width: number; height: number } {
  const bytes = fs.readFileSync(path);
  expect(bytes.subarray(1, 4).toString("ascii")).toBe("PNG");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

test.describe("schedule adjustment chart", () => {
  test("renders one dumbbell per team, Through Week N, with both readings explained", async ({ page }) => {
    await page.goto("/charts?chart=schedule&side=offense&week=3");
    await expect(page.getByRole("heading", { name: "Schedule adjustment" })).toBeVisible();
    await expect(page.getByTestId("chart-subtitle")).toHaveText("Offense | 2026 | FBS vs FBS | Through Week 3");
    const chart = page.getByTestId("schedule-chart");
    await expect(chart.locator("g[data-team]")).toHaveCount(PLOTTED);
    await expect(chart).toHaveAttribute("data-inverted", "false");
    await expect(chart.getByText(/raw understated: tougher opponents than average/)).toBeVisible();
    // A group of 30 or fewer shows everyone; no "Show all" toggle or omitted marker.
    await expect(page.getByTestId("schedule-show-all")).toHaveCount(0);
    await expect(page.getByTestId("schedule-omitted")).toHaveCount(0);
    await expect(page.getByTestId("unavailable-teams")).toContainText("Wyoming");
  });

  test("defense inverts the axis and says so", async ({ page }) => {
    await page.goto("/charts?chart=schedule&side=defense&week=3");
    await expect(page.getByTestId("schedule-chart")).toHaveAttribute("data-inverted", "true");
    await expect(page.getByTestId("schedule-axis-label")).toContainText("allowed (axis inverted: better is right)");
    await expect(page.getByTestId("schedule-inverted-note")).toBeVisible();
    await expect(page.getByTestId("schedule-chart").locator("g[data-team='Notre Dame']")).toHaveCount(0);
  });

  test("the table toggle lists the drawn rows with the decomposition", async ({ page }) => {
    await page.goto("/charts?chart=schedule&week=3");
    await openTable(page);
    const table = page.getByTestId("chart-table");
    await expect(table.locator("tbody tr")).toHaveCount(PLOTTED);
    for (const header of ["Position", "Raw PPA/play", "Venue correction", "Venue-neutral", "Adjusted", "Schedule effect", "Reading"]) {
      await expect(table.getByRole("columnheader", { name: header, exact: true })).toBeVisible();
    }
    await expect(table.locator("tbody tr").first()).toContainText(/raw (understated|inflated)/);
    await page.getByTestId("table-toggle").click();
    await expect(page.getByTestId("schedule-chart")).toBeVisible();
  });

  test("rows are keyboard reachable with a tooltip carrying the decomposition", async ({ page }) => {
    await page.goto("/charts?chart=schedule&week=3");
    const first = page.getByTestId("schedule-chart").locator("g[data-team]").first();
    const tooltip = page.getByTestId("chart-tooltip");
    // Focus handlers attach on hydration; retry until the tooltip responds.
    await expect(async () => {
      await first.blur();
      await first.focus();
      await expect(tooltip).toBeVisible({ timeout: 500 });
    }).toPass();
    const firstTeam = await first.getAttribute("data-team");
    await expect(tooltip).toContainText(new RegExp(`${firstTeam} .*raw .*venue correction .*venue-neutral .*adjusted .*schedule effect`));
    await page.keyboard.press("ArrowDown");
    const focused = await page.evaluate(() => document.activeElement?.getAttribute("data-team"));
    expect(focused).toBeTruthy();
    expect(focused).not.toBe(firstTeam);
    await expect(tooltip).toContainText(focused ?? "");
    await expect(page.locator("g[data-team]:focus .focus-ring")).toHaveCSS("opacity", "1");
    await page.keyboard.press("Enter");
    await expect(page.locator(`g[data-team='${focused}']`)).toHaveAttribute("aria-pressed", "true");
    await expect(page).toHaveURL(/team=/);
    await page.keyboard.press("Escape");
    await expect(tooltip).toHaveCount(0);
  });

  test("PNG export is 2000 px wide and tall enough for every drawn row", async ({ page }) => {
    await page.goto("/charts?chart=schedule&week=3");
    await page.waitForLoadState("networkidle");
    const download = page.waitForEvent("download");
    await page.getByTestId("chart-download").click();
    const file = await (await download).path();
    const size = pngSize(file);
    expect(size.width).toBe(2000);
    expect(size.height).toBeGreaterThanOrEqual(1125);
    const report = JSON.parse((await page.getByTestId("chart-export").getAttribute("data-last-export")) ?? "{}");
    expect(report.decoded).toBe(report.logos);
    expect(report.logos).toBeGreaterThan(0);
  });

  test("the team param seeds the highlight and persists to and from other charts", async ({ page }) => {
    await page.goto("/charts?chart=adjusted&week=3&team=michigan");
    await page.getByRole("link", { name: "Schedule adjustment" }).click();
    await expect(page).toHaveURL(/chart=schedule.*team=michigan/);
    const michigan = page.getByTestId("schedule-chart").locator("g[data-team='Michigan']");
    await expect(michigan).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("highlight-status")).toContainText("Michigan");
    await page.getByRole("link", { name: "defense", exact: true }).click();
    await expect(page).toHaveURL(/chart=schedule.*side=defense.*team=michigan/);
    await expect(michigan).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("link", { name: "Efficiency", exact: true }).click();
    await expect(page).toHaveURL(/chart=efficiency.*team=michigan/);
    await expect(page.locator("g[data-team='Michigan']")).toHaveAttribute("aria-pressed", "true");
  });
});

test("schedule national subset cuts ties at 15 and retains an omitted highlighted team", async ({ page }) => {
  await page.goto("/charts?chart=schedule&fixture=schedule&week=3");
  const chart = page.getByTestId("schedule-chart");
  const rows = chart.locator("g[data-team]");
  const teams = (await page.getByTestId("team-highlight").locator("option").allTextContents()).slice(2);
  expect(teams).toHaveLength(40);
  const expected = [...teams.slice(0, 15), ...teams.slice(-15)];
  await expect(rows).toHaveCount(30);
  expect(await rows.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-team")))).toEqual(expected);
  await expect(page.getByTestId("schedule-omitted")).toContainText("10");
  await page.getByTestId("schedule-show-all").click();
  await expect(rows).toHaveCount(40);
  expect(await rows.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-team")))).toEqual(teams);
  await page.getByTestId("schedule-show-all").click();
  await page.getByTestId("team-highlight").selectOption(teams[19]);
  await expect(rows).toHaveCount(31);
  expect(await rows.last().getAttribute("data-team")).toBe(teams[19]);
  await expect(chart).toContainText("20 of 40");
  await expect(rows.last()).toHaveAttribute("aria-pressed", "true");
  await openTable(page);
  const table = page.getByTestId("chart-table");
  await expect(table.locator("tbody tr")).toHaveCount(31);
  await expect(table.getByRole("cell", { name: teams[19], exact: true })).toBeVisible();
  await expect(table).toContainText("raw understated: tougher opponents than average");
  await expect(table).toContainText("raw inflated: weaker opponents");
});
