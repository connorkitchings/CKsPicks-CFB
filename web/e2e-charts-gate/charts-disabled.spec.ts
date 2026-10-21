import { expect, test } from "@playwright/test";

const pages = ["/", "/ratings", "/model"];
const names = ["Games", "Ratings", "Model"];

for (const query of ["", "?chart=trajectory&team=Alabama", "?chart=rating-trajectory&metric=defense", "?chart=possession&week=2&metric=epa_per_possession", "?chart=game-log&metric=explosive_rate", "?fixture=error", "?fixture=unsupported", "?fixture=schedule&chart=schedule", "?fixture=slate&chart=efficiency"]) {
  for (const base of ["/stats", "/charts"]) test(`disabled ${base}${query} responds with HTTP 404 before loading chart data`, async ({ page }) => {
    const response = await page.goto(`${base}${query}`);
    expect(response?.status()).toBe(404);
    await expect(page.getByRole("heading", { name: "Team charts", exact: true })).toHaveCount(0);
    await expect(page.getByTestId("charts-notice")).toHaveCount(0);
    await expect(page.getByTestId("chart-picker")).toHaveCount(0);
    await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Stats", exact: true })).toHaveCount(0);
    await expect(page.getByText(/Charts are temporarily unavailable|Charts arrive with the next weekly release/)).toHaveCount(0);
  });
}

for (const width of [1280, 390]) {
  test(`three navigation links and the core pages work at ${width}px without Stats`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    for (const path of pages) {
      const response = await page.goto(path);
      expect(response?.status()).toBe(200);
      const nav = page.getByRole("navigation", { name: "Main navigation" });
      const links = nav.getByRole("link");
      await expect(links).toHaveText(names);
      await expect(nav.getByRole("link", { name: "Stats", exact: true })).toHaveCount(0);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect.poll(async () => {
        const boxes = await links.evaluateAll((nodes) => nodes.map((node) => {
          const rect = node.getBoundingClientRect();
          return { left: rect.left, right: rect.right, width: rect.width };
        }));
        if (width === 390) return Math.max(...boxes.map((box) => box.width)) - Math.min(...boxes.map((box) => box.width));
        const gaps = boxes.slice(1).map((box, i) => box.left - boxes[i].right);
        return Math.max(...gaps) - Math.min(...gaps);
      }).toBeLessThan(1);
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
  });
}

test("disabled navigation is absent in server HTML before hydration", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.getByRole("link")).toHaveText(names);
  await expect(nav.getByRole("link", { name: "Stats", exact: true })).toHaveCount(0);
  await context.close();
});
