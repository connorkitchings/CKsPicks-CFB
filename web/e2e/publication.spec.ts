import { expect, test } from "@playwright/test";

for (const width of [375, 420]) {
  test(`market publication stays bounded and usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/?mode=market");

    await expect(page.getByText("Market Consensus")).toBeVisible();
    await expect(page.getByText("Spread win")).toBeVisible();
    await expect(page.getByText("Total push")).toBeVisible();
    await expect(page.getByText("Model projection:")).toHaveCount(0);
    await expect(page.getByText("Fixture Model")).toHaveCount(0);
    await page.locator("#week-select").focus();
    await expect(page.locator("#week-select")).toBeFocused();
    await page.locator("#week-select").selectOption("1");
    await expect(page).toHaveURL(/week=1/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}

test("prediction publication shows its own grades and model content", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await page.goto("/?mode=predictions");

  await expect(page.getByText("Model projection:")).toBeVisible();
  await expect(page.getByText("Spread loss")).toBeVisible();
  await expect(page.getByText("Total win")).toBeVisible();
  await expect(page.getByText("Fixture Model")).toBeVisible();
});
