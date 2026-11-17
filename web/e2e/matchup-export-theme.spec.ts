import sharp from "sharp";
import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

for (const theme of ["light", "dark"] as const) {
  test(`matchup PNG export follows the ${theme} page theme`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: theme });
    await gotoHydrated(page, "/matchup/1");
    await page.locator("html").evaluate((element, dark) => element.classList.toggle("dark", dark), theme === "dark");
    const download = page.waitForEvent("download");
    await page.getByTestId("share-download").click();
    await expect(page.getByTestId("share-card")).toHaveAttribute("data-theme", theme);
    const file = await (await download).path();
    const { data } = await sharp(file).extract({ left: 2, top: 2, width: 1, height: 1 }).raw().toBuffer({ resolveWithObject: true });
    const luminance = (data[0] + data[1] + data[2]) / 3;
    if (theme === "light") expect(luminance).toBeGreaterThan(200);
    else expect(luminance).toBeLessThan(60);
  });
}

test("matchup page text is at least 11px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoHydrated(page, "/matchup/1");
  const small = await page.evaluate(() => {
    const found: string[] = [];
    for (const element of document.body.querySelectorAll("*")) {
      if (element.closest("svg")) continue;
      if (![...element.childNodes].some((node) => node.nodeType === 3 && node.textContent?.trim())) continue;
      const style = getComputedStyle(element);
      if (!element.getBoundingClientRect().width || style.visibility === "hidden") continue;
      if (parseFloat(style.fontSize) < 11 && (element.textContent?.trim().length ?? 0) > 2) found.push(`${style.fontSize} ${element.textContent?.trim().slice(0, 30)}`);
    }
    return found;
  });
  expect(small, small.join(" | ")).toEqual([]);
});
