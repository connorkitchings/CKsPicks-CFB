import { expect, test } from "@playwright/test";

test.describe("team pages (fixture mode)", () => {
  test("a normal team shows its history and games", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/teams/Texas");
    await expect(page.getByRole("heading", { level: 1, name: "Texas" })).toBeVisible();
    await expect(page).toHaveTitle(/Texas · Team page/);
    await expect(page.getByRole("heading", { name: "Rating history" })).toBeVisible();
    await expect(page.getByRole("table")).toBeVisible();
    await expect(page.getByRole("link", { name: "← All ratings" })).toBeVisible();
  });

  for (const width of [390, 320]) {
    test(`the phone page fits at ${width}px with a back bar, header, history and schedule`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/teams/Texas");
      const bar = page.getByTestId("app-bar");
      await expect(bar.getByRole("link", { name: "Back to ratings" })).toHaveAttribute("href", "/ratings");
      await expect(page.getByTestId("app-bar-title")).toHaveText("TEX");
      await expect(page.getByRole("link", { name: "← All ratings" })).toBeHidden();
      const heading = page.getByRole("heading", { level: 1, name: "Texas" });
      await expect(heading).toBeVisible();
      await expect(page.locator("main img").first()).toBeVisible();
      await expect(page.getByText("4–0", { exact: true })).toBeVisible();

      const cells = page.locator("main dl > div");
      await expect(cells.locator("dt")).toHaveText(["OFF", "DEF", "SOR", "SOS"]);
      await expect(cells.locator("dd").nth(0)).toHaveText("+3.40");
      await expect(cells.locator("dd").nth(2)).toHaveText(/^#\d+$/);
      await expect(cells.locator("dd").nth(3)).toHaveText("#3");
      await expect(page.locator('[title="Overall rank"]')).toHaveText(/^#\d+$/);
      const tops = await cells.evaluateAll((nodes) => nodes.map((n) => Math.round(n.getBoundingClientRect().top)));
      expect(new Set(tops).size).toBe(1);

      const table = page.getByRole("table");
      await expect(table.getByRole("columnheader", { name: "Week" })).toBeVisible();
      await expect(table.getByRole("columnheader", { name: "Overall" })).toBeVisible();
      await expect(table.getByRole("columnheader", { name: "OFF" })).toBeVisible();
      await expect(table.getByRole("columnheader", { name: "Uncertainty" })).toBeHidden();
      await expect(table.getByRole("columnheader", { name: "DEF" })).toBeVisible();
      await expect(page.getByRole("img", { name: /^Overall rating 5\.50 in Week 0, 5\.90 in Week 1$/ })).toBeVisible();

      await expect(page.getByLabel("Next game")).toBeVisible();
      await expect(page.getByLabel("Next game")).toContainText("at Ohio State");
      const rows = page.getByRole("list", { name: "Schedule" }).getByRole("listitem");
      await expect(rows).toHaveCount(2);
      await expect(rows.nth(0)).toContainText("vs Ohio State");
      await expect(rows.nth(0)).toContainText("W 24–21");
      await expect(rows.nth(1)).toContainText("Forecast: Ohio State -6.2 · 54.8");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
  }

  test("the desktop page shows the Uncertainty column and a text back link", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/teams/Texas");
    await expect(page.getByRole("columnheader", { name: "Uncertainty" })).toBeVisible();
    await expect(page.getByRole("link", { name: "← All ratings" })).toHaveAttribute("href", "/ratings");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });

  test("legacy rating names and CFBD names reach the same page", async ({ page }) => {
    for (const segment of ["San%20Jos%C3%A9%20State", "San%20Jose%20State", "Hawai'i", "Hawai_i"]) {
      const response = await page.goto(`/teams/${segment}`);
      expect(response?.status(), segment).toBe(200);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(/San José State|Hawai'i/);
    }
  });

  test("an unknown team is a 404", async ({ page }) => {
    const response = await page.goto("/teams/Nowhere%20State");
    expect(response?.status()).toBe(404);
  });
});
