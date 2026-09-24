import { expect, test } from "@playwright/test";

for (const width of [375, 420]) {
  test(`market publication stays bounded and usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/?mode=market");

    const comparison = page.getByRole("table", { name: "Market and results" });
    await expect(comparison).toBeVisible();
    await expect(comparison.getByRole("columnheader", { name: "Market" })).toBeVisible();
    await expect(comparison.getByRole("columnheader", { name: "Bet Result" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "2026 Season Record" })).toHaveCount(0);
    await expect(page.getByRole("table", { name: "Market and model comparison" })).toHaveCount(0);
    await expect(page.getByText("Trench Warfare V5")).toHaveCount(0);
    await page.locator("#week-select").focus();
    await expect(page.locator("#week-select")).toBeFocused();
    await page.locator("#week-select").selectOption("1");
    await expect(page).toHaveURL(/week=1/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}

test("prediction publication shows the selected-week comparison and banner", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await page.goto("/?mode=predictions");

  const banner = page.getByRole("region", { name: "V5 season performance" });
  await expect(banner).toBeVisible();
  await expect(banner.getByText("replay forecasts")).toBeVisible();
  const comparison = page.getByRole("table", { name: "Market and model comparison" });
  await expect(comparison).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Market", exact: true })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Model", exact: true })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Bet", exact: true })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Bet Result" })).toHaveCount(0);
  await expect(comparison.getByText("Loss")).toBeVisible();
  await expect(comparison.getByText("Win")).toBeVisible();
  // Both responsive table variants carry the edge note; either proves the tone.
  await expect(page.getByLabel("Model minus market (-1.0)").first()).toHaveClass(/edge-low/);
  await expect(page.getByLabel("Model minus market (+0.5)").first()).toHaveClass(/edge-low/);
  await expect(page.getByText("Trench Warfare V5")).toBeVisible();
  await page.locator("#week-select").selectOption("1");
  await expect(page).toHaveURL(/week=1/);
  await expect(page.getByText("Trench Warfare V4")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
});

test("prediction comparison retains the full desktop table", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.goto("/?mode=predictions");

  const comparison = page.getByRole("table", { name: "Market and model comparison" });
  await expect(comparison.getByRole("columnheader", { name: "Model Bet" })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Bet Result" })).toBeVisible();
});

test("V5 week shows its model label and the replay performance banner", async ({ page }) => {
  await page.goto("/?mode=predictions&week=0");

  await expect(page.getByText("Trench Warfare V5")).toBeVisible();
  const banner = page.getByRole("region", { name: "V5 season performance" });
  await expect(banner).toBeVisible();
  await expect(banner.getByText("replay forecasts")).toBeVisible();
  await expect(banner.getByText("live forecasts")).toBeVisible();
});

test("legacy V4 fallback week renders its own model without the V5 banner", async ({ page }) => {
  await page.goto("/?mode=predictions&week=1");

  await expect(page.getByText("Trench Warfare V4")).toBeVisible();
  await expect(page.getByText("Trench Warfare V5")).toHaveCount(0);
  await expect(page.getByRole("region", { name: "V5 season performance" })).toHaveCount(0);
  await expect(page.getByText("replay forecasts")).toHaveCount(0);
});
