import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

const built = fs.existsSync(path.join(process.cwd(), "public", "logos", "v2", "manifest.json"));

// The pages that ship: logos render at 16-80 px on all of them.
const PAGES = ["/", "/results", "/matchup/1", "/charts"];

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

  test("dark mode preserves readable team colors and uses contrast variants elsewhere", async ({ page }) => {
    test.skip(!built, "v2 logo set not built yet");
    await page.emulateMedia({ colorScheme: "dark" });
    for (const url of PAGES) {
      await page.goto(url);
      await page.waitForLoadState("networkidle");
      const visible = await page.evaluate(() => [
        ...[...document.querySelectorAll<HTMLImageElement>("img[data-logo]")]
          .filter((img) => img.offsetWidth > 0)
          .map((img) => img.src),
        // Charts draw logos as SVG <image> pairs; the hidden variant has display: none.
        ...[...document.querySelectorAll<SVGImageElement>("svg image")]
          .filter((image) => getComputedStyle(image).display !== "none")
          .map((image) => image.href.baseVal),
      ]);
      expect(visible.length, url).toBeGreaterThan(0);
      for (const src of visible) {
        expect(src, url).toMatch(/\/(2633|228|2534|251|249|2084|254)\.webp$/.test(src)
          ? /\/light\/\d+\.webp$/
          : /\/dark\/\d+\.webp$/);
      }
    }
  });

  test("Tennessee stays orange in dark Picks, Results, chart markers and PNG capture", async ({ page }) => {
    test.skip(!built, "v2 logo set not built yet");
    await page.emulateMedia({ colorScheme: "dark" });
    for (const url of ["/", "/results"]) {
      await page.goto(url);
      const tennessee = page.locator('img[data-logo][src$="/2633.webp"]:visible');
      await expect(tennessee.first()).toBeVisible();
      for (const image of await tennessee.all()) {
        await expect(image).toHaveAttribute("src", /\/light\/2633\.webp$/);
      }
      await expect(page.locator('img[data-logo][src$="/dark/130.webp"]:visible').first()).toBeVisible();
    }

    await page.goto("/charts?chart=efficiency&week=2&fixture=slate");
    for (const [team, id] of [
      ["Tennessee", 2633], ["Clemson", 228], ["Sam Houston", 2534], ["Texas", 251],
      ["North Texas", 249], ["Buffalo", 2084], ["Utah", 254],
    ] as const) {
      await expect(page.locator(`g[data-team="${team}"] image:visible`)).toHaveAttribute("href", `/logos/v2/sm/light/${id}.webp`);
    }
    for (const [team, id] of [["Michigan", 130], ["Alabama", 333]] as const) {
      await expect(page.locator(`g[data-team="${team}"] image:visible`)).toHaveAttribute("href", `/logos/v2/sm/dark/${id}.webp`);
    }

    // Observe the transient static SVG that is rasterized into the downloaded PNG.
    await page.evaluate(() => {
      const root = document.querySelector('[data-testid="chart-export"]')!;
      const sources: string[] = [];
      const observer = new MutationObserver(() => {
        const svg = root.querySelector("div[aria-hidden] svg");
        if (svg) sources.push(...[...svg.querySelectorAll<SVGImageElement>('image[href$="/2633.webp"]')]
          .filter((image) => getComputedStyle(image).display !== "none")
          .map((image) => image.href.baseVal));
      });
      observer.observe(root, { childList: true, subtree: true });
      (window as typeof window & { logoCapture?: () => string[] }).logoCapture = () => {
        observer.disconnect();
        return sources;
      };
    });
    const download = page.waitForEvent("download");
    await page.getByTestId("chart-download").click();
    expect(await (await download).failure()).toBeNull();
    const capture = await page.evaluate(() => {
      const state = window as typeof window & { logoCapture?: () => string[] };
      const sources = state.logoCapture!();
      delete state.logoCapture;
      return sources;
    });
    expect(capture.length).toBeGreaterThan(0);
    expect(capture.every((src) => src === "/logos/v2/sm/light/2633.webp")).toBe(true);
    const report = JSON.parse(await page.getByTestId("chart-export").getAttribute("data-last-export") ?? "{}");
    expect(report.logos).toBeGreaterThan(0);
    expect(report.decoded).toBe(report.logos);
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
