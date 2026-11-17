import { expect, test } from "@playwright/test";
import { gotoHydrated, selectOffense } from "./helpers";

test.describe("Key factors tale of the tape", () => {
  test("renders five rows, the honest title and the turnover note, with no aggregate verdict", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    const card = page.getByTestId("tale-of-the-tape");
    await expect(card.getByRole("heading", { name: "Key factors" })).toBeVisible();
    await expect(card).toContainText("Turnovers are not included.");
    await expect(card).not.toContainText("Five Factors");
    await expect(card.getByTestId("tape-row")).toHaveCount(5);
    await expect(card).toContainText("20+ yard play rate across all plays");
    // The redesign removed the aggregate winner verdict; rows only state which unit ranks higher.
    await expect(card.getByTestId("tape-verdict")).toHaveCount(0);
    await expect(card).not.toContainText(/Tape Verdict/);
  });

  test("the share section follows the comparison, notes and full statistics, with Key factors after the notes", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    const summary = page.getByTestId("matchup-summary-header");
    await expect(summary.getByRole("heading", { name: "Share matchup", exact: true })).toBeVisible();
    await expect(summary.getByTestId("share-controls")).toHaveCount(1);
    await expect(page.getByTestId("game-facts").getByTestId("share-controls")).toHaveCount(0);
    await expect(page.getByTestId("tale-of-the-tape").getByTestId("share-controls")).toHaveCount(0);
    const order = await page.locator('[data-testid="matchup-summary-header"], table[aria-label*=" Offense vs "], [data-testid="matchup-notes"], [data-testid="tale-of-the-tape"]').evaluateAll(
      (elements) => elements.map((element) => element.getAttribute("data-testid") ?? element.tagName.toLowerCase()),
    );
    expect(order).toEqual(["matchup-notes", "tale-of-the-tape", "table", "matchup-summary-header"]);
  });

  test("the single offense selector switches the clash; the card has no selector of its own", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    const card = page.getByTestId("tale-of-the-tape");
    await expect(card.getByRole("group")).toHaveCount(0);
    await expect(page.getByRole("group", { name: "Offense comparison" })).toHaveCount(1);
    const awayRows = await card.getByTestId("tape-row").allInnerTexts();
    const awayHeader = await card.locator("div.border-b").nth(1).innerText();
    await selectOffense(page, "home");
    // The rows are recomputed for the other clash (the other team's offense against the first team's defense).
    await expect(async () => {
      expect(await card.locator("div.border-b").nth(1).innerText()).not.toBe(awayHeader);
      expect(await card.getByTestId("tape-row").allInnerTexts()).not.toEqual(awayRows);
    }).toPass({ timeout: 5_000 });
    await expect(card.getByTestId("tape-row")).toHaveCount(5);
  });

  test("is absent when lineage mismatches", async ({ page }) => {
    await page.goto("/matchup/987656");
    await expect(page.getByRole("status", { name: "Team stats" })).toBeVisible();
    await expect(page.getByTestId("tale-of-the-tape")).toHaveCount(0);
  });

  test("is absent when team stats are unavailable", async ({ page }) => {
    await page.goto("/matchup/987655");
    await expect(page.getByRole("region", { name: "Team stats" })).toContainText("temporarily unavailable");
    await expect(page.getByTestId("tale-of-the-tape")).toHaveCount(0);
    await expect(page.getByTestId("share-download")).toBeDisabled();
  });

  test.describe("at 320px", () => {
    test.use({ viewport: { width: 320, height: 568 }, hasTouch: true });

    test("has no horizontal overflow", async ({ page }) => {
      await gotoHydrated(page, "/matchup/1");
      const card = page.getByTestId("tale-of-the-tape");
      await expect(card).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      const inner = await card.evaluate((el) => el.scrollWidth - el.clientWidth);
      expect(inner).toBeLessThanOrEqual(0);
    });
  });
});
