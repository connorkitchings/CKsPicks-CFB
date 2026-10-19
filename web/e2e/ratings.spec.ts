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
