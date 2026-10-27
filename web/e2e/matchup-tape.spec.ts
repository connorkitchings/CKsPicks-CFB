import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

test.describe("Key factors tale of the tape", () => {
  test("renders five rows, the honest title and the turnover note", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    const card = page.getByTestId("tale-of-the-tape");
    await expect(card.getByRole("heading", { name: "Key factors" })).toBeVisible();
    await expect(card).toContainText("Turnovers are not included yet");
    await expect(card).not.toContainText("Five Factors");
    await expect(card.getByTestId("tape-row")).toHaveCount(5);
    await expect(card).toContainText("20+ yard play rate across all plays");
    await expect(card.getByTestId("tape-verdict")).toContainText(/Tape Verdict:/);
  });

  test("summary exports sit above the unit tables, with Key factors after their notes", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    const summary = page.getByTestId("matchup-summary-header");
    await expect(summary.getByRole("heading", { name: "Matchup summary", exact: true })).toBeVisible();
    await expect(summary.getByTestId("share-controls")).toHaveCount(1);
    await expect(page.getByTestId("game-facts").getByTestId("share-controls")).toHaveCount(0);
    await expect(page.getByTestId("tale-of-the-tape").getByTestId("share-controls")).toHaveCount(0);
    const order = await page.locator('[data-testid="matchup-summary-header"], table, [data-testid="matchup-notes"], [data-testid="tale-of-the-tape"]').evaluateAll(
      (elements) => elements.map((element) => element.getAttribute("data-testid") ?? element.tagName.toLowerCase()),
    );
    expect(order).toEqual(["matchup-summary-header", "table", "table", "matchup-notes", "tale-of-the-tape"]);
  });

  test("the segmented control switches the clash and its verdict", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    const card = page.getByTestId("tale-of-the-tape");
    const verdict = card.getByTestId("tape-verdict");
    const radios = card.getByRole("group", { name: "Unit matchup clash" }).getByRole("button");
    await expect(radios).toHaveCount(2);
    const before = await verdict.innerText();
    await radios.nth(1).click();
    await expect(radios.nth(1)).toHaveAttribute("aria-pressed", "true");
    // The verdict is recomputed for the other clash.
    await expect(async () => {
      expect(await verdict.innerText()).not.toBe(before);
    }).toPass({ timeout: 5_000 });
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
