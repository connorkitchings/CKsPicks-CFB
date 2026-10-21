import { expect, test } from "@playwright/test";

// Side/picker links intentionally drop fixture=, so these are genuine Next client
// transitions from a retained charts_v1 release to charts_v2, then cached navigation
// back to v1. The shared ChartsView stays mounted while its capabilities change.
test("efficiency resets its metric when release chart capabilities change", async ({ page }) => {
  await page.goto("/stats?chart=efficiency&fixture=v1&week=3");
  await expect(page.getByTestId("efficiency-metric-switcher")).toHaveCount(0);
  await expect(page.getByTestId("scatter-chart").locator("g[data-team]")).toHaveCount(16);
  await page.getByRole("link", { name: "defense", exact: true }).click();
  await expect(page).not.toHaveURL(/fixture=/);
  await expect(page.getByTestId("metric-toggle-explosive-rate")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("metric-toggle-yards-per-success").click();
  await expect(page.getByTestId("metric-toggle-yards-per-success")).toHaveAttribute("aria-pressed", "true");
  await page.goBack();
  await expect(page).toHaveURL(/fixture=v1/);
  await expect(page.getByTestId("efficiency-metric-switcher")).toHaveCount(0);
  await expect(page.getByTestId("scatter-chart").locator("g[data-team]")).toHaveCount(16);
  await expect(page.getByTestId("scatter-chart").getByText("PPA/play", { exact: true })).toBeVisible();
});

test("game log drops a yardage metric when navigating back to a retained release", async ({ page }) => {
  await page.goto("/stats?chart=game-log&fixture=v1&team=Alabama&metric=ppa");
  await expect(page.getByTestId("game-log-metric-ppa")).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("navigation", { name: "Chart type" }).getByRole("link", { name: "Game log", exact: true }).click();
  await expect(page).not.toHaveURL(/fixture=/);
  await expect(page.getByTestId("game-log-metric-success")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("game-log-metric-explosive-rate").click();
  await expect(page.getByTestId("game-log-metric-explosive-rate")).toHaveAttribute("aria-pressed", "true");
  await page.goBack();
  await expect(page).toHaveURL(/fixture=v1/);
  await expect(page.getByTestId("game-log-metric-explosive-rate")).toHaveCount(0);
  await expect(page.getByTestId("game-log-metric-ppa")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("game-log-season-offense")).not.toContainText("n/a");
});
