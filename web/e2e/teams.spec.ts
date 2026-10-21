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
