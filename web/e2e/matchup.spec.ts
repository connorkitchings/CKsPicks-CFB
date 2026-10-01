import { expect, test } from "@playwright/test";

test.describe("matchup page (fixture mode)", () => {
  test("shows both unit tables with opposing defense pairing, ranks, and a dash for unranked", async ({ page }) => {
    await page.goto("/matchup/1");
    await expect(page.getByRole("region", { name: "Team stats" })).toBeVisible();
    await expect(page.getByRole("table")).toHaveCount(2);
    const first = page.getByRole("table").first();
    await expect(first).toHaveAccessibleName(/Offense vs .* Defense/);
    await expect(first.getByText("Pass EPA/play")).toBeVisible();
    await expect(page.getByText(/FBS opponents only, garbage time excluded/)).toBeVisible();
    // The away team is unranked in the fixture: a dash, never "#null".
    await expect(page.getByText("#null")).toHaveCount(0);
    await expect(first.getByTitle("Not ranked yet").first()).toBeVisible();
  });

  test("does not overflow at phone width", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/matchup/1");
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
    expect(fits).toBe(true);
  });

  test("is noindex and unknown games show the not-found page", async ({ page }) => {
    await page.goto("/matchup/1");
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
    // Unknown ids stream the 404 page (the root loading boundary has already sent 200).
    await page.goto("/matchup/987654");
    await expect(page.getByText("This page could not be found")).toBeVisible();
    await expect(page.getByRole("region", { name: "Team stats" })).toHaveCount(0);
    await page.goto("/matchup/abc");
    await expect(page.getByText("This page could not be found")).toBeVisible();
  });
});
