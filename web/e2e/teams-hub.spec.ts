import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

test("/ratings lands on Teams in the browser with its query intact", async ({ page }) => {
  await page.goto("/ratings?sort=sor&dir=asc&q=tex&view=compare");
  const url = new URL(page.url());
  expect(url.pathname).toBe("/teams");
  expect(Object.fromEntries(url.searchParams)).toMatchObject({ sort: "sor", dir: "asc", q: "tex", view: "compare" });
});

test("two quick comparison selections both survive in the URL", async ({ page }) => {
  await gotoHydrated(page, "/teams?view=compare");
  const first = page.getByRole("combobox", { name: "First team" });
  const second = page.getByRole("combobox", { name: "Second team" });
  const options = await first.locator("option").allTextContents();
  const [a, b] = options.filter((name) => name && name !== "Choose a team");
  await Promise.all([first.selectOption(a), second.selectOption(b)]);
  await expect(page).toHaveURL(new RegExp(`team=${encodeURIComponent(a).replace(/%20/g, "(\\+|%20)")}`));
  const params = new URL(page.url()).searchParams;
  expect(params.get("team")).toBe(a);
  expect(params.get("compare")).toBe(b);
});

test("phone rank label follows the selected sort and the résumé scale ignores filters", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoHydrated(page, "/teams?sort=offense&dir=desc");
  const list = page.getByRole("list", { name: "Team ratings list" });
  const firstCard = list.getByRole("listitem").first();
  const offenseRank = await firstCard.getByRole("link").locator("span").first().textContent();
  expect(offenseRank).toBe("#1");
  const chartFor = () => page.getByRole("group", { name: "Strength versus résumé scatterplot" });
  const cx = (label: string) => chartFor().getByRole("button", { name: label }).locator("circle").getAttribute("cx");
  await gotoHydrated(page, "/teams?view=resume&conf=p4");
  const label = (await chartFor().getByRole("button").first().getAttribute("aria-label"))!;
  const filtered = await cx(label);
  await gotoHydrated(page, "/teams?view=resume");
  expect(await cx(label)).toBe(filtered);
});

test("the phone schedule has no nested links and links opponents inside the row", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoHydrated(page, "/teams/Texas");
  const rows = page.getByRole("list", { name: "Schedule" });
  await expect(rows.locator("a a")).toHaveCount(0);
  await expect(rows.getByText("Opponent profile")).toHaveCount(0);
  await expect(rows.getByTestId("matchup-link").first()).toBeAttached();
  await expect(rows.locator("li a[href^='/teams/']").first()).toBeVisible();
});

test("cleared Trends selection survives navigation, filters, periods and history", async ({ page }) => {
  await gotoHydrated(page, "/teams?view=trends");
  const first = page.getByRole("combobox", { name: "First team" });
  await expect(first).not.toHaveValue("");
  await first.selectOption("");
  const assertCleared = async () => {
    await expect(page.getByRole("combobox", { name: "First team" })).toHaveValue("");
    const params = new URL(page.url()).searchParams;
    expect(params.has("team")).toBe(true);
    expect(params.get("team")).toBe("");
  };
  await assertCleared();
  await page.reload();
  await assertCleared();
  await page.getByRole("searchbox", { name: "Search teams" }).fill("tex");
  await page.getByRole("combobox", { name: "Filter by conference" }).selectOption("SEC");
  await page.getByRole("button", { name: "Offense", exact: true }).click();
  await assertCleared();
  await page.getByRole("combobox", { name: "Rating period" }).selectOption({ label: "Preseason" });
  await assertCleared();
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await assertCleared();
  await page.getByRole("button", { name: "Trends", exact: true }).click();
  await assertCleared();
  await page.goBack();
  await assertCleared();
  await page.goForward();
  await assertCleared();
});

test("redirect preserves cleared Trends selection and nonempty team aliases resolve", async ({ page }) => {
  await gotoHydrated(page, "/ratings?view=trends&team=");
  expect(new URL(page.url()).pathname).toBe("/teams");
  expect(new URL(page.url()).searchParams.get("team")).toBe("");
  await expect(page.getByRole("combobox", { name: "First team" })).toHaveValue("");
  await gotoHydrated(page, "/teams?view=trends&team=App%20State");
  await expect(page.getByRole("combobox", { name: "First team" })).toHaveValue("Appalachian State");
});
