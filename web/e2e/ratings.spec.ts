import { expect, test } from "@playwright/test";

const fits = (page: import("@playwright/test").Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

test.describe("mobile team ratings", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("each category promotes its own value and preserves national rank when filtered", async ({ page }) => {
    await page.goto("/ratings");
    const list = page.getByRole("list", { name: "Team ratings list" });
    const cases = [
      { category: "Overall", team: "Texas", value: "+5.50" },
      { category: "Offense", team: "Ohio State", value: "+4.80" },
      { category: "Defense", team: "Appalachian State", value: "+3.60" },
    ];
    for (const entry of cases) {
      await page.getByRole("button", { name: entry.category, exact: true }).click();
      await expect(page.getByRole("button", { name: entry.category, exact: true })).toHaveAttribute("aria-pressed", "true");
      const first = list.getByRole("listitem").first();
      await expect(first).toContainText(entry.team);
      await expect(first.getByTestId("primary-rating")).toHaveText(`${entry.category}${entry.value}`);
      await expect(first).toContainText("Overall uncertainty ±1.63");
    }
    await page.getByRole("button", { name: "Offense", exact: true }).click();
    await page.getByRole("searchbox", { name: "Search teams" }).fill("Appalachian State");
    await expect(list.getByRole("listitem")).toHaveCount(1);
    await expect(list.getByLabel("National rank 3")).toBeVisible();
    await page.getByRole("searchbox", { name: "Search teams" }).fill("no matching team");
    await expect(page.getByRole("status")).toContainText("No teams match");
    await page.getByRole("button", { name: "Clear search", exact: true }).last().click();
    await expect(list.getByRole("listitem")).toHaveCount(4);
  });

  test("period changes preserve live search and sort and update frozen values", async ({ page }) => {
    await page.goto("/ratings?season=2026");
    await page.getByRole("searchbox", { name: "Search teams" }).fill("Texas");
    await page.getByRole("button", { name: "Offense", exact: true }).click();
    await page.getByLabel("Rating period", { exact: true }).selectOption({ label: "Post-Week 3" });
    await expect(page).toHaveURL(/sort=offense/);
    await expect(page).toHaveURL(/q=Texas/);
    await expect(page).toHaveURL(/season=2026/);
    await expect(page.getByRole("searchbox", { name: "Search teams" })).toHaveValue("Texas");
    await expect(page.getByRole("button", { name: "Offense", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("primary-rating")).toHaveText("Offense+3.20");
    await expect(page.getByText(/Evidence cutoff: Sep 22, 2026/)).toBeVisible();
    await page.getByLabel("Rating period", { exact: true }).selectOption({ label: "Preseason" });
    await expect(page.getByTestId("primary-rating")).toHaveText("Offense+3.00");
    await expect(page.getByText(/Preseason baseline priors before 2026 kickoff. Overall uncertainty/)).toBeVisible();
  });

  for (const width of [320, 360, 390, 430, 639, 640, 768, 1024, 1280]) {
    test(`loaded ratings and period controls fit ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/ratings");
      await expect(page.getByRole("heading", { name: "Team ratings" })).toBeVisible();
      if (width < 640) {
        await expect(page.getByLabel("Rating period", { exact: true })).toBeVisible();
        await expect(page.getByRole("navigation", { name: "Ratings timeline" })).toBeHidden();
        await expect(page.getByRole("list", { name: "Team ratings list" })).toContainText("Southern Mississippi");
      } else {
        await expect(page.getByLabel("Rating period", { exact: true })).toBeHidden();
        await expect(page.getByRole("navigation", { name: "Ratings timeline" })).toBeVisible();
        await expect(page.getByRole("table")).toContainText("Southern Mississippi");
      }
      expect(await fits(page)).toBe(true);
    });
  }
});

test("desktop timeline carries live filters and selected column semantics", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/ratings");
  await page.getByRole("searchbox", { name: "Search teams" }).fill("Appalachian");
  await page.getByRole("button", { name: "Defense", exact: true }).click();
  await expect(page.getByRole("columnheader", { name: "Defense", exact: true })).toHaveAttribute("aria-sort", "descending");
  await page.getByRole("navigation", { name: "Ratings timeline" }).getByRole("link", { name: "Post-Week 3" }).click();
  await expect(page).toHaveURL(/sort=defense/);
  await expect(page).toHaveURL(/q=Appalachian/);
  await expect(page.getByRole("searchbox", { name: "Search teams" })).toHaveValue("Appalachian");
  await expect(page.getByRole("columnheader", { name: "Defense", exact: true })).toHaveAttribute("aria-sort", "descending");
  await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(1);
  await expect(page.getByRole("navigation", { name: "Ratings timeline" }).getByRole("link", { name: "Post-Week 3" })).toHaveAttribute("aria-current", "page");
});

test.describe("résumé columns", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  // Table cells in order: rank, Overall, Offense, Defense, W-L, SOR, WAA, SOS, uncertainty.
  const rowCells = (page: import("@playwright/test").Page, team: string) =>
    page.getByRole("table").locator("tbody tr", { hasText: team }).getByRole("cell");
  const RESUME_SORT = "Résumé sort";

  test("W-L, SOR, WAA and SOS render fixture values and the Elite reference links to methodology", async ({ page }) => {
    await page.goto("/ratings");
    await expect(page.getByRole("columnheader", { name: "W-L (vs FBS)", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Elite", exact: true })).toHaveAttribute("href", "/methodology#elite-reference");

    const texas = rowCells(page, "Texas");
    await expect(texas.nth(4)).toHaveText("4–0");
    await expect(texas.nth(5)).toHaveText("81.2 #2");
    await expect(texas.nth(6)).toHaveText("+1.6");
    await expect(texas.nth(7)).toHaveText("41.3 / 47.9 / 45.7");

    const ohioState = rowCells(page, "Ohio State");
    await expect(ohioState.nth(4)).toHaveText("3–1");
    await expect(ohioState.nth(5)).toHaveText("93.7 #1");
    await expect(ohioState.nth(6)).toHaveText("+2.1");

    // Fewer than 3 completed FBS games: SOR and WAA are null and render as dashes.
    const southernMiss = rowCells(page, "Southern Mississippi");
    await expect(southernMiss.nth(4)).toHaveText("1–1");
    await expect(southernMiss.nth(5)).toHaveText("—");
    await expect(southernMiss.nth(6)).toHaveText("—");
  });

  test("the SOS reference switch changes the SOS values", async ({ page }) => {
    await page.goto("/ratings");
    const texas = rowCells(page, "Texas");
    await expect(texas.nth(7)).toHaveText("41.3 / 47.9 / 45.7");

    const reference = page.getByRole("group", { name: "SOS reference" });
    await reference.getByRole("button", { name: "Average", exact: true }).click();
    await expect(reference.getByRole("button", { name: "Average", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(texas.nth(7)).toHaveText("52.6 / 58.4 / 56.5");
  });

  test("the résumé sort orders rows by SOR with null SOR last", async ({ page }) => {
    await page.goto("/ratings");
    const rows = page.getByRole("table").locator("tbody tr");
    await expect(rows.nth(0)).toContainText("Texas");

    await page.getByRole("group", { name: RESUME_SORT }).getByRole("button", { name: "SOR", exact: true }).click();
    await expect(page.getByRole("columnheader", { name: "SOR", exact: true })).toHaveAttribute("aria-sort", "descending");
    await expect(rows.nth(0)).toContainText("Ohio State");
    await expect(rows.nth(1)).toContainText("Texas");
    await expect(rows.nth(2)).toContainText("Appalachian State");
    await expect(rows.nth(3)).toContainText("Southern Mississippi");
  });

  // Pending: `?sort=sor` is accepted only once the page widens its accepted sort values (in progress
  // on another task). Until that merges this test fails because the page falls back to Overall.
  test("?sort=sor selects the SOR sort on load and after reload", async ({ page }) => {
    await page.goto("/ratings?sort=sor");
    const rows = page.getByRole("table").locator("tbody tr");
    const sorButton = page.getByRole("group", { name: RESUME_SORT }).getByRole("button", { name: "SOR", exact: true });
    await expect(sorButton).toHaveAttribute("aria-pressed", "true");
    await expect(rows.nth(0)).toContainText("Ohio State");

    await page.reload();
    await expect(sorButton).toHaveAttribute("aria-pressed", "true");
    await expect(rows.nth(0)).toContainText("Ohio State");
  });
});

test.describe("release without résumé rows", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("renders dashes for résumé columns, hides the résumé controls, and logs no errors", async ({ page }) => {
    const problems: string[] = [];
    page.on("pageerror", (error) => problems.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") problems.push(message.text());
    });

    // `no-resume` is the fixture period that serves ratings without résumé rows.
    await page.goto("/ratings?period=no-resume");
    await expect(page.getByRole("heading", { name: "Team ratings" })).toBeVisible();
    await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(4);
    await expect(page.getByRole("columnheader", { name: "W-L (vs FBS)", exact: true })).toBeVisible();

    const texas = page.getByRole("table").locator("tbody tr", { hasText: "Texas" }).getByRole("cell");
    await expect(texas.nth(1)).toHaveText("+5.50");
    await expect(texas.nth(4)).toHaveText("—");
    await expect(texas.nth(5)).toHaveText("—");
    await expect(texas.nth(6)).toHaveText("—");
    await expect(texas.nth(7)).toHaveText("—");

    await expect(page.getByRole("group", { name: "Résumé sort" })).toBeHidden();
    await expect(page.getByRole("group", { name: "SOS reference" })).toBeHidden();
    await expect(page.getByRole("link", { name: "Elite", exact: true })).toBeHidden();
    expect(problems).toEqual([]);
  });
});
