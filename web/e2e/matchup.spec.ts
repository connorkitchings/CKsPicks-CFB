import { expect, test } from "@playwright/test";

test.describe("matchup page (fixture mode)", () => {
  test("shows both unit tables with opposing defense pairing, ranks, and a dash for unranked", async ({ page }) => {
    await page.goto("/matchup/1");
    await expect(page.getByRole("region", { name: "Team stats" })).toBeVisible();
    await expect(page.getByRole("table")).toHaveCount(2);
    const first = page.getByRole("table").first();
    await expect(first).toHaveAccessibleName(/Offense vs .* Defense/);
    await expect(first.getByText("Pass EPA/play")).toBeVisible();
    // V5 possession metrics are grouped under section headers (14 rows, 3 sections).
    await expect(first.getByText("Core possession efficiency")).toBeVisible();
    await expect(first.getByText("Situational / down and distance")).toBeVisible();
    await expect(first.getByText("Drive context")).toBeVisible();
    await expect(first.getByText("Points/possession")).toBeVisible();
    await expect(first.getByText("Non-offense pts/game")).toBeVisible();
    await expect(first.locator("tbody tr").filter({ has: page.locator("td") })).toHaveCount(14);
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

  test("the /matchup index lists the week's games and links to each breakdown", async ({ page }) => {
    await page.goto("/matchup");
    await expect(page.getByRole("heading", { name: "Matchups" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Week 5" })).toHaveAttribute("aria-current", "page");
    const links = page.locator("a[href^='/matchup/']");
    expect(await links.count()).toBeGreaterThan(3);
    await links.first().click();
    await expect(page).toHaveURL(/\/matchup\/\d+$/);
    await expect(page.getByRole("region", { name: "Team stats" })).toBeVisible();
    await page.getByRole("link", { name: /All Week \d+ matchups/ }).click();
    await expect(page).toHaveURL(/\/matchup\?week=\d+$/);
  });

  test("the index is noindex and fits a phone", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/matchup");
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });

  test("game cards carry a Matchup button that opens the breakdown, and team names are not links", async ({ page }) => {
    await page.goto("/");
    const home = page.getByTestId("matchup-link");
    expect(await home.count()).toBeGreaterThanOrEqual(1);
    await expect(home.first()).toHaveAttribute("href", /^\/matchup\/\d+$/);
    // The prototype slate's ids are the ones the matchup fixtures know, so click through there.
    await page.goto("/test-picks");
    await page.getByTestId("matchup-link").first().click();
    await expect(page).toHaveURL(/\/matchup\/\d+$/);
    await expect(page.getByRole("region", { name: "Team stats" })).toBeVisible();
    // No team name anywhere links to a team page (cards, hero, matchup footer).
    expect(await page.locator("a[href^='/teams/']").count()).toBe(0);
    await page.goto("/");
    expect(await page.locator("a[href^='/teams/']").count()).toBe(0);
    await page.goto("/results");
    expect(await page.getByTestId("matchup-link").count()).toBeGreaterThanOrEqual(1);
    expect(await page.locator("a[href^='/teams/']").count()).toBe(0);
    await page.goto("/ratings");
    expect(await page.locator("a[href^='/teams/']").count()).toBe(0);
  });

  test("prototype cards also carry the Matchup button", async ({ page }) => {
    await page.goto("/test-picks");
    expect(await page.getByTestId("matchup-link").count()).toBeGreaterThan(3);
    await page.goto("/test-results");
    expect(await page.getByTestId("matchup-link").count()).toBeGreaterThan(3);
  });
});
