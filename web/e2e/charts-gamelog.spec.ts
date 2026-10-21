import fs from "node:fs";
import { expect, test } from "@playwright/test";

test.describe("team game log", () => {
  test("shows the whole release, weekly references, and national ranks", async ({ page }) => {
    await page.goto("/stats?chart=game-log&team=alabama&week=0");
    await expect(page.getByRole("heading", { name: "Alabama game log" })).toBeVisible();
    await expect(page.getByTestId("chart-subtitle")).toHaveText("Alabama · 2026 · FBS opponents only · Through Week 3");
    for (const side of ["offense", "defense"]) await expect(page.getByTestId(`game-log-rank-${side}`)).toHaveText(/\d+(st|nd|rd|th) of 16 nationally/);
    const games = page.getByTestId("game-log-chart").locator("g[data-game]");
    await expect(games).toHaveCount(4);
    expect(await games.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("aria-label")?.match(/^Week (\d)/)?.[1]))).toEqual(["0", "1", "2", "3"]);
    await expect(page.getByTestId("game-log-panel-defense")).toContainText("axis inverted: up is better");
    await expect(page.getByTestId("game-log-chart").locator("[data-average]")).toHaveCount(8);
    await expect(page.getByTestId("game-log-chart").getByText(/^[WLT] \d+-\d+$/)).toHaveCount(4);
  });

  test("bars carry their values, results are colored, every game says vs or @, and the header gives FBS context", async ({ page }) => {
    await page.goto("/stats?chart=game-log&team=alabama&week=0");
    const chart = page.getByTestId("game-log-chart");
    // One value label per bar, in both panels.
    const bars = await chart.locator("[data-bar]").count();
    await expect(chart.locator("[data-value-label]")).toHaveCount(bars);
    await expect(chart.locator("[data-value-label]").first()).toHaveText(/^\d+(\.\d)?%$/);
    // Wins and losses are told apart by letter and color; a loss also tints its column.
    const results = chart.locator("[data-result]");
    await expect(results).toHaveCount(4);
    const losses = await chart.locator("[data-result='L']").count();
    await expect(chart.locator("[data-loss-band]")).toHaveCount(losses);
    await expect(chart.locator("[data-result='W']").first()).toHaveAttribute("fill", "var(--win)");
    // Every game is marked vs (home or neutral) or @ (away), not only the away ones.
    await expect(chart.locator("[data-site-marker]")).toHaveCount(4);
    await expect(chart.locator("[data-site-marker]").filter({ hasText: /^(vs|@)$/ })).toHaveCount(4);
    await expect(chart.getByText(/· away/)).toHaveCount(0);
    // The scope and axis notes live in the subtitle and the panel title, not repeated under the figure.
    await expect(page.getByText("Defense axis is inverted: up is better defense.")).toHaveCount(0);
    await expect(page.getByTestId("game-log-panel-defense")).toContainText("axis inverted: up is better");
    // The header names the metric and window, and gives the FBS average beside each side.
    const header = page.getByTestId("game-log-header");
    await expect(header).toContainText(/^Success rate, through Week 3/);
    await expect(page.getByTestId("game-log-average-offense")).toHaveText(/^FBS avg \d/);
    await expect(page.getByTestId("game-log-average-defense")).toHaveText(/^FBS avg \d/);
    // Definitions live under the chart, once, for the selected metric; the scope note is not repeated there.
    const footnote = page.getByTestId("chart-footnote");
    await expect(footnote).toContainText("Success rate is the share of plays that gain 50%");
    await expect(footnote).not.toContainText("FBS opponents only");
    await page.getByTestId("game-log-metric-ppa").click();
    await expect(footnote).toContainText("PPA/play is the average predicted points added per play.");
    await expect(footnote).not.toContainText("Success rate is the share");
  });

  test("both panels draw at one pixels-per-unit scale, each fitted to its own values", async ({ page }) => {
    for (const metric of ["success", "ppa"]) {
      await page.goto(`/stats?chart=game-log&team=alabama&week=0&metric=${metric}`);
      const scales: number[] = [];
      const heights: number[] = [];
      for (const side of ["offense", "defense"]) {
        const panel = page.getByTestId(`game-log-panel-${side}`);
        heights.push(Number(await panel.locator("rect").first().getAttribute("height")));
        // Axis tick labels: value text and its y position.
        const ticks = await panel.locator("text[text-anchor='end']").evaluateAll((nodes) =>
          nodes.map((node) => ({ text: node.textContent ?? "", y: Number(node.getAttribute("y")) })));
        const parsed = ticks.map(({ text, y }) => ({ value: parseFloat(text.replace("%", "")), y }));
        expect(parsed.length).toBeGreaterThanOrEqual(2);
        scales.push(Math.abs((parsed[1].y - parsed[0].y) / (parsed[1].value - parsed[0].value)));
      }
      // Same pixels per unit in both panels (to within rounding of the printed ticks).
      expect(Math.abs(scales[0] - scales[1]) / scales[0]).toBeLessThan(0.02);
      // Neither panel is padded out to the other's range: the heights follow the data.
      expect(heights[0]).toBeGreaterThan(40);
      expect(heights[1]).toBeGreaterThan(40);
    }
  });

  test("capability controls metrics and a team without games stays selectable", async ({ page }) => {
    await page.goto("/stats?chart=game-log&fixture=v1&team=alabama&metric=explosive_rate");
    await expect(page.getByTestId("game-log-metric-explosive-rate")).toHaveCount(0);
    await expect(page.getByTestId("game-log-metric-success")).toHaveAttribute("aria-pressed", "true");
    await page.goto("/stats?chart=game-log&team=alabama");
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
    await page.goto("/stats?chart=game-log&team=alabama");
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
    await page.goto("/stats?chart=game-log&team=alabama");
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
    await page.goto("/stats?chart=adjusted&week=3&team=alabama");
    await page.waitForLoadState("networkidle");
    const picker = page.getByTestId("team-highlight");
    await picker.selectOption("Michigan");
    await picker.selectOption("Georgia");
    await picker.selectOption("");
    await picker.selectOption("Texas");
    await expect(page).toHaveURL(/team=texas/i);
    await expect(page.getByTestId("team-search")).toHaveValue("Texas");
    await page.getByRole("link", { name: "Game log", exact: true }).click();
    await expect(page.getByTestId("chart-subtitle")).toContainText("Texas ·");
    await expect(page).toHaveURL(/chart=game-log.*team=texas/i);
    await page.reload();
    await expect(page.getByTestId("team-search")).toHaveValue("Texas");
    await page.goBack();
    await expect(page).toHaveURL(/chart=adjusted.*team=texas/i);
    await expect(page.getByTestId("team-search")).toHaveValue("Texas");
    await page.goForward();
    await expect(page).toHaveURL(/chart=game-log.*team=texas/i);
    await expect(page.getByTestId("chart-subtitle")).toHaveCount(1);
    await expect(page.getByTestId("chart-subtitle")).toContainText("Texas ·");
  });
});
