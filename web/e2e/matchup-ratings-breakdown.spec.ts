import { expect, test, type Page } from "@playwright/test";
import { gotoHydrated } from "./helpers";

const section = (page: Page) => page.getByRole("region", { name: "How the ratings are built" });
const cards = (page: Page) => section(page).getByRole("article");

test.describe("matchup rating breakdown (fixture mode)", () => {
  test("explains the build and shows four unit cards with a summary line each", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    const region = section(page);
    await expect(region).toContainText("Ratings use opponent-adjusted scoring per possession plus a shrinking preseason prior.");
    await expect(region).toContainText("The tables show raw statistics and are not combined to form the rating.");
    await expect(region).toContainText("not points");
    await expect(region.getByRole("link", { name: "prior" })).toHaveAttribute("href", "/model/method#prior");
    await expect(region.getByRole("link", { name: "updates" })).toHaveAttribute("href", "/model/method#updates");
    await expect(cards(page)).toHaveCount(4);
    for (const card of await cards(page).all()) {
      await expect(card).toContainText(/Raw PPP( allowed)? \d\.\d{2} → adjusted \d\.\d{2} → rating [+-]\d\.\d{2} \(#\d+\)/);
      await expect(card).toContainText(/Prior \d+% · \d+ games?, \d+ possessions/);
    }
    // Placed after the team stats.
    const stats = (await page.getByRole("region", { name: "Team stats", exact: true }).boundingBox())!;
    const box = (await region.boundingBox())!;
    expect(box.y).toBeGreaterThan(stats.y + stats.height - 2);
  });

  test("defense says allowed; the game table opens with the prior last and a footer equal to the rating", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    const defense = cards(page).filter({ hasText: "defense" }).first();
    await expect(defense).toContainText("PPP allowed");

    const offense = cards(page).first();
    const disclosure = offense.locator("details");
    await expect(disclosure).not.toHaveAttribute("open", "");
    await expect(offense.getByRole("table")).toBeHidden();
    await disclosure.locator("summary").click();
    const table = offense.getByRole("table");
    await expect(table).toBeVisible();
    const body = table.locator("tbody tr");
    await expect(body.last()).toContainText("Preseason prior");
    await expect(body).toHaveCount(4);
    const contributions = await body.locator("td:last-child").allTextContents();
    const total = contributions.reduce((sum, text) => sum + Number(text), 0);
    const footer = (await table.locator("tfoot td").last().textContent())!;
    expect(Math.abs(total - Number(footer))).toBeLessThan(0.006);
    await expect(table.locator("tfoot")).toContainText("Rating");
    await expect(table.getByText("†")).toHaveCount(1);
    await expect(offense).toContainText("No opponent context was available");
    await expect(offense).toContainText("Not used by the rating");
    await expect(offense).toContainText("scoring could not be attributed to a possession");
    await expect(offense).toContainText("1 not used");
  });

  test("lineage problems and unpublished stats hide the section", async ({ page }) => {
    for (const id of [987655, 987656]) {
      await page.goto(`/matchup/${id}`);
      await expect(section(page)).toHaveCount(0);
    }
  });

  test("a rating that disagrees with its stored components makes only that card unavailable", async ({ page }) => {
    await page.goto("/matchup/987657");
    await expect(cards(page)).toHaveCount(4);
    const unavailable = section(page).getByRole("status");
    await expect(unavailable).toHaveCount(1);
    await expect(unavailable).toContainText("Breakdown unavailable for this rating");
    await expect(cards(page).filter({ hasText: "Breakdown unavailable" })).not.toContainText(/\d\.\d{2}/);
    await expect(cards(page).filter({ hasText: "Raw PPP" })).toHaveCount(3);
  });

  test("preseason-only units say so and have no tables", async ({ page }) => {
    await page.goto("/matchup/987658");
    await expect(cards(page)).toHaveCount(4);
    for (const card of await cards(page).all()) {
      await expect(card).toContainText("No completed games yet · rating is the preseason prior (100%)");
    }
    await expect(section(page).getByRole("table")).toHaveCount(0);
    await expect(section(page).locator("details")).toHaveCount(0);
  });
});

for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 568 }]) {
  test.describe(`rating breakdown on a ${viewport.width}px phone`, () => {
    test.use({ viewport, hasTouch: true });

    test("opened disclosures do not scroll the page sideways and summaries are touch-sized", async ({ page }) => {
      await gotoHydrated(page, "/matchup/1");
      const summaries = section(page).locator("summary");
      await expect(summaries).toHaveCount(4);
      for (const summary of await summaries.all()) {
        expect((await summary.boundingBox())!.height).toBeGreaterThanOrEqual(44);
        await summary.click();
      }
      await expect(section(page).getByRole("table")).toHaveCount(4);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      // Every column, including the contribution values, must fit without an inner horizontal scroll.
      for (const table of await section(page).getByRole("table").all()) {
        expect(await table.evaluate((el) => el.parentElement!.scrollWidth <= el.parentElement!.clientWidth)).toBe(true);
      }
    });
  });
}
