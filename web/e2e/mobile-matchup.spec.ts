import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 568 }]) {
  test.describe(`phone matchup top at ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport, hasTouch: true });

    test("a pinned back row sits under the app bar, keeps its target after a scroll, and the hero stays compact", async ({ page }) => {
      await gotoHydrated(page, "/matchup/1");
      const appBar = page.getByTestId("app-bar");
      const back = page.getByTestId("matchup-back-bar");
      const link = back.getByRole("link", { name: /^Week \d+ games$/ });
      await expect(link).toBeVisible();
      await expect(link).toHaveAttribute("href", /^\/\?week=\d+$/);
      // The hero's own back link is desktop-only, so phones expose the back row and the footer link only.
      await expect(page.getByRole("link", { name: /Week \d+ games$/ })).toHaveCount(2);

      const appBox = (await appBar.boundingBox())!;
      const backBox = (await back.boundingBox())!;
      expect(Math.abs(backBox.y - (appBox.y + appBox.height))).toBeLessThanOrEqual(1);
      expect(backBox.height).toBeLessThanOrEqual(56);

      // Hero: the forecast grid (market, model and bet lines) starts high on the page.
      const grid = (await page.getByTestId("forecast-grid").boundingBox())!;
      expect(grid.y).toBeLessThan(viewport.height === 844 ? 340 : 360);
      const bet = (await page.getByTestId("model-bet-spread").boundingBox())!;
      expect(bet.y + bet.height).toBeLessThan(viewport.height === 844 ? 560 : 620);

      await page.mouse.wheel(0, 800);
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(300);
      await expect
        .poll(async () => Math.abs((await back.boundingBox())!.y - (await appBar.boundingBox())!.height))
        .toBeLessThanOrEqual(1);
      await expect(link).toBeInViewport();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
  });
}

test("desktop keeps the in-hero back link and has no phone back row", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await gotoHydrated(page, "/matchup/1");
  await expect(page.getByTestId("matchup-back-bar")).toBeHidden();
  await expect(page.getByRole("link", { name: /^← Week \d+ games$/ })).toBeVisible();
});
