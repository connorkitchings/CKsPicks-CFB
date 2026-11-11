import { expect, test } from "@playwright/test";

// `?finalWeek=4` (UI test mode only) makes the scored fixture week the final, active and only published week.

test("the final regular-season week shows the season-complete notice with the final record", async ({ page }) => {
  await page.goto("/?finalWeek=4");
  await expect(page.getByText("Regular season complete")).toBeVisible();
  await expect(page.getByTestId("regular-season-record")).toContainText("Final record: spread");
  await expect(page.getByTestId("regular-season-scope")).toContainText("Postseason games are not predicted, graded");
});

test("an ordinary week shows no season-complete notice", async ({ page }) => {
  await page.goto("/?week=4");
  await expect(page.getByText("Regular season complete")).toHaveCount(0);
  await page.goto("/");
  await expect(page.getByText("Regular season complete")).toHaveCount(0);
});

test("the season-complete notice fits a 320px phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto("/?finalWeek=4");
  await expect(page.getByText("Regular season complete")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
});
