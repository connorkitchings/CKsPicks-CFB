import { expect, test, type Page } from "@playwright/test";
import { gotoHydrated } from "./helpers";

const PAGES = [
  ["Games", "/"],
  ["Ratings", "/ratings"],
  ["Stats", "/stats?chart=efficiency&week=3"],
  ["Model", "/model"],
] as const;

const themeColor = (page: Page) => page.locator('meta[name="theme-color"]').getAttribute("content");

for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 568 }]) {
  test.describe(`phone app bar at ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport, hasTouch: true });

    for (const [title, url] of PAGES) {
      test(`${title}: the app bar names the page, stays pinned after an 800px scroll and nothing overflows`, async ({ page }) => {
        await gotoHydrated(page, url);
        const bar = page.getByTestId("app-bar");
        await expect(page.getByTestId("app-bar-title")).toHaveText(title);
        // The brand shows on Games only.
        await expect(bar.getByRole("link", { name: /CK.s Picks/ })).toHaveCount(title === "Games" ? 1 : 0);
        expect(await bar.evaluate((node) => getComputedStyle(node).backgroundColor)).not.toBe("rgba(0, 0, 0, 0)");
        await page.mouse.wheel(0, 800);
        await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(300);
        await expect.poll(async () => Math.abs((await bar.boundingBox())!.y)).toBeLessThanOrEqual(1);
        const height = (await bar.boundingBox())!.height;
        expect(height).toBeLessThanOrEqual(60);
        expect(await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--app-bar-h"))).not.toBe("");
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      });
    }

    test("the menu sheet holds season, theme and the update time, closes on Escape and returns focus", async ({ page }) => {
      await gotoHydrated(page, "/");
      const menu = page.getByTestId("app-menu-button");
      await expect(menu).toBeEnabled();
      await menu.click();
      const dialog = page.getByRole("dialog", { name: "Menu", exact: true });
      await expect(dialog).toBeVisible();
      await expect(dialog.getByText("Season", { exact: true })).toBeVisible();
      await expect(dialog.getByRole("button", { name: /^Theme:/ })).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
      await expect(menu).toBeFocused();

      // Matchups carry a forecast update time, which the sheet shows.
      await gotoHydrated(page, "/matchup/1");
      await expect(page.getByTestId("app-bar-title")).toHaveText("Matchup");
      await expect(menu).toBeEnabled();
      await menu.click();
      await expect(dialog).toContainText(/Updated Sep (29|30)/);
    });

    test("the theme-color meta follows the toggle and the stored choice", async ({ page }) => {
      await gotoHydrated(page, "/");
      expect(await themeColor(page)).toBe("#fafafa");
      await page.getByTestId("app-menu-button").click();
      const toggle = page.getByRole("dialog", { name: "Menu", exact: true }).getByRole("button", { name: /^Theme:/ });
      await toggle.click(); // system -> light
      await expect(toggle).toHaveAttribute("title", "Theme: Light");
      expect(await themeColor(page)).toBe("#fafafa");
      await toggle.click(); // light -> dark
      await expect(toggle).toHaveAttribute("title", "Theme: Dark");
      expect(await themeColor(page)).toBe("#000000");
      await page.reload();
      await page.locator('html[data-hydrated="true"]').waitFor({ state: "attached" });
      expect(await themeColor(page)).toBe("#000000");
    });
  });
}

test("the Retrospective replay state stays on the Games page itself on phones", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoHydrated(page, "/?week=4");
  await expect(page.getByText("Retrospective replay", { exact: true })).toBeVisible();
  await expect(page.getByTestId("app-menu-button")).toBeEnabled();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
