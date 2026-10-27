import { expect, test, type Locator } from "@playwright/test";
import { gotoHydrated } from "./helpers";

// Resolve modern CSS color-mix colors to sRGB without assuming a browser serialization.
async function chipStyles(root: Locator) {
  return root.locator("[data-rank-chip]").evaluateAll((chips) => chips.map((chip) => {
    const style = getComputedStyle(chip);
    const context = document.createElement("canvas").getContext("2d")!;
    context.fillStyle = "#000";
    context.fillRect(0, 0, 1, 1);
    context.fillStyle = style.backgroundColor;
    context.fillRect(0, 0, 1, 1);
    return {
      text: chip.textContent?.trim(),
      neutral: chip.hasAttribute("data-rank-none"),
      mix: Number(style.getPropertyValue("--rank-t")),
      background: style.backgroundColor,
      color: style.color,
      rgb: Array.from(context.getImageData(0, 0, 1, 1).data.slice(0, 3)),
    };
  }));
}

for (const scheme of ["light", "dark"] as const) {
  test(`matchup ranks and the always-dark export share the rank scale in ${scheme} mode`, async ({ page }, testInfo) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.addInitScript(() => {
      let release!: () => void;
      const ready = new Promise<void>((resolve) => { release = resolve; });
      Object.assign(window, { __releaseRankExport: release });
      Object.defineProperty(document.fonts, "ready", { get: () => ready, configurable: true });
    });
    await gotoHydrated(page, "/matchup/1");
    const live = await chipStyles(page.getByRole("table"));
    expect(live.some((chip) => chip.neutral)).toBe(true);
    const factors = await chipStyles(page.getByTestId("tale-of-the-tape").getByTestId("tape-row"));
    expect(factors.length).toBeGreaterThan(0);
    for (const chip of factors) {
      expect(live.some((other) => other.text === chip.text && other.mix === chip.mix && other.background === chip.background)).toBe(true);
    }

    // Collect the site's dark palette before starting an export (theme changes invalidate active exports).
    await page.locator("html").evaluate((element) => element.classList.add("dark"));
    const darkLive = await chipStyles(page.getByRole("region", { name: "Team stats", exact: true }));
    await page.locator("html").evaluate((element, dark) => element.classList.toggle("dark", dark), scheme === "dark");
    await expect.poll(() => page.locator("html").getAttribute("class")).toMatch(scheme === "dark" ? /dark/ : /^(?!.*dark)/);

    const download = page.waitForEvent("download");
    await page.getByTestId("share-download").click();
    const card = page.getByTestId("share-card");
    await expect(card).toBeAttached();
    const exported = await chipStyles(card);
    const green = exported.filter((chip) => !chip.neutral && chip.mix === 0);
    const red = exported.filter((chip) => !chip.neutral && chip.mix === 1);
    expect(green.length).toBeGreaterThan(0);
    expect(red.length).toBeGreaterThan(0);
    expect(exported.some((chip) => chip.neutral)).toBe(true);
    for (const chip of green) expect(chip.rgb[1]).toBeGreaterThan(chip.rgb[0]);
    for (const chip of red) expect(chip.rgb[0]).toBeGreaterThan(chip.rgb[1]);
    for (const chip of exported.filter((chip) => !chip.neutral)) expect(chip.color).toBe("rgb(244, 244, 245)");

    // Match the export against the site's dark palette even when exporting from light mode.
    for (const chip of exported) {
      if (!chip.neutral) {
        const matching = darkLive.find((other) => other.text === chip.text && other.mix === chip.mix);
        expect(matching, `live counterpart for ${chip.text}`).toBeDefined();
        expect(chip.background).toBe(matching!.background);
      }
    }
    await page.evaluate(() => (window as unknown as { __releaseRankExport: () => void }).__releaseRankExport());
    await (await download).saveAs(testInfo.outputPath("matchup-summary.png"));
    await expect(card).toHaveCount(0);
  });
}
