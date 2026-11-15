import { expect, test } from "@playwright/test";
import { featuredComparisons, gotoHydrated, openRecord } from "./helpers";

for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 568 }]) {
  test.describe(`phone Games page at ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport, hasTouch: true });

    for (const [name, url] of [["upcoming week", "/"], ["graded week", "/?week=4"]] as const) {
      test(`${name}: the first game card sits near the top and nothing overflows`, async ({ page }) => {
        await gotoHydrated(page, url);
        const card = page.locator("li[id^='game-']").first();
        await expect(card).toBeVisible();
        // Measured stack, graded week at 320px (the tallest, 537px): app bar 48 + title and phase lines +
        // timestamp line + slate bar 105 + status and analysis row 48 + day header. Featured comparisons
        // and the model record sit below the games, so they add nothing above the first card. The upcoming
        // week lands at 482-498px.
        expect((await card.boundingBox())!.y).toBeLessThan(560);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await expect(page.getByTestId("week-phase")).toBeVisible();
        await expect(page.getByRole("group", { name: "Game status" })).toBeVisible();
        await expect(featuredComparisons(page).locator("summary").first()).toBeVisible();
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
      expect(barBox.height).toBeLessThanOrEqual(110);
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

    test("the status row sits under the slate bar above the games, and featured comparisons stay collapsed below them", async ({ page }) => {
      await gotoHydrated(page, "/");
      const groups = page.locator("section[aria-label]").filter({ has: page.locator("li[id^='game-']") });
      const firstGroup = (await groups.first().boundingBox())!;
      const lastGroup = (await groups.last().boundingBox())!;
      const bar = (await page.getByTestId("slate-bar").boundingBox())!;
      const status = (await page.getByRole("group", { name: "Game status" }).boundingBox())!;
      expect(status.y).toBeGreaterThanOrEqual(bar.y + bar.height);
      expect(status.y + status.height).toBeLessThanOrEqual(firstGroup.y);
      const featured = featuredComparisons(page);
      await expect(featured).not.toHaveAttribute("open", "");
      const summary = (await featured.locator("summary").first().boundingBox())!;
      expect(summary.y).toBeGreaterThanOrEqual(lastGroup.y + lastGroup.height);
      expect(summary.height).toBeGreaterThanOrEqual(44);
      expect((await featured.boundingBox())!.height).toBeLessThan(76);
    });

    test("the record card header carries the week status without the run state or publish stamp", async ({ page }) => {
      await gotoHydrated(page, "/");
      await expect(page.getByText(/Run published/)).toBeHidden();
      // The phone status line sits under the title; the model record no longer carries it.
      const status = page.getByTestId("week-phase").locator("..");
      await expect(status).toContainText(/Week \d+ · Upcoming · \d+ games/);
      await expect(status).not.toContainText("Frozen before kickoff");
      await expect(page.getByText("Frozen before kickoff")).toBeHidden();
    });

    test("the week stepper is centered in the slate bar", async ({ page }) => {
      await gotoHydrated(page, "/");
      const nav = page.getByTestId("slate-bar").getByRole("navigation", { name: "Week navigation" });
      const box = (await nav.boundingBox())!;
      expect(Math.abs(box.x + box.width / 2 - viewport.width / 2)).toBeLessThanOrEqual(2);
      const search = page.getByTestId("slate-bar").getByRole("searchbox", { name: "Filter by team" });
      expect((await search.boundingBox())!.y).toBeGreaterThan(box.y + box.height - 1);
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

test("desktop keeps the heading, phase pill, week navigator and an open record card inside its disclosure", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await gotoHydrated(page, "/?week=4");
  await expect(page.getByRole("heading", { name: "Week 4 games", level: 1 })).toBeVisible();
  await expect(page.getByTestId("week-phase")).toBeVisible();
  await expect(page.locator("#week-select")).toBeVisible();
  await expect(page.getByTestId("slate-filters-button")).toBeHidden();
  await expect(page.getByRole("heading", { name: "Season record before Week 4" })).toBeHidden();
  await openRecord(page);
  await expect(page.getByRole("heading", { name: "Season record before Week 4" })).toBeVisible();
  await expect(page.getByTestId("record-summary")).toBeHidden();
});
