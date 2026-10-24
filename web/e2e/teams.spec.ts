import { expect, test } from "@playwright/test";

test.describe("team pages (fixture mode)", () => {
  test("a normal team shows its history and games", async ({ page }) => {
    await page.goto("/teams/Texas");
    await expect(page.getByRole("heading", { level: 1, name: "Texas" })).toBeVisible();
    await expect(page).toHaveTitle(/Texas · Team page/);
    await expect(page.getByRole("heading", { name: "Rating history" })).toBeVisible();
    await expect(page.getByRole("table")).toBeVisible();
    await expect(page.getByRole("link", { name: "← All ratings" })).toBeVisible();
  });

  for (const width of [390, 1280]) {
    test(`the summary shows record, SOR and one SOS rank at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/teams/Texas");
      const summary = page.locator('dl[aria-label="Team summary"]');
      await expect(summary.locator("dt")).toHaveText(["Record", "SOR", "SOS"]);
      await expect(summary.locator("dd").nth(0)).toHaveText("4–0");
      await expect(summary.locator("dd")).toHaveCount(3);
      await expect(summary.locator("dd").nth(1)).toHaveText(/^#\d+$/);
      // Same played-SOS rank the ratings table shows for Texas (third of four).
      await expect(summary.locator("dd").nth(2)).toHaveText("#3");
      await expect(summary.locator('[title="Strength of schedule played"]')).toHaveCount(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
  }

  test("legacy rating names and CFBD names reach the same page", async ({ page }) => {
    for (const segment of ["San%20Jos%C3%A9%20State", "San%20Jose%20State", "Hawai'i", "Hawai_i"]) {
      const response = await page.goto(`/teams/${segment}`);
      expect(response?.status(), segment).toBe(200);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(/San José State|Hawai'i/);
    }
  });

  test("an unknown team is a 404", async ({ page }) => {
    const response = await page.goto("/teams/Nowhere%20State");
    expect(response?.status()).toBe(404);
  });
});
