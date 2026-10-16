import fs from "node:fs";
import { expect, test, type Page } from "@playwright/test";

// Fixture: 17-team roster (Wyoming has no games), net-success weeks 0-3, efficiency and
// adjusted "Through Week" 2-3. See src/test/fixtures/charts.ts.
const PLOTTED = 16;
const SEC_TEAMS = 4;

function pngSize(path: string): { width: number; height: number } {
  const bytes = fs.readFileSync(path);
  expect(bytes.subarray(1, 4).toString("ascii")).toBe("PNG");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

async function exportPng(page: Page): Promise<{ file: string; report: { logos: number; decoded: number } }> {
  const download = page.waitForEvent("download");
  await page.getByTestId("chart-download").click();
  const file = await (await download).path();
  const raw = await page.getByTestId("chart-export").getAttribute("data-last-export");
  return { file, report: JSON.parse(raw ?? "{}") };
}

test.describe("team charts", () => {
  test("net success bars render one bar per game with logos and score labels", async ({ page }) => {
    await page.goto("/charts");
    await expect(page.getByRole("heading", { name: "Team charts" })).toBeVisible();
    await expect(page.getByText("Did We Really Get Beat That Bad?").first()).toBeVisible();
    const chart = page.getByTestId("net-success-chart");
    await expect(chart).toBeVisible();
    // Latest week (3) has 8 games: 8 bars, each with a winner and a loser mark.
    await expect(chart.locator("g[data-game]")).toHaveCount(8);
    await expect(chart.locator("g[data-game]").first().locator("g[data-mark='logo']")).toHaveCount(2);
    await expect(page.locator("main").getByText(/\b[A-Z]{2,6} \d+-\d+\b/).first()).toBeVisible();
  });

  test("scatter shows 'Through Week N' and a week switch changes the window", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    await expect(page.getByText("Offense | 2026 | FBS vs FBS | Through Week 3").first()).toBeVisible();
    await expect(page.locator("#week-select")).toHaveValue("3");
    await expect(page.getByRole("option", { name: "Through Week 2" })).toHaveCount(1);
    await page.locator("#week-select").selectOption("2");
    await expect(page).toHaveURL(/week=2/);
    await expect(page.getByTestId("chart-subtitle")).toContainText("Through Week 2");
    await expect(page.getByText("Success Rate").first()).toBeVisible();
    await expect(page.getByText("EPA/play").first()).toBeVisible();
    await expect(page.getByTestId("average-lines")).toBeVisible();
  });

  test("switching tabs from a net-success Week 0 or 1 URL coerces the week", async ({ page }) => {
    for (const requested of [0, 1]) {
      await page.goto(`/charts?chart=net-success&week=${requested}`);
      await expect(page.getByText(`Week ${requested} | 2026 | FBS vs FBS`).first()).toBeVisible();
      await page.getByRole("link", { name: "Efficiency", exact: true }).click();
      await expect(page).toHaveURL(/chart=efficiency/);
      await expect(page).toHaveURL(/week=2/);
      await expect(page.locator("#week-select")).toHaveValue("2");
      await page.getByRole("link", { name: "Adjusted EPA/play" }).click();
      await expect(page).toHaveURL(/chart=adjusted/);
      await expect(page).toHaveURL(/week=2/);
      await expect(page.getByTestId("corner-labels")).toBeVisible();
    }
  });

  test("adjusted chart has dashed averages, diagonals and corner labels but no free-hand notes", async ({ page }) => {
    await page.goto("/charts?chart=adjusted&week=3");
    await expect(page.getByText("Good Offense, Good Defense")).toBeVisible();
    await expect(page.getByText("Bad Offense, Bad Defense")).toBeVisible();
    await expect(page.getByTestId("average-lines")).toBeVisible();
    expect(await page.locator("[data-iso-net]").count()).toBeGreaterThan(0);
  });

  test("the conference filter dims other teams and search enlarges one", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    const marks = page.locator("g[data-team]");
    await expect(marks).toHaveCount(PLOTTED);
    await page.getByTestId("conference-filter").selectOption("SEC");
    await expect(page.locator("g[data-team][data-state='active']")).toHaveCount(SEC_TEAMS);
    await expect(page.locator("g[data-team][data-state='dim']")).toHaveCount(PLOTTED - SEC_TEAMS);
    await expect(page.locator("g[data-team][data-state='dim']").first()).toHaveAttribute("opacity", "0.15");
    await page.getByTestId("conference-filter").selectOption("p4");
    await expect(page.locator("g[data-team][data-state='dim']")).toHaveCount(3); // Tulane, Boise State, App State
    await page.getByTestId("team-search").fill("michigan");
    await expect(page.locator("g[data-team='Michigan']")).toHaveAttribute("data-state", "searched");
  });

  test("markers are keyboard reachable; arrows move focus and a tooltip appears", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    const first = page.locator("g[data-team]:not([data-state='dim'])").first();
    const tooltip = page.getByTestId("chart-tooltip");
    // Focus handlers attach on hydration; retry until the tooltip responds.
    await expect(async () => {
      await first.blur();
      await first.focus();
      await expect(tooltip).toBeVisible({ timeout: 500 });
    }).toPass();
    const firstTeam = await first.getAttribute("data-team");
    await expect(tooltip).toContainText(firstTeam ?? "");
    await page.keyboard.press("ArrowRight");
    const focused = await page.evaluate(() => document.activeElement?.getAttribute("data-team"));
    expect(focused).toBeTruthy();
    expect(focused).not.toBe(firstTeam);
    await expect(tooltip).toContainText(focused ?? "");
    await expect(first).toHaveAttribute("role", "img");
    await expect(first).toHaveAttribute("aria-label", /success rate .*EPA\/play .* plays/);
    await page.keyboard.press("Escape");
    await expect(tooltip).toHaveCount(0);
  });

  test("the table view lists the same rows and sorts", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    await page.getByTestId("table-toggle").click();
    const table = page.getByTestId("chart-table");
    await expect(table.locator("tbody tr")).toHaveCount(PLOTTED);
    await table.getByRole("button", { name: /EPA\/play/ }).click();
    const first = await table.locator("tbody tr").first().locator("td").nth(3).innerText();
    const last = await table.locator("tbody tr").last().locator("td").nth(3).innerText();
    expect(parseFloat(first)).toBeLessThanOrEqual(parseFloat(last));
    await page.getByTestId("table-toggle").click();
    await expect(page.getByTestId("scatter-chart")).toBeVisible();
  });

  test("teams without data are listed instead of plotted", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    await expect(page.getByTestId("unavailable-teams")).toContainText("Wyoming");
    await expect(page.locator("g[data-team='Wyoming']")).toHaveCount(0);
    await page.goto("/charts?chart=adjusted&week=3");
    // Window as_of_week 4 has no Notre Dame defense row: one role is not a point.
    await expect(page.getByTestId("unavailable-teams")).toContainText("Notre Dame");
    await expect(page.locator("g[data-team='Notre Dame']")).toHaveCount(0);
  });

  test("a release without chart tables shows the arrival notice, errors show unavailable", async ({ page }) => {
    await page.goto("/charts?fixture=unsupported");
    await expect(page.getByTestId("charts-notice")).toHaveText("Charts arrive with the next weekly release.");
    await expect(page.getByTestId("net-success-chart")).toHaveCount(0);
    await page.goto("/charts?fixture=error");
    await expect(page.getByTestId("charts-notice")).toHaveText("Charts are temporarily unavailable.");
    // A failing adjusted window shows the same card instead of the route error page.
    await page.goto("/charts?chart=adjusted&week=3&fixture=adjusted-error");
    await expect(page.getByTestId("charts-notice")).toHaveText("Charts are temporarily unavailable.");
  });

  test("charts on every tab load logos without a broken image", async ({ page }) => {
    const failed: string[] = [];
    page.on("response", (response) => {
      if (response.url().includes("/logos/") && !response.ok()) failed.push(`${response.status()} ${response.url()}`);
    });
    for (const url of ["/charts?chart=net-success&week=2", "/charts?chart=efficiency&week=3", "/charts?chart=adjusted&week=3"]) {
      await page.goto(url);
      await page.waitForLoadState("networkidle");
      const broken = await page.evaluate(() => [...document.images].filter((i) => i.complete && i.naturalWidth === 0).length);
      expect(broken, url).toBe(0);
      const svgLogos = await page.locator("svg image").count();
      expect(svgLogos, url).toBeGreaterThan(0);
    }
    expect(failed).toEqual([]);
  });

  test("mobile layout: bars become horizontal rows and nothing scrolls the page sideways", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto("/charts?chart=net-success&week=3");
    await expect(page.getByTestId("net-success-chart")).toHaveAttribute("data-orientation", "horizontal");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Charts" })).toBeVisible();
  });

  test("nav shows Charts and the nav width matches the chart page", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/charts");
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await expect(nav.getByRole("link", { name: "Charts" })).toHaveAttribute("aria-current", "page");
    // Styles may still be compiling on the first request; poll until the layout settles.
    await expect
      .poll(async () => {
        const navBox = await nav.locator("> div").boundingBox();
        const mainBox = await page.locator("main", { has: page.getByRole("heading", { name: "Team charts" }) }).boundingBox();
        return Math.abs((navBox?.width ?? 0) - (mainBox?.width ?? 0));
      })
      .toBeLessThanOrEqual(2);
  });

  test("PNG export of a scatter is 2000x1125 with every logo decoded", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    await page.waitForLoadState("networkidle");
    const { file, report } = await exportPng(page);
    expect(pngSize(file)).toEqual({ width: 2000, height: 1125 });
    expect(report.logos).toBeGreaterThan(0);
    expect(report.decoded).toBe(report.logos);
  });

  test("PNG export of a full Week 0 slate is as wide as 140 + 30 per game and keeps its logos", async ({ page }) => {
    await page.goto("/charts?chart=net-success&week=0&fixture=slate");
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("net-success-chart").locator("g[data-game]")).toHaveCount(69);
    const { file, report } = await exportPng(page);
    expect(pngSize(file)).toEqual({ width: 140 + 30 * 69, height: 1125 });
    expect(report.decoded).toBe(report.logos);
    expect(report.logos).toBeGreaterThanOrEqual(140);
    // Logos are in the captured pixels: the image has far more colors than flat bars alone.
    const colors = await page.evaluate(async (base64) => {
      const blob = await (await fetch(`data:image/png;base64,${base64}`)).blob();
      const bitmap = await createImageBitmap(blob);
      const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
      const context = canvas.getContext("2d")!;
      context.drawImage(bitmap, 0, 0);
      const data = context.getImageData(0, 0, bitmap.width, bitmap.height).data;
      const seen = new Set<number>();
      for (let i = 0; i < data.length; i += 4 * 7) seen.add(((data[i] >> 3) << 10) | ((data[i + 1] >> 3) << 5) | (data[i + 2] >> 3));
      return seen.size;
    }, fs.readFileSync(file).toString("base64"));
    expect(colors).toBeGreaterThan(300);
  });
});
