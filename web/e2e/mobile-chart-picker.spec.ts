import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

const TITLES = ["Net success rate", "Efficiency vs explosiveness", "Adjusted PPA/play", "Possession efficiency", "Game log"];

test.describe("phone chart picker", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

  test("a native dropdown lists every chart, navigates by URL and the chips are gone", async ({ page }) => {
    await gotoHydrated(page, "/stats?chart=efficiency&week=3&team=Alabama");
    const select = page.getByTestId("chart-select");
    await expect(select).toBeVisible();
    await expect(select.locator("option")).toHaveText(TITLES);
    expect(await select.evaluate((node) => parseFloat(getComputedStyle(node).fontSize))).toBeGreaterThanOrEqual(16);
    expect((await select.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await expect(page.getByTestId("chart-picker").getByRole("link")).toHaveCount(0);
    await select.selectOption({ label: "Possession efficiency" });
    await expect(page).toHaveURL(/chart=possession/);
    await expect(page).toHaveURL(/team=Alabama/);
    await expect(page.getByRole("heading", { level: 2, name: "Possession efficiency" })).toBeVisible();
    await expect(select.locator("option:checked")).toHaveText("Possession efficiency");
    await page.goBack();
    await expect(page).toHaveURL(/chart=efficiency/);
  });

  test("the picker bar stays pinned at the top while the chart scrolls and the settings sheet sits above it", async ({ page }) => {
    await gotoHydrated(page, "/stats?chart=efficiency&week=3");
    const bar = page.getByTestId("chart-picker");
    expect((await bar.boundingBox())!.y).toBeGreaterThan(20);
    await page.mouse.wheel(0, 800);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(300);
    // Pinned just below the app bar.
    const appBar = page.getByTestId("app-bar");
    await expect.poll(async () => Math.abs((await bar.boundingBox())!.y - (await appBar.boundingBox())!.height)).toBeLessThanOrEqual(1);
    await expect(page.getByTestId("chart-select")).toBeInViewport();
    expect(await bar.evaluate((node) => getComputedStyle(node).backgroundColor)).not.toBe("rgba(0, 0, 0, 0)");
    await page.getByRole("button", { name: "Chart settings", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Chart settings", exact: true });
    await expect(dialog).toBeVisible();
    // The native dialog is in the top layer, above the sticky bar.
    expect(await page.evaluate(() => {
      const rect = document.querySelector("dialog[open]")!.getBoundingClientRect();
      return document.elementFromPoint(rect.x + rect.width / 2, rect.y + 10)?.closest("dialog") !== null;
    })).toBe(true);
  });

  const CHARTS = [
    ["net-success", "/stats?chart=net-success&week=3", false],
    ["efficiency", "/stats?chart=efficiency&week=3", true],
    ["adjusted", "/stats?chart=adjusted&week=2", true],
    ["possession", "/stats?chart=possession&week=3", true],
    ["game-log", "/stats?chart=game-log", true],
  ] as const;

  for (const [chart, url, hasFinder] of CHARTS) {
    test(`${chart}: compact phone header with the pinned bar, one summary row and the chart card up top`, async ({ page }) => {
      await gotoHydrated(page, url);
      const bar = page.getByTestId("chart-picker");
      const settings = bar.getByRole("button", { name: "Chart settings", exact: true });
      await expect(bar.getByTestId("chart-select")).toBeVisible();
      await expect(settings).toBeVisible();
      expect((await settings.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      // The old heading is screen-reader only on phones.
      await expect(page.getByRole("heading", { level: 1, name: "Team charts" })).toBeAttached();
      expect((await page.getByRole("heading", { level: 1, name: "Team charts" }).boundingBox())!.width).toBeLessThanOrEqual(1);

      const summary = page.getByTestId("chart-settings-summary");
      await expect(summary).toHaveText(/Week \d+ · /);
      expect(await summary.innerText()).not.toMatch(/2026|FBS vs FBS|\|/);
      const summaryBox = (await summary.boundingBox())!;
      const exports = (await page.getByRole("group", { name: "Chart display and export" }).boundingBox())!;
      // Same row: the summary text and the export group overlap vertically.
      expect(exports.y).toBeLessThan(summaryBox.y + summaryBox.height);
      expect(exports.y + exports.height).toBeGreaterThan(summaryBox.y);
      expect(exports.x).toBeGreaterThan(summaryBox.x + 100);

      const finder = page.getByTestId("team-search");
      if (hasFinder) {
        await expect(finder).toBeVisible();
        expect((await finder.boundingBox())!.y).toBeGreaterThan(summaryBox.y);
      } else {
        await expect(finder).toHaveCount(0);
      }

      const card = page.locator('[data-card]', { has: page.getByTestId("chart-figure") }).first();
      const top = (await card.boundingBox())!.y;
      console.log(`chart card top ${chart}: ${Math.round(top)}px`);
      expect(top).toBeLessThan(335);

      await page.mouse.wheel(0, 800);
      const appBar = page.getByTestId("app-bar");
      await expect.poll(async () => Math.abs((await bar.boundingBox())!.y - (await appBar.boundingBox())!.height)).toBeLessThanOrEqual(1);
      await expect(settings).toBeInViewport();
      await settings.click();
      const dialog = page.getByRole("dialog", { name: "Chart settings", exact: true });
      await expect(dialog).toBeVisible();
      expect(await page.evaluate(() => {
        const rect = document.querySelector("dialog[open]")!.getBoundingClientRect();
        return document.elementFromPoint(rect.x + rect.width / 2, rect.y + 10)?.closest("dialog") !== null;
      })).toBe(true);
      await page.keyboard.press("Escape");
      await expect(dialog).not.toBeVisible();
      await expect(settings).toBeFocused();
    });
  }

  test("at 320px the settings button is icon-only and nothing overflows", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 568 });
    await gotoHydrated(page, "/stats?chart=efficiency&week=3");
    const settings = page.getByTestId("chart-picker").getByRole("button", { name: "Chart settings", exact: true });
    await expect(settings).toBeVisible();
    await expect(settings.locator("span")).toBeHidden();
    expect((await settings.boundingBox())!.width).toBeLessThan(60);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    // Icon-only up to 439px; the "Settings" label returns from 440px, still below the 640px phone layout.
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(settings.locator("span")).toBeHidden();
    await page.setViewportSize({ width: 440, height: 844 });
    await expect(settings.locator("span")).toBeVisible();
    await page.setViewportSize({ width: 600, height: 844 });
    await expect(settings.locator("span")).toBeVisible();
  });

  for (const width of [360, 390]) {
    test(`the longest chart name fits the dropdown unclipped at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await gotoHydrated(page, "/stats?chart=efficiency&week=3");
      const select = page.getByTestId("chart-select");
      await expect(select.locator("option:checked")).toHaveText("Efficiency vs explosiveness");
      const settings = page.getByTestId("chart-picker").getByRole("button", { name: "Chart settings", exact: true });
      const box = (await settings.boundingBox())!;
      expect(box.width).toBeLessThanOrEqual(48);
      expect(box.height).toBeGreaterThanOrEqual(44);
      const fit = await select.evaluate((node: HTMLSelectElement) => {
        const style = getComputedStyle(node);
        const probe = document.createElement("span");
        probe.textContent = "Efficiency vs explosiveness";
        Object.assign(probe.style, { font: style.font, position: "absolute", visibility: "hidden", whiteSpace: "nowrap" });
        document.body.append(probe);
        const text = probe.getBoundingClientRect().width;
        probe.remove();
        const room = node.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) - 24; // chevron
        return { scroll: node.scrollWidth <= node.clientWidth, text, room };
      });
      expect(fit.scroll).toBe(true);
      expect(fit.text).toBeLessThanOrEqual(fit.room);
    });
  }

  test("at 640px and wider the original chart nav is unchanged", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 800 });
    await page.goto("/stats?chart=efficiency&week=3");
    await expect(page.getByTestId("chart-select")).toBeHidden();
    await expect(page.getByTestId("chart-picker").getByRole("link")).toHaveText(TITLES);
    expect(await page.getByTestId("chart-picker").evaluate((node) => getComputedStyle(node).position)).toBe("static");
  });
});
