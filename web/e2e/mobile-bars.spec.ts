import fs from "node:fs";
import { expect, test } from "@playwright/test";

for (const width of [320, 390, 430]) {
  test(`mobile bar charts reflow with readable rows at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/stats?chart=net-success&week=3");
    const net = page.getByTestId("net-success-chart");
    await expect(net).toHaveAttribute("data-orientation", "horizontal");
    await expect(net.locator("g[data-game]")).toHaveCount(8);
    const targets = await net.locator("[data-row-target]").evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().height));
    expect(Math.min(...targets)).toBeGreaterThanOrEqual(44);
    const sizes = await net.locator("svg text").evaluateAll((nodes) => nodes.map((node) => parseFloat(getComputedStyle(node).fontSize) * (node as SVGGraphicsElement).getScreenCTM()!.a));
    expect(Math.min(...sizes)).toBeGreaterThanOrEqual(11.99);
    const first = net.locator("g[data-game]").first();
    await first.dispatchEvent("pointerdown", { pointerType: "touch", clientX: 20, clientY: 100 });
    await first.dispatchEvent("click");
    await expect(page.getByTestId("chart-selected-details")).toBeVisible();
    await page.getByRole("button", { name: "Clear selection" }).click();
    await expect(page.getByTestId("chart-selected-details")).toHaveCount(0);

    await page.goto("/stats?chart=game-log&team=Alabama");
    const log = page.getByTestId("game-log-chart");
    await expect(log).toHaveAttribute("data-orientation", "horizontal");
    await expect(log.getByRole("heading", { name: "Offense · higher is better" })).toBeVisible();
    await expect(log.getByRole("heading", { name: "Defense allowed · lower is better" })).toBeVisible();
    const scales = await log.getByTestId("game-log-mobile-scale").allTextContents();
    expect(scales[0]).toEqual(scales[1]);
    const rows = log.locator("button[data-game]");
    const heights = await rows.evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().height));
    expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
    await expect(rows.first()).toContainText(/Wk \d+ · (Home vs|Away at|Neutral vs)/);
    await expect(rows.first()).toContainText("Weekly FBS avg");
    await rows.first().click();
    await expect(page.getByTestId("chart-selected-details")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test("mobile game log cancels selection after scrolling and keyboard retains access", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await page.goto("/stats?chart=game-log&team=Alabama");
  const chart = page.getByTestId("game-log-chart");
  await expect(chart).toHaveAttribute("data-orientation", "horizontal");
  const row = chart.locator("button[data-game]").first();
  await row.dispatchEvent("pointerdown", { pointerType: "touch", clientX: 100, clientY: 100 });
  await row.dispatchEvent("pointermove", { pointerType: "touch", clientX: 100, clientY: 140 });
  await row.dispatchEvent("pointercancel", { pointerType: "touch" });
  await row.dispatchEvent("click", { detail: 1 });
  await expect(page.getByTestId("chart-selected-details")).toHaveCount(0);
  await row.focus();
  await row.press("Enter");
  await expect(page.getByTestId("chart-selected-details")).toBeVisible();
  await row.press("Escape");
  await expect(page.getByTestId("chart-selected-details")).toHaveCount(0);
});

test("mobile game-log download retains desktop SVG and original PNG dimensions", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await page.goto("/stats?chart=game-log&team=Alabama");
  await expect(page.getByTestId("game-log-chart")).toHaveAttribute("data-orientation", "horizontal");
  await page.evaluate(() => {
    const state = { verticalSvg: false, mobileRows: false };
    Object.assign(window, { mobileExportProbe: state });
    new MutationObserver(() => {
      const card = document.querySelector('[data-testid="export-card"]');
      if (!card) return;
      state.verticalSvg ||= !!card.querySelector('[data-testid="game-log-chart"] svg');
      state.mobileRows ||= !!card.querySelector('button[data-game]');
    }).observe(document.body, { childList: true, subtree: true });
  });
  const download = page.waitForEvent("download");
  await page.getByTestId("chart-download").click();
  const file = await (await download).path();
  const bytes = fs.readFileSync(file!);
  expect(bytes.readUInt32BE(16)).toBe(2000);
  expect(bytes.readUInt32BE(20)).toBe(1125);
  expect(await page.evaluate(() => (window as unknown as { mobileExportProbe: unknown }).mobileExportProbe)).toEqual({ verticalSvg: true, mobileRows: false });
});

test("mobile full slate keeps every game and full-size row targets", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await page.goto("/stats?chart=net-success&week=0&fixture=slate");
  const chart = page.getByTestId("net-success-chart");
  await expect(chart).toHaveAttribute("data-orientation", "horizontal");
  await expect(chart.locator("g[data-game]")).toHaveCount(69);
  const heights = await chart.locator("[data-row-target]").evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().height));
  expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
