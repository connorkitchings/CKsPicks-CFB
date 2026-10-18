import fs from "node:fs";
import { expect, test } from "@playwright/test";

test.describe("team game log", () => {
  test("shows the whole release, weekly references, national ranks and ordered table", async ({ page }) => {
    await page.goto("/charts?chart=game-log&team=alabama&week=0");
    await expect(page.getByRole("heading", { name: "Team game log" })).toBeVisible();
    await expect(page.getByTestId("chart-subtitle")).toHaveText("Alabama | 2026 | FBS opponents only | Through Week 3");
    for (const side of ["offense", "defense"]) await expect(page.getByTestId(`game-log-rank-${side}`)).toHaveText(/\d+(st|nd|rd|th) of 16 nationally/);
    const games = page.getByTestId("game-log-chart").locator("g[data-game]");
    await expect(games).toHaveCount(4);
    expect(await games.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("aria-label")?.match(/^Week (\d)/)?.[1]))).toEqual(["0", "1", "2", "3"]);
    await expect(page.getByTestId("game-log-panel-defense")).toContainText("axis inverted: up is better");
    await expect(page.getByTestId("game-log-chart").locator("[data-average]")).toHaveCount(8);
    await expect(page.getByTestId("game-log-chart").getByText(/^[WLT] \d+-\d+$/)).toHaveCount(4);
    await page.getByTestId("table-toggle").click();
    const table = page.getByTestId("chart-table");
    await expect(table.locator("tbody tr")).toHaveCount(4);
    expect(await table.locator("tbody tr td:first-child").allTextContents()).toEqual(["0", "1", "2", "3"]);
    for (const name of ["Opponent", "Result", "FBS week average (offense)", "FBS week average (defense)"]) await expect(table.getByRole("columnheader", { name, exact: true })).toBeVisible();
    await page.getByTestId("table-toggle").click();
    await expect(page.getByTestId("game-log-chart")).toBeVisible();
  });

  test("capability controls metrics and a team without games stays selectable", async ({ page }) => {
    await page.goto("/charts?chart=game-log&fixture=v1&team=alabama&metric=explosive_rate");
    await expect(page.getByTestId("game-log-metric-explosive-rate")).toHaveCount(0);
    await expect(page.getByTestId("game-log-metric-success")).toHaveAttribute("aria-pressed", "true");
    await page.goto("/charts?chart=game-log&team=alabama");
    await page.getByTestId("game-log-metric-explosive-rate").click();
    await expect(page.getByTestId("game-log-metric-explosive-rate")).toHaveAttribute("aria-pressed", "true");
    await page.getByTestId("game-log-metric-ppa").click();
    await expect(page.getByTestId("game-log-header")).toContainText("PPA/play");
    const picker = page.getByRole("combobox", { name: "Highlight a team" });
    await picker.fill("Wyoming");
    await picker.press("Enter");
    await expect(page.getByTestId("chart-empty")).toHaveText("Wyoming has no FBS games in this release yet.");
    await expect(page.getByTestId("chart-download")).toHaveCount(0);
    await expect(page).toHaveURL(/team=wyoming/i);
  });

  test("arrow keys reach games and show each game's tooltip", async ({ page }) => {
    await page.goto("/charts?chart=game-log&team=alabama");
    const games = page.getByTestId("game-log-chart").locator("g[data-game]");
    const tooltip = page.getByTestId("chart-tooltip");
    await expect(async () => {
      await games.first().blur();
      await games.first().focus();
      await expect(tooltip).toContainText("Week 0:", { timeout: 500 });
    }).toPass();
    await page.keyboard.press("ArrowRight");
    await expect(tooltip).toContainText("Week 1:");
    await page.keyboard.press("End");
    await expect(tooltip).toContainText("Week 3:");
    await page.keyboard.press("Home");
    await expect(tooltip).toContainText(/offense .*FBS week average .*defense allowed/);
    await expect(games.first().locator(".focus-ring")).toHaveCSS("opacity", "1");
    await page.keyboard.press("Escape");
    await expect(tooltip).toHaveCount(0);
  });

  test("PNG export includes decoded logos at 2000 by 1125 pixels", async ({ page }) => {
    await page.goto("/charts?chart=game-log&team=alabama");
    await page.waitForLoadState("networkidle");
    const download = page.waitForEvent("download");
    await page.getByTestId("chart-download").click();
    const bytes = fs.readFileSync(await (await download).path());
    expect(bytes.subarray(1, 4).toString("ascii")).toBe("PNG");
    expect([bytes.readUInt32BE(16), bytes.readUInt32BE(20)]).toEqual([2000, 1125]);
    const report = JSON.parse((await page.getByTestId("chart-export").getAttribute("data-last-export")) ?? "{}");
    expect(report.decoded).toBe(report.logos);
    expect(report.logos).toBeGreaterThan(0);
  });

  test("team selection survives rapid changes, chart navigation, reload and browser history", async ({ page }) => {
    await page.goto("/charts?chart=adjusted&week=3&team=alabama");
    await page.waitForLoadState("networkidle");
    const picker = page.getByTestId("team-highlight");
    await picker.selectOption("Michigan");
    await picker.selectOption("Georgia");
    await picker.selectOption("");
    await picker.selectOption("Texas");
    await expect(page).toHaveURL(/team=texas/i);
    await expect(page.getByTestId("team-search")).toHaveValue("Texas");
    await page.getByRole("link", { name: "Game log", exact: true }).click();
    await expect(page.getByTestId("chart-subtitle")).toContainText("Texas |");
    await expect(page).toHaveURL(/chart=game-log.*team=texas/i);
    await page.reload();
    await expect(page.getByTestId("team-search")).toHaveValue("Texas");
    await page.goBack();
    await expect(page).toHaveURL(/chart=adjusted.*team=texas/i);
    await expect(page.getByTestId("team-search")).toHaveValue("Texas");
    await page.goForward();
    await expect(page).toHaveURL(/chart=game-log.*team=texas/i);
    await expect(page.getByTestId("chart-subtitle")).toHaveCount(1);
    await expect(page.getByTestId("chart-subtitle")).toContainText("Texas |");
  });
});
