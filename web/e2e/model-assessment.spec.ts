import { expect, test, type Page } from "@playwright/test";
import { gotoHydrated } from "./helpers";

const points = (page: Page) => page.getByTestId("error-point");
const tableRows = (page: Page) => page.getByTestId("error-table").locator("tbody tr");
const targetButton = (page: Page, name: "Spread" | "Totals") =>
  page.getByRole("group", { name: "Error target" }).getByRole("button", { name, exact: true });

async function openTable(page: Page) {
  const details = page.getByTestId("error-table-details");
  if ((await details.getAttribute("open")) === null) await details.locator("summary").click();
  await expect(page.getByTestId("error-table")).toBeVisible();
}

test.describe("model assessment", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("sections run from separate records to paired accuracy, errors, weekly results and limits", async ({ page }) => {
    await gotoHydrated(page, "/model");
    const order = await page.evaluate((ids) => {
      const nodes = ids.map((id) => document.getElementById(id)!);
      return nodes.every(Boolean) && nodes.every((node, i) => i === 0 || !!(nodes[i - 1].compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING));
    }, ["kpi-heading", "market-heading", "trend-heading", "errors-heading", "weekly-heading", "calibration-heading"]);
    expect(order).toBe(true);
    const summary = page.getByRole("region", { name: "Forecast accuracy summary", exact: true });
    await expect(summary.getByTestId("record-spread")).toContainText("6 decided · 2 pushes");
    await expect(summary.getByTestId("record-total")).toContainText("6 decided · 2 pushes");
    await expect(page.getByTestId("record-caveat")).toContainText("52.4% is the reference win rate");
    await expect(page.locator("body").getByText(/luck|normal approximation|significan/i)).toHaveCount(0);
  });

  test("the target persists in the URL across reload and invalid values normalize to spread", async ({ page }) => {
    await gotoHydrated(page, "/model");
    await expect(targetButton(page, "Spread")).toHaveAttribute("aria-pressed", "true");
    await expect(points(page)).toHaveCount(7);
    await targetButton(page, "Totals").click();
    await expect(page).toHaveURL(/[?&]target=total/);
    await expect(targetButton(page, "Totals")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("error-count")).toContainText("7 games");
    await page.reload();
    await expect(targetButton(page, "Totals")).toHaveAttribute("aria-pressed", "true");
    await page.goto("/model?target=nonsense");
    await expect(targetButton(page, "Spread")).toHaveAttribute("aria-pressed", "true");
  });

  test("selecting a point shows the forecast, line, actual, both errors and a matchup link", async ({ page }) => {
    await gotoHydrated(page, "/model");
    await expect(page.getByTestId("equal-error-diagonal")).toHaveCount(1);
    const detail = page.getByTestId("error-detail");
    await expect(detail).toContainText("Select a point");
    const point = page.getByRole("button", { name: /^Wyoming at Boise State, Week 3/ });
    await point.click();
    await expect(point).toHaveAttribute("aria-pressed", "true");
    await expect(detail).toContainText("Wyoming at Boise State");
    await expect(detail).toContainText("Model forecast");
    await expect(detail).toContainText("Boise State by 10.0");
    await expect(detail).toContainText("Retained line");
    await expect(detail).toContainText("Boise State by 20.0");
    await expect(detail).toContainText("Boise State by 45.0");
    await expect(detail).toContainText("35.0 pts toward Wyoming");
    await expect(detail).toContainText("25.0 pts toward Wyoming");
    await expect(detail).toContainText("Betting line");
    await expect(detail.getByTestId("matchup-link")).toHaveAttribute("href", "/matchup/401000009");
    // Switching target clears the selection.
    await targetButton(page, "Totals").click();
    await expect(detail).toContainText("Select a point");
  });

  test("the table lists the same games as the scatter and sorts with aria-sort", async ({ page }) => {
    await gotoHydrated(page, "/model");
    await openTable(page);
    await expect(tableRows(page)).toHaveCount(await points(page).count());
    await expect(page.getByTestId("error-table").locator("xpath=ancestor::div[contains(@class,'overflow-x-auto')]")).toHaveCount(1);
    const modelError = page.getByTestId("error-table").getByRole("columnheader", { name: /Model error/ });
    await expect(page.getByTestId("error-table").getByRole("columnheader", { name: /^Week/ })).toHaveAttribute("aria-sort", "ascending");
    await modelError.getByRole("button").click();
    await expect(modelError).toHaveAttribute("aria-sort", "ascending");
    await modelError.getByRole("button").click();
    await expect(modelError).toHaveAttribute("aria-sort", "descending");
    await expect(tableRows(page).first()).toContainText("Wyoming at Boise State");
    await tableRows(page).first().getByRole("button").click();
    await expect(page.getByTestId("error-detail")).toContainText("Wyoming at Boise State");
    await targetButton(page, "Totals").click();
    await openTable(page);
    await expect(tableRows(page)).toHaveCount(await points(page).count());
  });

  test("points work from the keyboard", async ({ page }) => {
    await gotoHydrated(page, "/model");
    const first = points(page).first();
    await first.focus();
    await page.keyboard.press("ArrowRight");
    const second = points(page).nth(1);
    await expect(second).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(second).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("error-detail")).not.toContainText("Select a point");
    await page.keyboard.press("End");
    await expect(points(page).last()).toBeFocused();
    await page.keyboard.press("Space");
    await expect(points(page).last()).toHaveAttribute("aria-pressed", "true");
    await expect(second).toHaveAttribute("aria-pressed", "false");
  });

  test("the latest four weeks lead and older weeks sit in an expandable archive", async ({ page }) => {
    await gotoHydrated(page, "/model");
    const weekly = page.getByRole("region", { name: "Weekly accuracy breakdown" });
    await expect(weekly.getByRole("link", { name: /^Week \d$/ })).toHaveCount(4);
    await expect(page.getByTestId("weekly-archive")).toHaveCount(0);

    await gotoHydrated(page, "/model?fixture=archive");
    await expect(weekly.getByRole("link", { name: /^Week \d$/ })).toHaveCount(4);
    await expect(weekly.getByRole("link", { name: "Week 7", exact: true })).toBeVisible();
    const archive = page.getByTestId("weekly-archive");
    await expect(archive).not.toHaveAttribute("open", "");
    await expect(archive.getByRole("link", { name: /^Week \d$/ })).toHaveCount(0);
    await archive.locator("summary").click();
    await expect(archive.getByRole("link", { name: /^Week \d$/ })).toHaveCount(4);
    await expect(archive.getByRole("link", { name: "Week 0", exact: true })).toBeVisible();
  });
});

for (const width of [320, 390]) {
  test(`the error view fits ${width}px with the table open and a point selected`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await gotoHydrated(page, "/model?target=total");
    await points(page).first().click();
    await openTable(page);
    await expect(page.getByTestId("error-detail")).not.toContainText("Select a point");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}
