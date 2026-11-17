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
    await expect(chart.locator("[data-break-value]").filter({ hasText: trueValue })).toHaveCount(1);
  });

  test("break value labels stay inside the chart and render at 12px or more", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await gotoHydrated(page, "/stats?chart=net-success&week=3");
    const chart = page.getByTestId("net-success-chart");
    const svg = (await chart.locator("svg").first().boundingBox())!;
    const labels = chart.locator("[data-break-value]");
    for (let i = 0; i < (await labels.count()); i++) {
      const box = (await labels.nth(i).boundingBox())!;
      expect(box.x + box.width).toBeLessThanOrEqual(svg.x + svg.width + 1);
      const size = await labels.nth(i).evaluate((el) => parseFloat(getComputedStyle(el).fontSize) * (el as SVGTextElement).getScreenCTM()!.a);
      expect(size).toBeGreaterThanOrEqual(11.9);
    }
  });

  test("break value backing exists and no other bar's logo shows through it", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await gotoHydrated(page, "/stats?chart=net-success&week=3");
    const chart = page.getByTestId("net-success-chart");
    await expect(chart).toHaveAttribute("data-orientation", "vertical");
    const backings = chart.getByTestId("break-value-bg");
    await expect(backings.first()).toBeAttached();
    const logos = chart.locator("g[data-game] g[data-mark='logo'] image:visible");
    const logoCount = await logos.count();
    expect(logoCount).toBeGreaterThan(0);
    const placed = [];
    for (let j = 0; j < logoCount; j++) {
      const logo = logos.nth(j);
      placed.push({
        owner: await logo.evaluate((el) => el.closest("g[data-game]")?.getAttribute("data-game")),
        box: (await logo.boundingBox())!,
      });
    }
    for (let i = 0; i < (await backings.count()); i++) {
      const backing = backings.nth(i);
      const owner = await backing.getAttribute("data-game");
      const box = (await backing.boundingBox())!;
      for (const logo of placed.filter((p) => p.owner !== owner)) {
        const overlaps =
          box.x < logo.box.x + logo.box.width &&
          logo.box.x < box.x + box.width &&
          box.y < logo.box.y + logo.box.height &&
          logo.box.y < box.y + box.height;
        expect(overlaps, `break value of game ${owner} overlaps logo of game ${logo.owner}`).toBe(false);
      }
    }
  });
});
