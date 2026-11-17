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
  const cx = (team: string) => chartFor().locator(`[data-team="${team}"] circle.focus-ring`).getAttribute("cx");
  await gotoHydrated(page, "/teams?view=resume&conf=p4");
  const team = (await chartFor().locator("[data-team]").first().getAttribute("data-team"))!;
  const filtered = await cx(team);
  await gotoHydrated(page, "/teams?view=resume");
  expect(await cx(team)).toBe(filtered);
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
  await page.locator('html[data-hydrated="true"]').waitFor({ state: "attached" });
  await assertCleared();
  await page.getByRole("searchbox", { name: "Search teams" }).fill("tex");
  await page.getByRole("combobox", { name: "Filter by conference" }).selectOption("SEC");
  await page.getByRole("button", { name: "Offense", exact: true }).click();
  await assertCleared();
  await page.getByRole("combobox", { name: "Rating period" }).selectOption({ label: "Preseason" });
  await expect.poll(() => new URL(page.url()).searchParams.get("period")).toBe("preseason");
  await expect(page.getByText(/^Preseason · 4 teams/)).toBeVisible();
  const assertView = async (view: "Compare" | "Trends") => {
    await expect.poll(() => new URL(page.url()).searchParams.get("view")).toBe(view.toLowerCase());
    await expect(page.getByRole("button", { name: view, exact: true })).toHaveAttribute("aria-current", "page");
    await expect.poll(() => new URL(page.url()).searchParams.get("period")).toBe("preseason");
    await assertCleared();
  };
  await assertView("Trends");
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await assertView("Compare");
  await page.getByRole("button", { name: "Trends", exact: true }).click();
  await assertView("Trends");
  await page.goBack();
  await assertView("Compare");
  await page.goForward();
  await assertView("Trends");
});

test("redirect preserves cleared Trends selection and nonempty team aliases resolve", async ({ page }) => {
  await gotoHydrated(page, "/ratings?view=trends&team=");
  expect(new URL(page.url()).pathname).toBe("/teams");
  expect(new URL(page.url()).searchParams.get("team")).toBe("");
  await expect(page.getByRole("combobox", { name: "First team" })).toHaveValue("");
  await gotoHydrated(page, "/teams?view=trends&team=App%20State");
  await expect(page.getByRole("combobox", { name: "First team" })).toHaveValue("Appalachian State");
});

test("/teams?group=resume ranks by SOR, not by raw overall rating", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoHydrated(page, "/teams?group=resume");
  const items = page.getByRole("list", { name: "Team ratings list" }).getByRole("listitem");
  await expect(items.first().getByRole("link").locator("span").first()).toHaveText("#1");
  const ranks = await items.getByRole("link").locator("span:first-child").allTextContents();
  for (const rank of ranks) expect(rank).not.toContain(".");
  await expect(page.locator("#rating-sort")).toHaveValue("sor");
});

test("phone ratings rows are compact and reveal details one toggle at a time", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoHydrated(page, "/teams");
  const list = page.getByRole("list", { name: "Team ratings list" });
  const items = list.getByRole("listitem");
  const count = await items.count();
  expect(count).toBeGreaterThan(1);
  for (let i = 0; i < count; i++) expect((await items.nth(i).boundingBox())!.height).toBeLessThanOrEqual(64);
  expect((await list.boundingBox())!.height / count).toBeLessThan(80);
  const first = items.nth(0);
  const second = items.nth(1);
  await expect(first.locator("dl")).toHaveCount(0);
  const toggle = first.getByRole("button", { name: /details for/ });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect((await toggle.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await toggle.click();
  await second.getByRole("button", { name: /details for/ }).click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(first.locator("dl")).toBeVisible();
  await expect(second.locator("dl")).toBeVisible();
});

test("résumé plot keeps the rank-1 dot below the top frame and table links are tap-sized", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoHydrated(page, "/teams?view=resume");
  const chart = page.getByRole("group", { name: "Strength versus résumé scatterplot" });
  const gap = await chart.evaluate((group) => {
    const svg = group.closest("svg") ?? group.querySelector("svg") ?? group.ownerDocument.querySelector("svg");
    const frame = svg!.querySelector('rect[fill="var(--surface-card)"]')!;
    const top = Number(frame.getAttribute("y"));
    const cys = [...group.querySelectorAll("[data-team] circle.focus-ring")].map((c) => Number(c.getAttribute("cy")));
    return Math.min(...cys) - top;
  });
  expect(gap).toBeGreaterThanOrEqual(8);
  await expect(chart.getByText("#0", { exact: true })).toHaveCount(0);
  await page.getByText("Show as table").click();
  const link = page.locator("details table tbody a").first();
  expect((await link.boundingBox())!.height).toBeGreaterThanOrEqual(44);
});
