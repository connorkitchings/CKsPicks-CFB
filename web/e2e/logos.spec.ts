import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

const built = fs.existsSync(path.join(process.cwd(), "public", "logos", "v2", "manifest.json"));

test.describe("team logos", () => {
  test("every rendered logo loads and is never a broken image", async ({ page }) => {
    await page.goto("/test-picks");
    const broken = await page.evaluate(() =>
      [...document.images].filter((img) => img.complete && img.naturalWidth === 0).length,
    );
    expect(broken).toBe(0);
  });

  test("logos are sharp: natural width is at least 2x the displayed width", async ({ page }) => {
    test.skip(!built, "v2 logo set not built yet (web/scripts/build-team-logos.mjs)");
    for (const url of ["/test-picks", "/test-results"]) {
      await page.goto(url);
      await page.waitForLoadState("networkidle");
      const bad = await page.evaluate(() =>
        [...document.querySelectorAll<HTMLImageElement>("img[data-logo]")]
          .filter((img) => img.offsetWidth > 0 && img.naturalWidth < 2 * img.clientWidth)
          .map((img) => `${img.src} ${img.naturalWidth}<2x${img.clientWidth}`),
      );
      expect(bad).toEqual([]);
    }
  });

  test("dark mode swaps to the dark file", async ({ page }) => {
    test.skip(!built, "v2 logo set not built yet");
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/test-picks");
    const visible = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLImageElement>("img[data-logo]")]
        .filter((img) => img.offsetWidth > 0)
        .map((img) => img.src),
    );
    expect(visible.length).toBeGreaterThan(0);
    expect(visible.every((src) => src.includes("/dark/"))).toBe(true);
  });
});
