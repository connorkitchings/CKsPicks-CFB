import { expect, test } from "@playwright/test";

for (const width of [375, 420]) {
  test(`market publication stays bounded and usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/?mode=market");

    const comparison = page.getByRole("table", { name: "Market and results" });
    await expect(comparison).toBeVisible();
    await expect(comparison.getByRole("columnheader", { name: "Market" })).toBeVisible();
    // Picks is forward-looking: results belong to the Results tab.
    await expect(comparison.getByRole("columnheader", { name: "Bet Result" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "2026 Season Record" })).toHaveCount(0);
    await expect(page.getByRole("table", { name: "Market and model comparison" })).toHaveCount(0);
    await expect(page.getByText("Blitzkrieg")).toHaveCount(0);
    await page.locator("#week-select").focus();
    await expect(page.locator("#week-select")).toBeFocused();
    await expect(page.getByText("1 / 3", { exact: true })).toHaveCount(0);
    await page.locator("#week-select").selectOption("1");
    await expect(page).toHaveURL(/week=1/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}

test("market results tab keeps the Bet Result column", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await page.goto("/results?mode=market");

  const comparison = page.getByRole("table", { name: "Market and results" }).first();
  await expect(comparison).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Market" })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Bet Result" })).toBeVisible();
});

test("prediction publication shows the selected-week comparison and season record", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await page.goto("/?mode=predictions");

  const banner = page.getByRole("region", { name: "2026 so far" });
  await expect(banner).toBeVisible();
  await expect(banner.getByText("Spread")).toBeVisible();
  await expect(banner.getByText("Total")).toBeVisible();
  await expect(banner.getByText("0–0–0").first()).toBeVisible();
  await expect(banner.getByText("— win rate").first()).toBeVisible();
  const comparison = page.getByRole("table", { name: "Market and model comparison" });
  await expect(comparison).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Market", exact: true })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Model", exact: true })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Bet", exact: true })).toBeVisible();
  // On picks tab, Bet Result is omitted from cards
  await expect(comparison.getByRole("columnheader", { name: "Bet Result" })).toHaveCount(0);

  // Both responsive table variants carry the edge note; either proves the tone.
  await expect(page.getByLabel("Model minus market (-1.0)").first()).toHaveClass(/edge-low/);
  await expect(page.getByLabel("Model minus market (+0.5)").first()).toHaveClass(/edge-low/);
  await expect(page.getByText("Blitzkrieg")).toBeVisible();
  await page.locator("#week-select").selectOption("1");
  await expect(page).toHaveURL(/week=1/);
  await expect(page.getByText("Trench Warfare V4")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);

  // On results tab, graded results (Win / Loss) are present
  await page.goto("/results?mode=predictions");
  const resultsComparison = page.getByRole("table", { name: "Market and model comparison" });
  await expect(resultsComparison.getByText("Loss").first()).toBeVisible();
  await expect(resultsComparison.getByText("Win").first()).toBeVisible();
});

test("prediction comparison retains the full desktop table", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.goto("/?mode=predictions");

  const comparison = page.getByRole("table", { name: "Market and model comparison" });
  await expect(comparison.getByRole("columnheader", { name: "Model Bet" })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Bet Result" })).toHaveCount(0);

  // Results tab preserves the desktop Bet Result column
  await page.goto("/results?mode=predictions");
  const resultsComparison = page.getByRole("table", { name: "Market and model comparison" });
  await expect(resultsComparison.getByRole("columnheader", { name: "Bet Result" })).toBeVisible();
});

test("V5 week shows its model label and season record", async ({ page }) => {
  await page.goto("/?mode=predictions&week=0");

  await expect(page.getByText("Blitzkrieg")).toBeVisible();
  const banner = page.getByRole("region", { name: "2026 so far" });
  await expect(banner).toBeVisible();
  await expect(banner.getByText("0–0–0").first()).toBeVisible();
  await expect(page.getByText("2026 · Week 0", { exact: true })).toHaveCount(0);
  await expect(page.getByText("2026", { exact: true })).toBeVisible();
  await expect(page.getByText("replay", { exact: true })).toHaveCount(0);
  await expect(page.getByText("published", { exact: true })).toHaveCount(0);
});

test("V5 record includes only results before the selected week", async ({ page }) => {
  await page.goto("/?mode=predictions&week=2");

  const banner = page.getByRole("region", { name: "2026 so far" });
  await expect(banner.getByText("1–0–0")).toBeVisible();
  await expect(banner.getByText("0–1–0")).toBeVisible();
});

test("legacy V4 fallback week renders its own model without the V5 banner", async ({ page }) => {
  await page.goto("/?mode=predictions&week=1");

  await expect(page.getByText("Trench Warfare V4")).toBeVisible();
  await expect(page.getByText("Blitzkrieg")).toHaveCount(0);
  await expect(page.getByRole("region", { name: "2026 so far" })).toHaveCount(0);
});

test("navigation exposes active tabs", async ({ page }) => {
  await page.goto("/?mode=predictions");

  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.getByRole("link", { name: "Picks" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Results" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Ratings" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Performance" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Method" })).toHaveCount(0);
});
