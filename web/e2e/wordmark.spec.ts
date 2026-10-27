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

      test("is named, themed, contained and links home", async ({ page }, testInfo) => {
        const bar = page.locator(vp.bar).first();
        const link = bar.getByRole("link", { name: /Stratum CFB/ });
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
        await page.screenshot({ path: testInfo.outputPath("wordmark.png") });
      });

      test("shows a focus outline for keyboard focus and navigates home on click", async ({ page }) => {
        const link = page.locator(vp.bar).first().getByRole("link", { name: /Stratum CFB/ });
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

test("metadata and generated image routes use the current identity", async ({ page, request }) => {
  await gotoHydrated(page, "/");
  await expect(page).toHaveTitle(/Stratum CFB/);
  await expect(page.locator('meta[name="application-name"]')).toHaveAttribute("content", "Stratum CFB");
  await expect(page.locator('meta[property="og:site_name"]')).toHaveAttribute("content", "Stratum CFB");
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute("content", /Stratum CFB/);
  await expect(page.locator('meta[name="twitter:title"]')).toHaveAttribute("content", /Stratum CFB/);
  for (const [selector, width, height] of [
    ['link[rel="icon"]', 32, 32],
    ['meta[property="og:image"]', 1200, 630],
  ] as const) {
    const url = await page.locator(selector).first().getAttribute(selector.startsWith("link") ? "href" : "content");
    expect(url).toBeTruthy();
    const imageUrl = new URL(url!, page.url());
    const response = await request.get(imageUrl.pathname + imageUrl.search);
    expect(response.ok()).toBeTruthy();
    expect(response.headers()["content-type"]).toContain("image/png");
    const png = await response.body();
    expect(png.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
    expect(png.readUInt32BE(16)).toBe(width);
    expect(png.readUInt32BE(20)).toBe(height);
  }
});
