import { expect, test } from "@playwright/test";

test.describe("matchup page (fixture mode)", () => {
  test("shows both unit tables: 12 grouped metrics, ties, an unranked zero and unranked dashes", async ({ page }) => {
    await page.goto("/matchup/1");
    await expect(page.getByRole("region", { name: "Team stats" })).toBeVisible();
    await expect(page.getByRole("table")).toHaveCount(2);
    const first = page.getByRole("table").first();
    await expect(first).toHaveAccessibleName(/Offense vs .* Defense/);
    for (const section of ["Core possession efficiency", "Situational / down and distance", "Drive context"]) {
      await expect(first.getByText(section)).toBeVisible();
    }
    for (const label of ["Points/possession", "EPA/possession", "EPA/play", "Pass EPA/play"]) {
      const escaped = label.replace(/[/]/g, "\\/");
      await expect(first.locator("td").filter({ hasText: new RegExp(`^${escaped}`) }).first()).toBeVisible();
    }
    // Plays/possession and non-offense points are stored but not shown.
    await expect(page.getByText("Non-offense pts/game")).toHaveCount(0);
    await expect(page.getByText("Plays/possession")).toHaveCount(0);
    await expect(first.locator("tbody tr").filter({ has: page.locator("td") })).toHaveCount(12);
    await expect(page.getByText(/FBS opponents only, regulation\s+play, garbage time excluded/)).toBeVisible();
    await expect(page.getByText("#null")).toHaveCount(0);
    // Ties show as T-N; unranked rows (no sample or an exact zero) show a dash with a "Not ranked" tooltip.
    await expect(page.getByText(/^T-\d+$/).first()).toBeVisible();
    await expect(first.getByTitle("Not ranked").first()).toBeVisible();
  });

  test("an exact zero shows its value but no rank and no edge", async ({ page }) => {
    await page.goto("/matchup/1");
    const row = page
      .getByRole("table")
      .first()
      .locator("tr", { hasText: "Explosive plays" });
    await expect(row.locator("td").last()).toHaveText("0.0%");
    await expect(row).toHaveAttribute("data-edge", "none"); // unranked side: no cue
    await expect(row.getByTitle("Not ranked")).toHaveCount(2);
  });

  test("rows carry an accent edge bar on the favored side, with a summary and legend", async ({ page }) => {
    await page.goto("/matchup/1");
    await expect(page.getByTestId("edge-legend")).toBeVisible();
    await expect(page.getByTestId("edge-summary").first()).toContainText(/Edge: .* offense \d+ · .* defense \d+ · even \d+/);
    const strong = page.locator("tr[data-strength='strong']").first();
    const slight = page.locator("tr[data-strength='slight']").first();
    expect(await page.locator("tr[data-edge='offense'], tr[data-edge='defense']").count()).toBeGreaterThan(2);
    for (const rowLoc of [strong, slight]) {
      if (await rowLoc.count()) {
        const side = await rowLoc.getAttribute("data-edge");
        const cell = side === "offense" ? rowLoc.locator("td").first() : rowLoc.locator("td").last();
        await expect(cell).toHaveClass(/border-(l|r)-\[3px\]/);
        await expect(cell).toHaveClass(/border-accent/);
        await expect(rowLoc.locator(".sr-only")).toContainText(/Edge: /);
      }
    }
    // Even rows draw no bar.
    const even = page.locator("tr[data-edge='even']").first();
    if (await even.count()) await expect(even.locator("td").first()).toHaveClass(/border-transparent/);
  });

  test("tables sit side by side on desktop with aligned rows, and stack on a phone", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/matchup/1");
    const tables = page.getByRole("table");
    const a = await tables.nth(0).boundingBox();
    const b = await tables.nth(1).boundingBox();
    expect(a && b).toBeTruthy();
    expect(Math.abs(a!.y - b!.y)).toBeLessThan(2); // same top: side by side
    expect(b!.x).toBeGreaterThan(a!.x + a!.width - 2);
    expect(a!.width).toBeGreaterThan(430); // roomy enough for five columns
    // Rows line up across the two tables (fixed row heights).
    const ra = await tables.nth(0).locator("tr[data-edge]").evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().top)));
    const rb = await tables.nth(1).locator("tr[data-edge]").evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().top)));
    expect(ra).toEqual(rb);

    await page.setViewportSize({ width: 390, height: 900 });
    await page.goto("/matchup/1");
    const pa = await page.getByRole("table").nth(0).boundingBox();
    const pb = await page.getByRole("table").nth(1).boundingBox();
    expect(pb!.y).toBeGreaterThan(pa!.y + pa!.height - 2); // stacked
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });

  test("top of the page: records, venue, rating labels, edges, a real Updated time, no duplicate system name", async ({ page }) => {
    await page.goto("/matchup/1");
    const away = page.locator("[data-side='away']");
    await expect(away).toContainText(/Away · \d+-\d+/);
    await expect(page.locator("[data-side='home']")).toContainText(/Home · \d+-\d+/);
    await expect(away).toContainText(/V5 rank #\d+/);
    await expect(away).toContainText(/Rating [+−]\d\.\d{2}/);
    await expect(away).toContainText(/Off #\d+ · Def #\d+/);
    const facts = page.getByTestId("game-facts");
    await expect(facts).toContainText(/, [A-Z]{2}|Neutral site/); // venue
    await expect(facts).not.toContainText("Blitzkrieg");
    // The header's Updated time is the forecast update, not the kickoff.
    const header = await page.locator("header").innerText();
    expect(header).toMatch(/Updated Sep (29|30)/);
    await expect(page.locator("#matchup-header")).toHaveText(/ at /);
    await expect(page.locator("#matchup-header")).toHaveClass(/sr-only/);
    // Forecast box carries the model edge notes like the Picks cards.
    await expect(page.getByText("Forecast & Lines")).toBeVisible();
    // The model bet names the side without the word "Lean".
    const bet = page.getByText("Model Bet:").locator("xpath=following-sibling::div[1]");
    await expect(bet).not.toContainText("Lean");
    // Explanations and legends live below the tables, not above them.
    const lastTable = await page.getByRole("table").last().boundingBox();
    const notes = await page.getByTestId("matchup-notes").boundingBox();
    expect(notes!.y).toBeGreaterThan(lastTable!.y + lastTable!.height - 2);
    const firstTable = await page.getByRole("table").first().boundingBox();
    const legend = await page.getByTestId("edge-legend").boundingBox();
    expect(legend!.y).toBeGreaterThan(firstTable!.y);
    await expect(page.locator("[title='Model minus market']").first()).toBeVisible();
    await expect(page).toHaveTitle(/ at .* · Matchup/);
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
    // The slate fixture ids are the ones the matchup fixtures know, so click through there.
    await page.goto("/");
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

  test("slate cards also carry the Matchup button", async ({ page }) => {
    await page.goto("/");
    expect(await page.getByTestId("matchup-link").count()).toBeGreaterThan(3);
    await page.goto("/results");
    expect(await page.getByTestId("matchup-link").count()).toBeGreaterThan(3);
  });
});
