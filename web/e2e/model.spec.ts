import { expect, test, type Page } from "@playwright/test";
import { gotoHydrated, openTable } from "./helpers";


/** Matches the `sm` breakpoint, below which ResponsiveDisclosure collapses. */
const isPhone = (page: Page) => (page.viewportSize()?.width ?? 1280) < 640;

async function expectUniqueIds(page: Page) {
  const ids = await page.locator("[id]").evaluateAll(nodes => nodes.map(node => node.id));
  expect(ids.filter((id, i) => ids.indexOf(id) !== i)).toEqual([]);
}

test.describe("model section", () => {
  test("record page marks its tab current and has unique ids", async ({ page }) => {
    await page.goto("/model");
    const tabs = page.getByRole("navigation", { name: "Model sections" });
    await expect(tabs.getByRole("link", { name: "Record" })).toHaveAttribute("aria-current", "page");
    await expect(tabs.getByRole("link", { name: "How it works" })).toHaveAttribute("href", "/model/method");
    await expect(tabs.getByRole("link", { name: "How it works" })).not.toHaveAttribute("aria-current", "page");
    await expectUniqueIds(page);
  });

  test("method page links back, keeps the elite-reference anchor and has unique ids", async ({ page }) => {
    await page.goto("/model/method");
    await expect(page.getByRole("heading", { level: 1, name: "How the model works" })).toBeVisible();
    const tabs = page.getByRole("navigation", { name: "Model sections" });
    await expect(tabs.getByRole("link", { name: "How it works" })).toHaveAttribute("aria-current", "page");
    for (const link of await tabs.getByRole("link").all()) {
      expect((await link.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
    await expect(page.locator("#elite-reference")).toHaveCount(1);
    await expect(page.getByRole("heading", { name: "Elite reference" })).toBeVisible();
    await expectUniqueIds(page);
    await tabs.getByRole("link", { name: "Record" }).click();
    await expect(page).toHaveURL(/\/model$/);
  });

  test("method page fits the viewport at 320px", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.goto("/model/method#elite-reference");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  });
});

test.describe("model page is accuracy-only", () => {
  test("leads with separate records, keeps diagnostics collapsed on phones", async ({ page }) => {
    await page.goto("/model");
    await expect(page.getByRole("heading", { name: "Season record & performance" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "2026 V5 cumulative record" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Designated prospective V5 performance" })).toHaveCount(0);

    const summary = page.getByRole("region", { name: "Forecast accuracy summary", exact: true });
    await expect(summary.locator("[data-card]").filter({ hasText: "Spread" })).toContainText("3–3–2");
    await expect(summary.locator("[data-card]").filter({ hasText: "Totals" })).toContainText("3–3–2");
    await expect(summary.getByText("50.0%", { exact: true })).toHaveCount(2);
    await expect(summary.getByText("-2.4 pp vs 52.4% break-even", { exact: true })).toHaveCount(2);
    await expect(page.locator("details[open]")).toHaveCount(0);
    await expect(page.getByText("Graded picks audit")).toHaveCount(0);

    // Phones collapse diagnostics behind the summary; wider screens show them inline.
    if (isPhone(page)) await page.getByText("Season-wide forecast diagnostics", { exact: true }).filter({ visible: true }).click();
    const accuracy = page.getByRole("region", { name: "Forecast accuracy", exact: true }).filter({ visible: true });
    await expect(accuracy.getByText("Spread average miss", { exact: true })).toBeVisible();
    await expect(accuracy.getByText(/Average miss, every game with a final score \(9 games\)/)).toBeVisible();
    await expect(accuracy.getByText("Total 95% interval", { exact: true })).toBeVisible();
    await expect(accuracy.getByText("4.5 pts", { exact: true })).toBeVisible();

    for (const banned of [/\bROI\b/, /profit/i, /\bunits?\b/i, /net return/i, /closing line/i, /-110/, /\d\.\d+u\b/]) {
      await expect(page.locator("body").getByText(banned)).toHaveCount(0);
    }
  });

  test("compares the model with the retained pre-kickoff line on the same games", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/model");
    // Hand-derived in src/test/fixtures/performance-mobile.ts.
    const spread = page.getByTestId("market-spread");
    await expect(spread).toContainText("Model 10.9 pts · Betting line 8.6 pts");
    await expect(spread).toContainText("Model closer in 2 of 6 games");
    await expect(spread).toContainText("Betting line closer in 4 · Even: 1");
    await expect(spread).toContainText("Model 5.1 pts toward the away team; betting line 4.8 pts toward the away team");
    await expect(spread).toContainText("Model 1 · Betting line 0");
    await expect(spread).toContainText("Compared on 7 games with a retained pre-kickoff line");
    await expect(spread).toContainText("Left out: 1 graded against a historical line and 0 with an unknown line source.");
    const totals = page.getByTestId("market-total");
    await expect(totals).toContainText("Model 5.1 pts · Betting line 3.8 pts");
    await expect(totals).toContainText("Model closer in 3 of 7 games");
    await expect(totals).toContainText("Betting line closer in 4 · Even: 0");
    await expect(totals).toContainText("Model 3.4 pts high; betting line 0.5 pts high");
    await expect(totals).toContainText("Compared on 7 games");
    await expect(page.getByTestId("record-caveat")).toContainText("it is not a betting result");
    await expect(page.getByTestId("record-caveat")).toContainText("within normal luck of break-even");
  });

  test("the season trend has an accessible name and a table view", async ({ page }) => {
    await gotoHydrated(page, "/model");
    const chart = page.getByRole("img", { name: /win rate through Week 3: 50\.0% season to date/ });
    await expect(chart).toHaveCount(2);
    await expect(page.getByRole("img", { name: /^Spread win rate through Week 3/ })).toBeVisible();
    await expect(page.getByRole("img", { name: /^Totals win rate through Week 3/ })).toBeVisible();
    await openTable(page);
    const table = page.getByTestId("chart-table");
    await expect(table).toBeVisible();
    await expect(table.getByRole("row", { name: /Week 3.*3–3–2/ })).toBeVisible();
    await expect(chart).toHaveCount(0);
  });

  test("weeks show season-to-date records and an in-progress tag", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/model");
    const week3 = page.getByRole("row", { name: /Week 3/ });
    await expect(week3).toContainText("In progress");
    await expect(week3).toContainText("50.0%");
    await expect(week3).toContainText("3–3–2");
    await expect(page.getByRole("row", { name: /Week 0/ })).not.toContainText("In progress");
  });

  test("a partial record shows empty states instead of the trend and comparison", async ({ page }) => {
    await page.goto("/model?fixture=partial");
    await expect(page.getByText("The trend appears after two graded weeks.")).toBeVisible();
    await expect(page.getByTestId("table-toggle")).toHaveCount(0);
    await expect(page.getByText("No games with a retained pre-kickoff line and a final score yet.")).toHaveCount(2);
    await expect(page.getByTestId("market-spread")).not.toContainText("NaN");
  });

  test("one weekly table shows both targets with no selector or average-miss column", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/model");
    await expect(page.getByRole("columnheader", { name: "Spread", exact: true })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Totals", exact: true })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /Average miss/ })).toHaveCount(0);
    await expect(page.getByRole("group", { name: "Pick target" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "All Picks" })).toHaveCount(0);
  });

  for (const width of [320, 390, 640, 1280]) {
    test(`summary and weekly links stay usable at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/model");
      await expect(page.getByRole("heading", { name: "Season record & performance" })).toBeVisible();
      const weekly = page.getByRole("region", { name: "Weekly accuracy breakdown" });
      const link = weekly.getByRole("link", { name: "Week 0", exact: true }).filter({ visible: true });
      await expect(link).toHaveAttribute("href", "/?week=0");
      const box = await link.boundingBox();
      // Phone rows are 44px touch targets; the desktop table link stays compact.
      if (isPhone(page)) expect(box!.height).toBeGreaterThanOrEqual(44);
      else expect(box!.height).toBeLessThanOrEqual(40);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    });
  }
});

test.describe("inline links on phones", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the method page record link is a 44px tap target", async ({ page }) => {
    await page.goto("/model/method");
    const box = (await page.getByRole("link", { name: "See the 2026 record" }).boundingBox())!;
    expect(box.height).toBeGreaterThanOrEqual(44);
  });

  test("the ratings elite link is a 44px tap target", async ({ page }) => {
    await page.goto("/ratings");
    const box = (await page.getByRole("link", { name: "elite", exact: true }).boundingBox())!;
    expect(box.height).toBeGreaterThanOrEqual(44);
    expect(box.width).toBeGreaterThanOrEqual(44);
  });
});
