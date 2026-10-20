import { expect, test, type Page } from "@playwright/test";

const audit = (page: Page) => page.getByRole("region", { name: "Graded picks audit", exact: true });
const target = (page: Page) => page.getByRole("group", { name: "Pick target" });

/** Matches the `sm` breakpoint, below which ResponsiveDisclosure collapses. */
const isPhone = (page: Page) => (page.viewportSize()?.width ?? 1280) < 640;

async function openAudit(page: Page) {
  await audit(page).locator(":scope > details > summary").click();
  await expect(page.getByLabel("Audit week")).toBeVisible();
}

test.describe("performance page is accuracy-only", () => {
  test("leads with separate records, keeps the audit collapsed and diagnostics collapsed on phones", async ({ page }) => {
    await page.goto("/performance");
    await expect(page.getByRole("heading", { name: "Season record & performance" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "2026 V5 cumulative record" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Designated prospective V5 performance" })).toHaveCount(0);

    const summary = page.getByRole("region", { name: "Forecast accuracy summary", exact: true });
    await expect(summary.getByRole("button", { name: /Spread/ })).toContainText("1–1–1");
    await expect(summary.getByRole("button", { name: /Totals/ })).toContainText("1–1–1");
    await expect(summary.getByText("50.0%", { exact: true })).toHaveCount(2);
    await expect(page.locator("details[open]")).toHaveCount(0);
    await expect(page.getByLabel("Audit week")).toBeHidden();

    // Phones collapse diagnostics behind the summary; wider screens show them inline.
    if (isPhone(page)) await page.getByText("Season-wide forecast diagnostics", { exact: true }).filter({ visible: true }).click();
    const accuracy = page.getByRole("region", { name: "Forecast accuracy", exact: true }).filter({ visible: true });
    await expect(accuracy.getByText("Spread MAE", { exact: true })).toBeVisible();
    await expect(accuracy.getByText("Total 95% interval", { exact: true })).toBeVisible();
    await expect(accuracy.getByText("4.5 pts", { exact: true })).toBeVisible();
    await target(page).getByRole("button", { name: "Totals", exact: true }).click();
    await expect(accuracy.getByText("4.5 pts", { exact: true })).toBeVisible();

    for (const banned of [/\bROI\b/, /profit/i, /\bunits?\b/i, /net return/i, /closing line/i, /-110/, /\d\.\d+u\b/]) {
      await expect(page.locator("body").getByText(banned)).toHaveCount(0);
    }
  });

  test("target filter narrows weekly records and preserves an empty selected audit week", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/performance");
    await openAudit(page);
    await expect(page.getByLabel("Audit week")).toHaveValue("2");
    await target(page).getByRole("button", { name: "Totals", exact: true }).click();
    await expect(page.getByRole("columnheader", { name: "Total (W-L-P)" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Spread (W-L-P)" })).toHaveCount(0);
    await expect(page.getByLabel("Audit week")).toHaveValue("2");
    await expect(audit(page).getByRole("status")).toHaveText("No graded totals in Week 2.");
    await expect(audit(page).getByTestId("audit-game")).toHaveCount(0);

    await page.getByLabel("Audit week").selectOption("1");
    await expect(audit(page).getByTestId("audit-game")).toHaveCount(2);
    const game = audit(page).locator('[data-game-id="401000002"]');
    await game.locator("summary").click();
    await expect(game.getByText("Total · captured line 47.0", { exact: true })).toBeVisible();
    await expect(game.getByText(/Spread · captured line/)).toHaveCount(0);
    await expect(game.getByText("Forecast 50.0 · over · push", { exact: true })).toBeVisible();
    await target(page).getByRole("button", { name: "Spreads", exact: true }).click();
    await expect(page.getByLabel("Audit week")).toHaveValue("1");
    await expect(game.getByText("Spread · captured line Alabama -3.5", { exact: true })).toBeVisible();
    // The forecast is a +5.0 home margin; it reads as the home spread, signed like the line.
    await expect(game.getByText("Forecast Alabama -5.0 · home · loss", { exact: true })).toBeVisible();
  });

  test("every graded game remains reachable by week and exposes preserved audit facts", async ({ page }) => {
    await page.goto("/performance");
    await openAudit(page);
    const expected: Record<string, number[]> = {
      "0": [401000001],
      "1": [401000002, 401000003],
      "2": [401000004],
    };
    for (const [week, ids] of Object.entries(expected)) {
      await page.getByLabel("Audit week").selectOption(week);
      const games = audit(page).getByTestId("audit-game");
      await expect(games).toHaveCount(ids.length);
      expect(await games.evaluateAll((nodes) => nodes.map((node) => Number(node.getAttribute("data-game-id"))))).toEqual(ids);
      for (const id of ids) {
        const game = audit(page).locator(`[data-game-id="${id}"]`);
        await game.locator("summary").click();
        await expect(game.getByText(/Original run:/)).toBeVisible();
        await expect(game.getByText(/Forecast /).first()).toBeVisible();
        await expect(game.getByText(/Price:/).first()).toBeVisible();
        await expect(game.getByRole("link", { name: "Matchup" })).toHaveAttribute("href", `/matchup/${id}`);
      }
    }
    const latest = audit(page).locator('[data-game-id="401000004"]');
    await expect(latest.getByText("Price: unavailable", { exact: true })).toBeVisible();
    await expect(latest.getByText(/Freeze evidence SHA-256:/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(await page.evaluate(() => innerWidth));
  });

  test("the selected audit week and expanded audit remain stable across target changes", async ({ page }) => {
    await page.goto("/performance");
    await openAudit(page);
    await page.getByLabel("Audit week").selectOption("0");
    await target(page).getByRole("button", { name: "Totals", exact: true }).click();
    await expect(page.getByLabel("Audit week")).toBeVisible();
    await expect(page.getByLabel("Audit week")).toHaveValue("0");
    await target(page).getByRole("button", { name: "All Picks", exact: true }).click();
    await expect(page.getByLabel("Audit week")).toHaveValue("0");
    await page.reload();
    await openAudit(page);
    await expect(page.getByLabel("Audit week")).toHaveValue("2");
  });

  for (const width of [320, 390, 640, 1280]) {
    test(`summary, expanded provenance and weekly links stay usable at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/performance");
      await expect(page.getByRole("heading", { name: "Season record & performance" })).toBeVisible();
      const weekly = page.getByRole("region", { name: "Weekly accuracy breakdown" });
      const link = weekly.getByRole("link", { name: "Week 0", exact: true }).filter({ visible: true });
      await expect(link).toHaveAttribute("href", "/results?week=0");
      const box = await link.boundingBox();
      // Phone rows are 44px touch targets; the desktop table link stays compact.
      if (isPhone(page)) expect(box!.height).toBeGreaterThanOrEqual(44);
      else expect(box!.height).toBeLessThanOrEqual(40);
      await openAudit(page);
      await audit(page).getByTestId("audit-game").locator("summary").click();
      await expect(audit(page).getByText(/Freeze evidence SHA-256:/)).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    });
  }
});
