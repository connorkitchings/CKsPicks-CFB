import sharp from "sharp";
import { expect, test } from "@playwright/test";

for (const theme of ["light", "dark"] as const) {
  test(`PNG keeps the visible Alabama logo variant in ${theme} mode`, async ({ page }, testInfo) => {
    await page.emulateMedia({ colorScheme: theme });
    await page.goto("/stats?chart=adjusted&week=3&team=Alabama");
    await expect(page.getByTestId("scatter-chart")).toBeVisible();
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => {
      type Probe = { x: number; y: number; width: number; height: number; source: string; displays: string[] };
      const state = window as typeof window & { logoExportProbe?: Probe };
      const root = document.querySelector('[data-testid="chart-export"]')!;
      const observer = new MutationObserver(() => {
        const card = root.querySelector('[data-testid="export-card"]');
        const images = card?.querySelectorAll<SVGImageElement>('g[data-team="Alabama"] image');
        if (!card || !images?.length) return;
        const visible = [...images].find((image) => getComputedStyle(image).display !== "none");
        if (!visible) return;
        const cardRect = card.getBoundingClientRect();
        const imageRect = visible.getBoundingClientRect();
        state.logoExportProbe = {
          x: imageRect.x - cardRect.x, y: imageRect.y - cardRect.y,
          width: imageRect.width, height: imageRect.height,
          source: visible.getAttribute("href")!, displays: [...images].map((image) => getComputedStyle(image).display),
        };
        observer.disconnect();
      });
      observer.observe(root, { childList: true, subtree: true });
    });
    const downloadEvent = page.waitForEvent("download");
    await page.getByTestId("chart-download").click();
    const download = await downloadEvent;
    const path = testInfo.outputPath(`adjusted-${theme}-export.png`);
    await download.saveAs(path);
    const probe = await page.evaluate(() => (window as typeof window & {
      logoExportProbe?: { x: number; y: number; width: number; height: number; source: string; displays: string[] };
    }).logoExportProbe);
    expect(probe).toBeTruthy();
    expect(probe!.source).toContain(`/sm/${theme}/333.webp`);
    expect(probe!.displays.filter((display) => display === "none")).toHaveLength(1);
    const { data, info } = await sharp(path).extract({
      left: Math.round(probe!.x * 2), top: Math.round(probe!.y * 2),
      width: Math.floor(probe!.width * 2), height: Math.floor(probe!.height * 2),
    }).removeAlpha().raw().toBuffer({ resolveWithObject: true });
    let red = 0;
    let white = 0;
    for (let i = 0; i < data.length; i += info.channels) {
      const [r, g, b] = [data[i], data[i + 1], data[i + 2]];
      if (r > 80 && r > g * 1.8 && r > b * 1.5) red++;
      if (r > 200 && g > 200 && b > 200) white++;
    }
    const area = info.width * info.height;
    await testInfo.attach("logo-color-summary", { body: JSON.stringify({ theme, redFraction: red / area, whiteFraction: white / area }), contentType: "application/json" });
    // Before the fix, light mode's SVG clone paints the white dark variant
    // over the red A, despite the on-screen card reporting that variant hidden.
    if (theme === "light") expect(red / area).toBeGreaterThan(0.12);
    else expect(white / area).toBeGreaterThan(0.12);
    const report = JSON.parse((await page.getByTestId("chart-export").getAttribute("data-last-export")) ?? "{}");
    expect(report.decoded).toBe(report.logos);
    expect(report.logos).toBeGreaterThan(0);
  });
}
