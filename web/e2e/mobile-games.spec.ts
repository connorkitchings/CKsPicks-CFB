import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 568 }]) {
  test.describe(`phone Games page at ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport, hasTouch: true });

    for (const [name, url] of [["upcoming week", "/"], ["graded week", "/?week=4"]] as const) {
      test(`${name}: the first game card sits near the top and nothing overflows`, async ({ page }) => {
        await gotoHydrated(page, url);
        const card = page.locator("li[id^='game-']").first();
        await expect(card).toBeVisible();
        expect((await card.boundingBox())!.y).toBeLessThan(330);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await expect(page.getByTestId("week-phase")).toBeVisible();
        await expect(page.getByTestId("record-summary")).toBeVisible();
        await expect(page.locator("details[open]")).toHaveCount(0);
      });
    }

    test("the pinned bar stays directly under the app bar after an 800px scroll", async ({ page }) => {
      await gotoHydrated(page, "/");
      const appBar = page.getByTestId("app-bar");
      const bar = page.getByTestId("slate-bar");
      await page.mouse.wheel(0, 800);
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(300);
      await expect.poll(async () => {
        const [a, b] = [await appBar.boundingBox(), await bar.boundingBox()];
        return Math.abs(b!.y - (a!.y + a!.height));
      }).toBeLessThanOrEqual(1);
      const barBox = (await bar.boundingBox())!;
      expect(barBox.height).toBeLessThanOrEqual(115);
      // The sticky day header sits just below the bar, not under it. Headers of groups scrolled
      // fully past the bar don't count; the group in view has its header stuck at the bar's bottom.
      const barBottom = barBox.y + barBox.height;
      const headerTops = await page.locator("section[aria-label] > div").filter({ hasText: /· \d+ games?$/ })
        .evaluateAll((els, limit) => els.map((el) => el.getBoundingClientRect()).filter((r) => r.bottom > limit).map((r) => r.y), barBottom);
      expect(headerTops.length).toBeGreaterThan(0);
      expect(Math.min(...headerTops)).toBeGreaterThanOrEqual(barBottom - 1);
    });

    test("the Filters sheet holds conference and sort, opens above the bar, and Escape returns focus", async ({ page }) => {
      await gotoHydrated(page, "/");
      await expect(page.getByTestId("conference-filter")).toHaveCount(1);
      await expect(page.getByTestId("conference-filter")).toBeHidden();
      const button = page.getByTestId("slate-filters-button");
      await expect(button).toBeEnabled();
      await button.click();
      const dialog = page.getByRole("dialog", { name: "Filters", exact: true });
      await expect(dialog).toBeVisible();
      expect((await dialog.boundingBox())!.y).toBeLessThanOrEqual((await page.getByTestId("slate-bar").boundingBox())!.y);
      await dialog.getByTestId("conference-filter").selectOption("Sun Belt");
      await expect(page.getByTestId("slate-filters-dot")).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
      await expect(button).toBeFocused();
      await expect(page.locator("li[id^='game-']")).toHaveCount(1);
    });

    test("the week navigator lives in the bar and the quick search filters the slate", async ({ page }) => {
      await gotoHydrated(page, "/");
      const bar = page.getByTestId("slate-bar");
      await expect(bar.getByRole("navigation", { name: "Week navigation" })).toBeVisible();
      await bar.getByRole("searchbox", { name: "Filter by team" }).fill("Oregon");
      await expect(page.locator("li[id^='game-']")).toHaveCount(1);
    });

    test("biggest edges follows the first day's games, collapsed", async ({ page }) => {
      await gotoHydrated(page, "/");
      const edges = page.getByRole("region", { name: "Biggest edges" });
      await expect(edges.locator("summary")).toBeVisible();
      const firstGroup = page.locator("section[aria-label]").filter({ has: page.locator("li[id^='game-']") }).first();
      expect((await edges.boundingBox())!.y).toBeGreaterThan((await firstGroup.boundingBox())!.y);
    });

    test("the Retrospective replay state stays visible on one status line", async ({ page }) => {
      await gotoHydrated(page, "/?week=4");
      const replay = page.getByText("Retrospective replay", { exact: true });
      await expect(replay).toBeVisible();
      expect((await replay.boundingBox())!.y).toBeLessThan(160);
      await expect(page.getByRole("dialog")).toHaveCount(0);
    });
  });
}

test("desktop keeps the heading, phase pill, week navigator and open record", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await gotoHydrated(page, "/?week=4");
  await expect(page.getByRole("heading", { name: "Week 4", level: 1 })).toBeVisible();
  await expect(page.getByTestId("week-phase")).toBeVisible();
  await expect(page.locator("#week-select")).toBeVisible();
  await expect(page.getByTestId("slate-filters-button")).toBeHidden();
  await expect(page.getByRole("heading", { name: "Season record before Week 4" })).toBeVisible();
  await expect(page.getByTestId("record-summary")).toBeHidden();
});
