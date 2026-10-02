import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

const built = fs.existsSync(path.join(process.cwd(), "public", "logos", "v2", "manifest.json"));

// Prototypes and the pages that ship: logos render at 16-80 px on all of them.
const PAGES = ["/test-picks", "/test-results", "/", "/results", "/matchup/1"];

test.describe("team logos", () => {
  test("every rendered logo loads and is never a broken image", async ({ page }) => {
    for (const url of PAGES) {
      await page.goto(url);
      await page.waitForLoadState("networkidle");
      const broken = await page.evaluate(() =>
        [...document.images].filter((img) => img.complete && img.naturalWidth === 0).length,
      );
      expect(broken, url).toBe(0);
    }
  });

  test("logos are sharp: natural width is at least 2x the displayed width", async ({ page }) => {
    test.skip(!built, "v2 logo set not built yet (web/scripts/build-team-logos.mjs)");
    for (const url of PAGES) {
      await page.goto(url);
      await page.waitForLoadState("networkidle");
      const bad = await page.evaluate(() =>
        [...document.querySelectorAll<HTMLImageElement>("img[data-logo]")]
          .filter((img) => img.offsetWidth > 0 && img.naturalWidth < 2 * img.clientWidth)
          .map((img) => `${img.src} ${img.naturalWidth}<2x${img.clientWidth}`),
      );
      expect(bad, url).toEqual([]);
    }
  });

  test("dark mode swaps to the dark file", async ({ page }) => {
    test.skip(!built, "v2 logo set not built yet");
    await page.emulateMedia({ colorScheme: "dark" });
    for (const url of PAGES) {
      await page.goto(url);
      await page.waitForLoadState("networkidle");
      const visible = await page.evaluate(() =>
        [...document.querySelectorAll<HTMLImageElement>("img[data-logo]")]
          .filter((img) => img.offsetWidth > 0)
          .map((img) => img.src),
      );
      expect(visible.length, url).toBeGreaterThan(0);
      expect(visible.every((src) => src.includes("/dark/")), url).toBe(true);
    }
  });

  test("the matchup hero logo follows its responsive size classes", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto("/matchup/1");
    const widths = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLImageElement>("img[data-logo]")]
        .filter((img) => img.offsetWidth > 0 && img.className.includes("h-16"))
        .map((img) => img.clientWidth),
    );
    expect(widths.length).toBeGreaterThan(0);
    expect(widths.every((w) => w === 64)).toBe(true);
  });
});
