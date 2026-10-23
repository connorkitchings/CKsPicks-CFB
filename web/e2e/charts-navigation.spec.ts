import { expect, test } from "@playwright/test";

test("Stats is reachable from the main navigation and keeps the selected side when changing weeks on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto("/ratings");
  await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link")).toHaveText(["Games", "Ratings", "Stats", "Model"]);
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Stats", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Team charts" })).toBeVisible();
  await page.getByTestId("chart-select").selectOption({ label: "Efficiency vs explosiveness" });
  await expect(page).toHaveURL(/chart=efficiency/);
  await page.getByRole("button", { name: "Chart settings", exact: true }).click();
  await page.getByRole("group", { name: "Side of the ball" }).getByRole("link", { name: "defense", exact: true }).click();
  await expect(page.getByTestId("chart-subtitle")).toContainText("Defense");
  await page.getByLabel("Through Week", { exact: true }).selectOption("2");
  await page.getByRole("dialog").getByRole("button", { name: "Close", exact: true }).click();
  await expect(page).toHaveURL(/side=defense/);
  await expect(page.getByTestId("chart-subtitle")).toContainText("Through Week 2");
  await expect(page.getByTestId("chart-subtitle")).toContainText("Defense");
  await page.getByRole("combobox", { name: "Highlight a team" }).fill("Michigan");
  await page.getByRole("option", { name: /^Michigan/ }).click();
  await expect(page.locator("g[data-team='Michigan']")).toHaveAttribute("data-state", "searched");
  await expect(page.getByTestId("table-toggle")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
});
