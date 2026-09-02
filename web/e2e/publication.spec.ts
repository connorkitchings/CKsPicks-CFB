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
    await expect(page.getByText("Fixture Model")).toHaveCount(0);
    await page.locator("#week-select").focus();
    await expect(page.locator("#week-select")).toBeFocused();
    await page.locator("#week-select").selectOption("1");
    await expect(page).toHaveURL(/week=1/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}

test("prediction publication shows the selected-week record and comparison", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await page.goto("/?mode=predictions");

  await expect(page.getByRole("heading", { name: "2026 Season Record" })).toBeVisible();
  await expect(page.getByText("Through Week 0")).toBeVisible();
  const comparison = page.getByRole("table", { name: "Market and model comparison" });
  await expect(comparison).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Market", exact: true })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Model", exact: true })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Bet", exact: true })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Bet Result" })).toHaveCount(0);
  await expect(comparison.getByText("Loss")).toBeVisible();
  await expect(comparison.getByText("Win")).toBeVisible();
  await expect(comparison.getByLabel("Model minus market (-1.0)")).toHaveClass(/edge-low/);
  await expect(comparison.getByLabel("Model minus market (+0.5)")).toHaveClass(/edge-low/);
  await expect(page.getByText("Fixture Model")).toBeVisible();
  await page.locator("#week-select").selectOption("1");
  await expect(page).toHaveURL(/week=1/);
  await expect(page.getByText("Through Week 0")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
});

test("prediction comparison retains the full desktop table", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.goto("/?mode=predictions");

  const comparison = page.getByRole("table", { name: "Market and model comparison" });
  await expect(comparison.getByRole("columnheader", { name: "Model Bet" })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Bet Result" })).toBeVisible();
});
