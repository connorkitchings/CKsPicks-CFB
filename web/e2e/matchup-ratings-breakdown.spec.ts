import { expect, test, type Page } from "@playwright/test";
import { gotoHydrated, openDetails, openUnitStats, ratingBreakdownDetails, selectOffense, unitStats } from "./helpers";

const section = (page: Page) => page.getByRole("region", { name: "How the ratings are built" });
const cards = (page: Page) => section(page).getByRole("article");

/** Loads a matchup and expands the collapsed full rating breakdown (it shows the two units of the selected offense). */
async function openBreakdown(page: Page, path = "/matchup/1") {
  await gotoHydrated(page, path);
  await openDetails(ratingBreakdownDetails(page));
}

test.describe("matchup rating breakdown (fixture mode)", () => {
  test("explains the build and shows four unit cards with a summary line each", async ({ page }) => {
    await openBreakdown(page);
    await openUnitStats(page);
    const region = section(page);
    await expect(region).toContainText("points scored (or allowed) per possession, adjusted for the strength of opponents");
    await expect(region).toContainText("do not feed the rating");
    await expect(region).toContainText("0 is an average team and higher is better, including defense");
    await expect(region.getByRole("link", { name: "prior" })).toHaveAttribute("href", "/model/method#prior");
    await expect(region.getByRole("link", { name: "updates" })).toHaveAttribute("href", "/model/method#updates");
    // The selected offense shows its two units (away offense and home defense); the other side shows the other two.
    for (const side of ["away", "home"] as const) {
      await selectOffense(page, side);
      await expect(cards(page)).toHaveCount(2);
      await expect(cards(page).nth(0).getByRole("heading")).toContainText(/ offense$/i);
      await expect(cards(page).nth(1).getByRole("heading")).toContainText(/ defense$/i);
    }
    await selectOffense(page, "away");
    for (const card of await cards(page).all()) {
      await expect(card).toContainText(/(Scores|Allows) \d\.\d{2} points per possession\./);
      await expect(card).toContainText(/Rating [+-]\d\.\d{2} \(#\d+\), (above |below )?average/);
      await expect(card).toContainText(/\d+% of this rating is the preseason estimate; the rest is this season's \d+ games? \(\d+ possessions?\)/);
    }
    // Placed after the full unit statistics.
    const stats = (await unitStats(page).boundingBox())!;
    const box = (await region.boundingBox())!;
    expect(box.y).toBeGreaterThan(stats.y + stats.height - 2);
  });

  test("defense says allowed; the season-to-date table ends at the headline numbers", async ({ page }) => {
    await openBreakdown(page);
    const defense = cards(page).filter({ has: page.getByRole("heading", { name: / defense$/ }) }).first();
    await expect(defense).toContainText("Allows");

    const offense = cards(page).first();
    const disclosure = offense.locator("details").first();
    await expect(disclosure).not.toHaveAttribute("open", "");
    await expect(offense.getByRole("table")).toBeHidden();
    await disclosure.locator("summary").first().click();
    await expect(offense).toContainText("Season to date after each week.");
    await expect(offense).toContainText("re-score every past game with today's opponent ratings");
    await expect(offense).toContainText(/The rating blends the season-to-date adjusted number .* of this rating\./);
    const table = offense.getByRole("table", { name: /season-to-date/ });
    await expect(table).toBeVisible();
    await expect(table.locator("thead")).toContainText("Through week");
    await expect(table.locator("thead th")).toHaveCount(3);
    const body = table.locator("tbody tr");
    await expect(body.first().locator("th")).toContainText(/^Wk \d+\s*\+ \S/);
    const last = body.last().locator("td");
    const headline = (await offense.textContent())!.match(/Scores (\d\.\d{2}) points per possession\. .* as (\d\.\d{2})\./);
    expect(headline).not.toBeNull();
    if (headline) {
      expect((await last.nth(0).textContent())!.replace("†", "")).toBe(headline[1]);
      expect((await last.nth(1).textContent())!.replace("†", "")).toBe(headline[2]);
    }
    await expect(table.getByText("†").first()).toBeVisible();
    await expect(offense).toContainText("No opponent context was available");
    await expect(offense).toContainText("Not used by the rating");
    await expect(offense).toContainText("scoring could not be attributed to a possession");
    await expect(offense).toContainText("1 game not used");
  });

  test("the audit detail starts closed and its per-game table sums to the rating", async ({ page }) => {
    await openBreakdown(page);
    const offense = cards(page).first();
    await offense.locator("summary").first().click();
    const audit = offense.locator("details details");
    await expect(audit).not.toHaveAttribute("open", "");
    await expect(audit.locator("summary")).toContainText("Each game's effect on the rating");
    await expect(offense.getByRole("table")).toHaveCount(1);
    await expect(audit.getByRole("table")).toBeHidden();
    await audit.locator("summary").click();
    const table = audit.getByRole("table");
    await expect(table).toBeVisible();
    const body = table.locator("tbody tr");
    await expect(body.last()).toContainText("Preseason estimate");
    await expect(table.locator("tfoot")).toContainText("Rating");
    const contributions = await body.locator("td:last-child").allTextContents();
    const total = contributions.reduce((sum, text) => sum + Number(text), 0);
    const footer = (await table.locator("tfoot td").last().textContent())!;
    expect(Math.abs(total - Number(footer))).toBeLessThan(0.006);
    expect(await table.locator("tbody tr:last-child").evaluate((row) => row.nextElementSibling)).toBeNull();
    await expect(table.getByText("†")).toHaveCount(1);
    await expect(table.locator("tbody th").first()).toContainText(/poss\./);
  });

  test("lineage problems and unpublished stats hide the section", async ({ page }) => {
    for (const id of [987655, 987656]) {
      await page.goto(`/matchup/${id}`);
      await expect(section(page)).toHaveCount(0);
      await expect(page.getByText("How the ratings are built")).toHaveCount(0);
      await expect(page.getByText("Rating evidence")).toHaveCount(0);
      await expect(ratingBreakdownDetails(page)).toHaveCount(0);
    }
  });

  test("a rating that disagrees with its stored components makes only that card unavailable", async ({ page }) => {
    await openBreakdown(page, "/matchup/987657");
    let unavailableCards = 0;
    let readyCards = 0;
    for (const side of ["away", "home"] as const) {
      await selectOffense(page, side);
      await expect(cards(page)).toHaveCount(2);
      const broken = cards(page).filter({ hasText: "Breakdown unavailable" });
      unavailableCards += await broken.count();
      readyCards += await cards(page).filter({ hasText: "points per possession" }).count();
      for (const card of await broken.all()) await expect(card).not.toContainText(/\d\.\d{2}/);
    }
    expect(unavailableCards).toBe(1);
    expect(readyCards).toBe(3);
  });

  test("preseason-only units say so and have no tables", async ({ page }) => {
    await openBreakdown(page, "/matchup/987658");
    for (const side of ["away", "home"] as const) {
      await selectOffense(page, side);
      await expect(cards(page)).toHaveCount(2);
      for (const card of await cards(page).all()) {
        await expect(card).toContainText("No completed games yet · rating is the preseason estimate (100%)");
      }
    }
    await expect(section(page).getByRole("table")).toHaveCount(0);
    await expect(section(page).locator("details")).toHaveCount(0);
  });
});

for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 568 }]) {
  test.describe(`rating breakdown on a ${viewport.width}px phone`, () => {
    test.use({ viewport, hasTouch: true });

    test("opened disclosures do not scroll the page sideways and summaries are touch-sized", async ({ page }) => {
      await openBreakdown(page);
      for (const side of ["away", "home"] as const) {
        await selectOffense(page, side);
        const outer = section(page).locator("article:visible > details > summary");
        await expect(outer).toHaveCount(2);
        for (const summary of await outer.all()) {
          expect((await summary.boundingBox())!.height).toBeGreaterThanOrEqual(44);
          await summary.click();
        }
        const nested = section(page).locator("article:visible details details > summary");
        await expect(nested).toHaveCount(2);
        for (const summary of await nested.all()) {
          expect((await summary.boundingBox())!.height).toBeGreaterThanOrEqual(44);
          await summary.click();
        }
        await expect(section(page).getByRole("table")).toHaveCount(4);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        // Every column, including the effect-on-rating values, must fit without an inner horizontal scroll.
        for (const table of await section(page).getByRole("table").all()) {
          const [scroll, client] = await table.evaluate((el) => [el.parentElement!.scrollWidth, el.parentElement!.clientWidth]);
          expect(scroll, `table ${await table.getAttribute("aria-label")}`).toBeLessThanOrEqual(client);
        }
      }
    });
  });
}
