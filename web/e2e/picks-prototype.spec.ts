import { expect, test } from "@playwright/test";

test("picks prototype shows record, top leans and the full slate", async ({ page }) => {
  await page.goto("/test");

  await expect(page.getByRole("region", { name: "Record" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Top leans" })).toBeVisible();
  await expect(page.getByText("Showing 10 of 10 games · 8 with a lean")).toBeVisible();
  // Only one navigation: the prototype header replaces the global nav.
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toHaveCount(1);
});

test("leans only, sort and list view work", async ({ page }) => {
  await page.goto("/test");

  await page.getByRole("button", { name: /Leans only/ }).click();
  await expect(page.getByText("Showing 8 of 10 games")).toBeVisible();

  await page.locator("#proto-sort").selectOption("bestEdge");
  // Flat list, biggest edge first (Oregon @ USC total edge 8.7).
  await expect(page.locator("li[id^='game-']").first()).toHaveAttribute("id", "game-3");

  await page.getByRole("button", { name: "list", exact: true }).click();
  await expect(page.getByRole("button", { name: "list", exact: true })).toHaveAttribute("aria-pressed", "true");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("prototype fits a 390px phone without horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/test");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
