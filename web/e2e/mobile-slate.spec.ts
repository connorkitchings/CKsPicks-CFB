import { expect, test } from "@playwright/test";

for (const path of ["/", "/results"]) {
  test(`${path}: the first complete phone card fits above navigation`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(path);
    const card = page.locator("li[id^='game-']").first();
    await expect(card).toBeVisible();
    await expect(page.locator("details[open]")).toHaveCount(0);
    await expect(page.getByRole("group", { name: "Layout" })).toBeHidden();
    const cardBox = await card.boundingBox();
    const navigationBox = await page.getByRole("navigation", { name: "Main navigation" }).boundingBox();
    expect(cardBox).not.toBeNull();
    expect(navigationBox).not.toBeNull();
    expect(cardBox!.y + cardBox!.height).toBeLessThanOrEqual(navigationBox!.y);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await expect(card.locator("[data-pick]")).toHaveCount(2);
    await expect(card.getByRole("link", { name: "Matchup" })).toBeVisible();
  });

  test(`${path}: the first phone card clears a 34px home-indicator safe area`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(path);
    await expect(page.locator("li[id^='game-']").first()).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await page.addStyleTag({ content: `
      @media (max-width: 639px) {
        nav[aria-label="Main navigation"] { padding-bottom: 34px !important; }
        body { padding-bottom: calc(3.5rem + 34px + 0.5rem) !important; }
      }
    ` });
    const geometry = await page.evaluate(() => ({
      cardBottom: document.querySelector("li[id^='game-']")!.getBoundingClientRect().bottom,
      navigationTop: document.querySelector('nav[aria-label="Main navigation"]')!.getBoundingClientRect().top,
    }));
    expect(geometry.cardBottom).toBeLessThanOrEqual(geometry.navigationTop);
    await expect(page.locator("details[open]")).toHaveCount(0);
  });

  test(`${path}: desktop list selection becomes cards on phones and survives resize`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(path);
    await page.getByRole("button", { name: "list", exact: true }).click();
    await expect(page.locator("ul[data-layout]").first()).toHaveAttribute("data-layout", "list");
    const originalCount = await page.locator("li[id^='game-']").count();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.locator("ul[data-layout]").first()).toHaveAttribute("data-layout", "grid");
    await expect(page.locator("li[id^='game-']")).toHaveCount(originalCount);
    const ids = await page.locator("li[id^='game-']").evaluateAll((cards) => cards.map((card) => card.id));
    expect(new Set(ids).size).toBe(ids.length);
    await page.setViewportSize({ width: 1280, height: 900 });
    await expect(page.locator("ul[data-layout]").first()).toHaveAttribute("data-layout", "list");
  });
}

test("phone details preserve source, full forecast and venue through a filter rerender", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const card = page.locator("#game-3");
  await card.getByText("Game details", { exact: true }).click();
  await expect(card.getByText(/Los Angeles, CA/)).toBeVisible();
  await expect(card.getByText(/FanDuel/)).toBeVisible();
  await page.getByPlaceholder("Filter by team…").fill("Oregon");
  await expect(card.getByText(/FanDuel/)).toBeVisible();
  await card.getByText("Game details", { exact: true }).click();
  await expect(card.locator("details")).not.toHaveAttribute("open", "");
  await card.getByText("Game details", { exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(card.locator("details")).toHaveAttribute("open", "");
});

test("collapsed best bets preserve every game anchor and selected category", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const bestBets = page.getByRole("region", { name: "Best bets" });
  await bestBets.locator("summary").click();
  const anchors = await bestBets.locator("a[href^='#game-']").evaluateAll((links) => links.map((link) => link.getAttribute("href")));
  // Five spread leans and four eligible total leans in the unchanged slate fixture.
  expect(anchors).toEqual(["#game-3", "#game-9", "#game-1", "#game-8", "#game-5", "#game-3", "#game-6", "#game-5", "#game-1"]);
  await bestBets.getByRole("button", { name: "Totals", exact: true }).click();
  await expect(bestBets.getByRole("button", { name: "Totals", exact: true })).toHaveAttribute("aria-pressed", "true");
  const firstAnchor = bestBets.locator("a[href^='#game-']:visible").first();
  const target = await firstAnchor.getAttribute("href");
  await firstAnchor.click();
  expect(new URL(page.url()).hash).toBe(target);
});


test("search waits for hydration before accepting the first filter", async ({ page }) => {
  let releaseScripts!: () => void;
  const scriptsReady = new Promise<void>((resolve) => { releaseScripts = resolve; });
  await page.route("**/_next/static/**/*.js", async (route) => {
    await scriptsReady;
    await route.continue();
  });
  try {
    await page.goto("/", { waitUntil: "commit" });
    const search = page.getByRole("searchbox", { name: "Filter by team" });
    await expect(search).toBeVisible();
    await expect(search).not.toBeEditable();
    await expect(search).toHaveAttribute("aria-busy", "true");
    const firstFilter = search.fill("Oregon");
    releaseScripts();
    await firstFilter;
    await expect(search).toBeEditable();
    await expect(search).toHaveValue("Oregon");
    await expect(page.locator("li[id^='game-']")).toHaveCount(1);
    await expect(page.locator("li[id^='game-']")).toHaveAttribute("id", "game-3");
  } finally {
    releaseScripts();
  }
});

test("market timestamps hydrate without replacing the slate", async ({ page }) => {
  const hydrationErrors: string[] = [];
  page.on("pageerror", (error) => {
    if (/hydration|server rendered/i.test(error.message)) hydrationErrors.push(error.message);
  });
  await page.goto("/?mode=market");
  await expect(page.getByRole("searchbox", { name: "Filter by team" })).toBeEditable();
  await expect(page.getByRole("table", { name: "Market and results" })).toBeVisible();
  await expect(page.getByText("Sat, Aug 29, 3:30 PM EDT", { exact: true })).toBeVisible();
  expect(hydrationErrors).toEqual([]);
});
