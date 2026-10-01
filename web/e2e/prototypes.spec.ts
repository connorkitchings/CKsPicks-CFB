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

  test("explains each lean's direction once, without a second market/model table", async ({ page }) => {
    await page.goto("/test-picks");

    // Edge sits in parentheses next to the pick; no separate "Edge" label.
    await expect(page.getByText("(5.1)").first()).toBeVisible();
    await expect(page.getByText(/^Edge \d/)).toHaveCount(0);
    // One line under the pick: what it means plus the model's number.
    await expect(page.getByText(/^wins by more than 2\.5 · model: wins by 7\.6$/).first()).toBeVisible();
    await expect(page.getByText(/^total below 57\.5 · model: 54\.1$/).first()).toBeVisible();
    await expect(page.getByText(/^loses by under 1\.5, or wins · model: wins by 0\.4$/).first()).toBeVisible();
    // The old Market / Model grid is gone from the cards.
    await expect(page.getByText("Market", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Model", { exact: true })).toHaveCount(0);
  });

  test("top of the page shows how the model is doing against break-even", async ({ page }) => {
    await page.goto("/test-picks");

    const record = page.getByRole("region", { name: "Record" });
    await expect(record.getByRole("heading", { name: "How the model is doing" })).toBeVisible();
    await expect(record.getByRole("heading", { name: "Season" })).toBeVisible();
    // Spread and total each show their gap to 52.4%; there is no Live/Replay split.
    await expect(record.getByText(/pts vs 52\.4% break-even/)).toHaveCount(2);
    await expect(record.getByText(/Live/)).toHaveCount(0);
    // How big the misses typically are, for taking picks with a grain of salt.
    await expect(record.getByText(/Average miss: 14\.5 pts on the margin, 13\.4 on totals\./)).toBeVisible();
    await expect(record.getByText(/read it as a back-test/)).toBeVisible();
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

  test("weekly record is not benchmarked; season records are; finals read from the pick's side", async ({ page }) => {
    await page.goto("/test-results");

    const record = page.getByRole("region", { name: "Record" });
    await expect(record.getByText(/small sample/)).toBeVisible();
    // Only the two season cells carry a break-even comparison.
    await expect(record.getByText(/pts vs 52\.4% break-even/)).toHaveCount(2);
    await expect(record.getByText(/Live/)).toHaveCount(0);
    await expect(page.getByText(/model: wins by 8\.6 · final: won by 7/).first()).toBeVisible();
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
