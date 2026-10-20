import { expect, test, type Locator, type Page } from "@playwright/test";

const DESKTOP = { width: 1280, height: 900 };

/** Segmented options must stay compact and one line tall, so a wrapped label fails here. */
async function expectCompactSegments(group: Locator): Promise<void> {
  const options = group.getByRole("button");
  const count = await options.count();
  expect(count).toBeGreaterThan(1);
  for (let index = 0; index < count; index += 1) {
    const option = options.nth(index);
    const measured = await option.evaluate((element) => {
      const style = getComputedStyle(element);
      const fontSize = parseFloat(style.fontSize);
      const lineHeight = parseFloat(style.lineHeight) || fontSize * 1.2;
      const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
      const minHeight = parseFloat(style.minHeight) || 0;
      return { oneLine: lineHeight + padding, minHeight, height: element.getBoundingClientRect().height };
    });
    // A wrapped label grows past one line; min-height may exceed one line when the control is taller.
    expect(measured.height, `segment ${index} height`).toBeLessThanOrEqual(Math.max(measured.oneLine, measured.minHeight) + 0.5);
    expect(measured.height, `segment ${index} height`).toBeLessThanOrEqual(40);
  }
}

async function expectMaxHeight(locator: Locator, max = 40): Promise<void> {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.height).toBeLessThanOrEqual(max);
}

function visibleHeading(page: Page, name: string): Locator {
  return page.getByRole("heading", { name, exact: true }).filter({ visible: true });
}

test.describe("desktop layout at 1280px", () => {
  test.use({ viewport: DESKTOP });

  test("slate toolbar controls are compact and the layout toggle reads Grid and List", async ({ page }) => {
    await page.goto("/");
    const toolbar = page.getByRole("group", { name: "Layout" });
    await expect(toolbar).toBeVisible();
    await expect(toolbar.getByRole("button", { name: "Grid", exact: true })).toBeVisible();
    await expect(toolbar.getByRole("button", { name: "List", exact: true })).toBeVisible();
    await expectCompactSegments(toolbar);
    await expectMaxHeight(toolbar);

    const sort = page.getByRole("combobox", { name: "Sort by" });
    await expect(sort).toBeVisible();
    await expectMaxHeight(sort);

    const search = page.getByRole("searchbox", { name: "Filter by team" });
    await expect(search).toBeVisible();
    await expectMaxHeight(search);
  });

  test("slate shows Biggest edges and the season record without a click", async ({ page }) => {
    await page.goto("/");
    const biggestEdges = page.getByRole("region", { name: "Biggest edges" });
    await expect(biggestEdges.getByText("Biggest edges", { exact: false }).filter({ visible: true }).first()).toBeVisible();
    await expect(biggestEdges.getByText("Spread", { exact: true }).filter({ visible: true }).first()).toBeVisible();
    await expect(biggestEdges.locator("summary").filter({ visible: true })).toHaveCount(0);

    const record = page.getByRole("region", { name: "Record", exact: true });
    await expect(visibleHeading(page, "Season record")).toBeVisible();
    await expect(record).toBeVisible();
  });

  test("results shows Result Highlights without a click", async ({ page }) => {
    await page.goto("/results");
    await expect(visibleHeading(page, "Highlights")).toBeVisible();
    await expect(page.locator("summary").filter({ visible: true, hasText: "Highlights" })).toHaveCount(0);
  });

  test("performance Pick target control is compact and one line per option", async ({ page }) => {
    await page.goto("/performance");
    const target = page.getByRole("group", { name: "Pick target" }).filter({ visible: true });
    await expect(target).toBeVisible();
    await expectCompactSegments(target);
    await expectMaxHeight(target);
  });

  test("ratings sort headers are compact and one line at desktop width", async ({ page }) => {
    await page.goto("/ratings");
    const labels = [
      "Sort by Overall",
      "Sort by Offense",
      "Sort by Defense",
      "Sort by SOR",
      "Sort by SOS Played",
      "Sort by SOS Remaining",
      "Sort by SOS Full",
    ];
    for (const label of labels) {
      const header = page.getByRole("button", { name: label, exact: true }).filter({ visible: true });
      await expect(header, label).toHaveCount(1);
      await expectMaxHeight(header, 40);
      const measured = await header.evaluate((element) => {
        const style = getComputedStyle(element);
        const fontSize = parseFloat(style.fontSize);
        const lineHeight = parseFloat(style.lineHeight) || fontSize * 1.2;
        const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
        const minHeight = parseFloat(style.minHeight) || 0;
        return { oneLine: lineHeight + padding, minHeight, height: element.getBoundingClientRect().height };
      });
      // A wrapped label grows past one line; min-height may exceed one line when the control is taller.
      expect(measured.height, `${label} height`).toBeLessThanOrEqual(Math.max(measured.oneLine, measured.minHeight) + 0.5);
    }
  });

  test("matchup hero places the forecast panel between the two teams", async ({ page }) => {
    await page.goto("/matchup/1");
    const away = page.locator('[data-side="away"]').filter({ visible: true });
    const home = page.locator('[data-side="home"]').filter({ visible: true });
    const forecast = page.getByTestId("forecast-grid");
    await expect(forecast).toBeVisible();

    const [awayBox, homeBox, forecastBox] = await Promise.all([away.boundingBox(), home.boundingBox(), forecast.boundingBox()]);
    expect(awayBox).not.toBeNull();
    expect(homeBox).not.toBeNull();
    expect(forecastBox).not.toBeNull();
    expect(awayBox!.x + awayBox!.width).toBeLessThanOrEqual(forecastBox!.x);
    expect(forecastBox!.x + forecastBox!.width).toBeLessThanOrEqual(homeBox!.x);

    // The team blocks are direct children of the hero grid, so their parent sets the track count.
    const columns = await away.evaluate((element) => getComputedStyle(element.parentElement!).gridTemplateColumns.split(" ").length);
    expect(columns).toBe(3);
  });

  test("matchup offense selector is hidden at desktop widths where both tables show", async ({ page }) => {
    await page.goto("/matchup/1");
    await expect(page.getByRole("group", { name: "Offense comparison" })).toBeHidden();
    await expect(page.getByRole("table")).toHaveCount(2);
  });

  test("each unit table header shows one logo per team in light mode", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/matchup/1");
    for (const table of await page.getByRole("table").all()) {
      const header = table.locator("xpath=preceding-sibling::div[1]");
      await expect(header.locator("img[data-logo]:visible")).toHaveCount(2);
    }
  });

  test("matchup offense selector is compact at tablet width", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 900 });
    await page.goto("/matchup/1");
    const selector = page.getByRole("group", { name: "Offense comparison" });
    await expect(selector).toBeVisible();
    await expectCompactSegments(selector);
    await expectMaxHeight(selector);
  });
});
