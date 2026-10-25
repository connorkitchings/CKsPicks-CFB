import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 568 }]) {
  test.describe(`phone matchup top at ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport, hasTouch: true });

    test("the app bar holds the back link and matchup title (no second bar), and the hero stays compact", async ({ page }) => {
      await gotoHydrated(page, "/matchup/1");
      const appBar = page.getByTestId("app-bar");
      const link = appBar.getByRole("link", { name: /^Week \d+ games$/ });
      await expect(link).toBeVisible();
      await expect(link).toHaveAttribute("href", /^\/\?week=\d+$/);
      await expect(appBar.getByTestId("app-bar-title")).toHaveText(/ at /);
      await expect(appBar.getByTestId("app-menu-button")).toBeVisible();
      // No separate pinned back row; the hero's own link is desktop-only, so phones expose the app bar link and the footer link.
      await expect(page.getByTestId("matchup-back-bar")).toHaveCount(0);
      await expect(page.locator("[data-mobile-sticky-bar]")).toHaveCount(0);
      await expect(page.getByRole("link", { name: /Week \d+ games$/ })).toHaveCount(2);
      const linkBox = (await link.boundingBox())!;
      expect(linkBox.width).toBeGreaterThanOrEqual(44);
      expect(linkBox.height).toBeGreaterThanOrEqual(44);
      const appBox = (await appBar.boundingBox())!;
      expect(appBox.height).toBeLessThanOrEqual(60);

      // Date/place and the share buttons share one compact row.
      const facts = (await page.getByTestId("game-facts").boundingBox())!;
      expect(facts.height).toBeLessThanOrEqual(50);
      const share = (await page.getByTestId("share-controls").boundingBox())!;
      expect(Math.abs(share.y + share.height / 2 - (facts.y + facts.height / 2))).toBeLessThanOrEqual(4);

      // Hero: the forecast grid (market, model and bet lines) starts high on the page, each spread cell on one line.
      const grid = (await page.getByTestId("forecast-grid").boundingBox())!;
      console.log(`forecast grid top ${viewport.width}x${viewport.height}: ${grid.y}; facts row ${facts.height}`);
      expect(grid.y).toBeLessThan(280);
      const bet = (await page.getByTestId("model-bet-spread").boundingBox())!;
      expect(bet.y + bet.height).toBeLessThan(viewport.height === 844 ? 480 : 520);
      for (const id of ["model-bet-spread", "model-bet-total"]) {
        expect((await page.getByTestId(id).boundingBox())!.height).toBeLessThanOrEqual(24);
      }
      const cellHeights = await page
        .getByTestId("forecast-grid")
        .locator("> div:not([aria-hidden])")
        .evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().height)));
      console.log(`forecast cell heights ${viewport.width}: ${cellHeights.join(",")}`);
      // At 390 the source label sits beside the spread (one line); at 320 only the market cell may wrap it beneath.
      expect(Math.max(...cellHeights)).toBeLessThanOrEqual(viewport.width === 390 ? 24 : 32);
      expect(cellHeights.filter((height) => height > 24).length).toBeLessThanOrEqual(1);

      await page.mouse.wheel(0, 800);
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(300);
      await expect.poll(async () => Math.abs((await appBar.boundingBox())!.y)).toBeLessThanOrEqual(1);
      await expect(link).toBeInViewport();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test("the unit table header lines up with its columns and the card header is one line", async ({ page }) => {
      await gotoHydrated(page, "/matchup/1");
      const table = page.getByRole("table").first();
      const heads = await table.locator("thead th").all();
      const offenseHead = (await heads[0].locator("span").first().boundingBox())!;
      const metricHead = (await heads[1].boundingBox())!;
      const defenseHead = (await heads[2].locator("span").first().boundingBox())!;
      const firstRow = table.locator("tbody tr:has(td)").first();
      const offenseValue = (await firstRow.locator('[data-value="offense"]').boundingBox())!;
      const defenseValue = (await firstRow.locator('[data-value="defense"]').boundingBox())!;
      const metricCell = (await firstRow.locator("td").nth(1).boundingBox())!;
      expect(Math.abs(offenseHead.x - offenseValue.x)).toBeLessThanOrEqual(2);
      expect(Math.abs(defenseHead.x + defenseHead.width - (defenseValue.x + defenseValue.width))).toBeLessThanOrEqual(2);
      expect(Math.abs(metricHead.x + metricHead.width / 2 - (metricCell.x + metricCell.width / 2))).toBeLessThanOrEqual(2);

      const card = table.locator("xpath=ancestor::div[1]");
      const rank = card.getByTestId("unit-offense-rank");
      await expect(rank).toHaveText(/^Model Offense Rank\s*#\d+$/);
      const headerTop = (await card.locator("h3").first().boundingBox())!;
      const tableTop = (await table.boundingBox())!;
      console.log(`unit header to table: ${Math.round(tableTop.y - headerTop.y)} at ${viewport.width}`);
      expect(tableTop.y - headerTop.y).toBeLessThanOrEqual(viewport.width === 390 ? 60 : 84);
      // The rank chip sits on the team's own line.
      const chip = (await rank.boundingBox())!;
      expect(Math.abs(chip.y + chip.height / 2 - (headerTop.y + headerTop.height / 2))).toBeLessThanOrEqual(viewport.width === 390 ? 8 : 20);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
  });
}

test("desktop keeps the in-hero back link and has no back link in the app bar", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await gotoHydrated(page, "/matchup/1");
  await expect(page.getByTestId("matchup-back-bar")).toHaveCount(0);
  await expect(page.getByTestId("app-bar")).toBeHidden();
  await expect(page.getByRole("link", { name: /^← Week \d+ games$/ })).toBeVisible();
});
