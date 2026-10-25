import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

const VIEWPORTS = [
  { width: 1440, height: 900, bar: "header" },
  { width: 1280, height: 800, bar: "header" },
  { width: 390, height: 844, bar: '[data-testid="app-bar"]' },
  { width: 320, height: 568, bar: '[data-testid="app-bar"]' },
] as const;
const COLORS = { light: "rgb(32, 52, 77)", dark: "rgb(248, 250, 252)" } as const;

for (const vp of VIEWPORTS) {
  for (const theme of ["light", "dark"] as const) {
    test.describe(`wordmark at ${vp.width}px, ${theme} theme`, () => {
      test.use({ viewport: { width: vp.width, height: vp.height } });

      test.beforeEach(async ({ page }) => {
        await page.addInitScript((t) => localStorage.setItem("theme", t), theme);
        await gotoHydrated(page, "/");
      });

      test("is named, themed, contained and links home", async ({ page }) => {
        const bar = page.locator(vp.bar).first();
        const link = bar.getByRole("link", { name: /Crest CFB/ });
        await expect(link).toHaveCount(1);
        const svg = link.locator("svg");
        await expect(svg).toBeVisible();

        const box = (await svg.boundingBox())!;
        const barBox = (await bar.boundingBox())!;
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.x + box.width).toBeLessThanOrEqual(vp.width);
        expect(box.y).toBeGreaterThanOrEqual(barBox.y);
        expect(box.y + box.height).toBeLessThanOrEqual(barBox.y + barBox.height);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

        expect(await link.evaluate((el) => getComputedStyle(el).color)).toBe(COLORS[theme]);
        expect(await svg.locator("path").first().evaluate((el) => getComputedStyle(el).fill)).toBe(COLORS[theme]);
      });

      test("shows a focus outline for keyboard focus and navigates home on click", async ({ page }) => {
        const link = page.locator(vp.bar).first().getByRole("link", { name: /Crest CFB/ });
        for (let i = 0; i < 8 && !(await link.evaluate((el) => el === document.activeElement)); i++) {
          await page.keyboard.press("Tab");
        }
        await expect(link).toBeFocused();
        const outline = await link.evaluate((el) => {
          const s = getComputedStyle(el);
          return { style: s.outlineStyle, width: parseFloat(s.outlineWidth) };
        });
        expect(outline.style).not.toBe("none");
        expect(outline.width).toBeGreaterThan(0);

        await page.goto("/ratings");
        await link.click();
        await expect(page).toHaveURL(/\/$/);
      });
    });
  }
}
