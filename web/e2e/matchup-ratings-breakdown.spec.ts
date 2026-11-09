import { expect, test, type Page } from "@playwright/test";
import { gotoHydrated } from "./helpers";

const section = (page: Page) => page.getByRole("region", { name: "How the ratings are built" });
const cards = (page: Page) => section(page).getByRole("article");

test.describe("matchup rating breakdown (fixture mode)", () => {
  test("explains the build and shows four unit cards with a summary line each", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    const region = section(page);
    await expect(region).toContainText("points scored (or allowed) per possession, adjusted for the strength of opponents");
    await expect(region).toContainText("do not feed the rating");
    await expect(region).toContainText("0 is an average team and higher is better, including defense");
    await expect(region.getByRole("link", { name: "prior" })).toHaveAttribute("href", "/model/method#prior");
    await expect(region.getByRole("link", { name: "updates" })).toHaveAttribute("href", "/model/method#updates");
    await expect(cards(page)).toHaveCount(4);
    for (const card of await cards(page).all()) {
      await expect(card).toContainText(/(Scores|Allows) \d\.\d{2} points per possession\./);
      await expect(card).toContainText(/Rating [+-]\d\.\d{2} \(#\d+\), (above |below )?average/);
      await expect(card).toContainText(/\d+% of this rating is the preseason estimate; the rest is this season's \d+ games? \(\d+ possessions?\)/);
    }
    // Placed after the team stats.
    const stats = (await page.getByRole("region", { name: "Team stats", exact: true }).boundingBox())!;
    const box = (await region.boundingBox())!;
    expect(box.y).toBeGreaterThan(stats.y + stats.height - 2);
  });

  test("defense says allowed; the season-to-date table ends at the headline numbers", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
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
    await gotoHydrated(page, "/matchup/1");
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
    }
  });

  test("a rating that disagrees with its stored components makes only that card unavailable", async ({ page }) => {
    await page.goto("/matchup/987657");
    await expect(cards(page)).toHaveCount(4);
    const unavailable = section(page).getByRole("status");
    await expect(unavailable).toHaveCount(1);
    await expect(unavailable).toContainText("Breakdown unavailable for this rating");
    await expect(cards(page).filter({ hasText: "Breakdown unavailable" })).not.toContainText(/\d\.\d{2}/);
    await expect(cards(page).filter({ hasText: "points per possession" })).toHaveCount(3);
  });

  test("preseason-only units say so and have no tables", async ({ page }) => {
    await page.goto("/matchup/987658");
    await expect(cards(page)).toHaveCount(4);
    for (const card of await cards(page).all()) {
      await expect(card).toContainText("No completed games yet · rating is the preseason estimate (100%)");
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
      // DOM order is outer, nested, outer, nested... for the four ready units.
      const summaries = section(page).locator("summary");
      await expect(summaries).toHaveCount(8);
      for (const parity of [0, 1]) {
        for (const summary of (await summaries.all()).filter((_, index) => index % 2 === parity)) {
          expect((await summary.boundingBox())!.height).toBeGreaterThanOrEqual(44);
          await summary.click();
        }
      }
      await expect(section(page).getByRole("table")).toHaveCount(8);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      // Every column, including the effect-on-rating values, must fit without an inner horizontal scroll.
      for (const table of await section(page).getByRole("table").all()) {
        const [scroll, client] = await table.evaluate((el) => [el.parentElement!.scrollWidth, el.parentElement!.clientWidth]);
        expect(scroll, `table ${await table.getAttribute("aria-label")}`).toBeLessThanOrEqual(client);
      }
    });
  });
}
