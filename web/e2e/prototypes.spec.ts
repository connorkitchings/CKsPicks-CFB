import { expect, test } from "@playwright/test";

const fits = (page: import("@playwright/test").Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

test.describe("picks prototype (/test-picks)", () => {
  test("shows record, top leans and the full slate", async ({ page }) => {
    await page.goto("/test-picks");

    await expect(page.getByRole("region", { name: "Record" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Top leans" })).toBeVisible();
    await expect(page.getByText("Showing 10 of 10 games · 8 with a lean")).toBeVisible();
    // Scored weeks link to the Results prototype, never a Picks view of a finished slate.
    await expect(page.getByRole("link", { name: "Wk 4" })).toHaveAttribute("href", "/test-results?week=4");
    await expect(page.locator("a[href='/test-picks?week=4']")).toHaveCount(0);
    // Only one navigation: the prototype header replaces the global nav.
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toHaveCount(1);
  });

  test("leans only, sort and list view work", async ({ page }) => {
    await page.goto("/test-picks");

    await page.getByRole("button", { name: /Leans only/ }).click();
    await expect(page.getByText("Showing 8 of 10 games")).toBeVisible();

    await page.locator("#proto-sort").selectOption("bestEdge");
    // Flat list, biggest edge first (Oregon @ USC total edge 8.7).
    await expect(page.locator("li[id^='game-']").first()).toHaveAttribute("id", "game-3");

    await page.getByRole("button", { name: "list", exact: true }).click();
    await expect(page.getByRole("button", { name: "list", exact: true })).toHaveAttribute("aria-pressed", "true");
    expect(await fits(page)).toBe(true);
  });

  test("fits a 390px phone without horizontal scroll", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto("/test-picks");
    expect(await fits(page)).toBe(true);
  });
});

test.describe("results prototype (/test-results)", () => {
  test("shows week and season records, highlights and the full slate", async ({ page }) => {
    await page.goto("/test-results");

    await expect(page.getByRole("region", { name: "Record" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Week 4" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Highlights" })).toBeVisible();
    await expect(page.getByText("Showing 9 of 9 games")).toBeVisible();
    // Upcoming weeks link back to the Picks prototype.
    await expect(page.getByRole("link", { name: "Wk 5" })).toHaveAttribute("href", "/test-picks?week=5");
    await expect(page.getByRole("link", { name: "Results" }).first()).toHaveAttribute("aria-current", "page");
  });

  test("result filters narrow the slate and every card shows a graded badge", async ({ page }) => {
    await page.goto("/test-results");

    const count = async () => {
      const text = (await page.getByText(/Showing \d+ of 9 games/).innerText()) ?? "";
      return Number(/Showing (\d+) of/.exec(text)?.[1]);
    };
    await page.getByRole("button", { name: /^Wins/ }).click();
    const wins = await count();
    expect(wins).toBeGreaterThan(0);
    expect(wins).toBeLessThan(9);
    await expect(page.locator("li[id^='game-']").first().getByText("Win", { exact: true }).first()).toBeVisible();

    await page.getByRole("button", { name: /^Losses/ }).click();
    expect(await count()).toBeGreaterThan(0);
    await page.getByRole("button", { name: /^All/ }).click();
    expect(await count()).toBe(9);
  });

  test("sort by biggest miss, list view and phone width all fit", async ({ page }) => {
    await page.goto("/test-results");
    await page.locator("#proto-sort").selectOption("worstResult");
    await page.getByRole("button", { name: "list", exact: true }).click();
    expect(await fits(page)).toBe(true);

    await page.setViewportSize({ width: 390, height: 800 });
    await page.getByRole("button", { name: "grid", exact: true }).click();
    expect(await fits(page)).toBe(true);
  });
});
