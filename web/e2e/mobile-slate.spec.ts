import { expect, test } from "@playwright/test";

// Upcoming week, then a final week whose graded cards and highlights share the page.
for (const path of ["/", "/?week=4"]) {
  test(`${path}: the first complete phone card fits above navigation`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(path);
    const card = page.locator("li[id^='game-']").first();
    await expect(card).toBeVisible();
    await expect(page.locator("details[open]")).toHaveCount(0);
    await expect(page.getByRole("group", { name: "Layout" })).toBeHidden();
    // A graded week stacks the season and week records above the slate, so only the
    // upcoming week promises a complete first card above the navigation.
    if (path === "/") {
      const cardBox = await card.boundingBox();
      const navigationBox = await page.getByRole("navigation", { name: "Main navigation" }).boundingBox();
      expect(cardBox).not.toBeNull();
      expect(navigationBox).not.toBeNull();
      expect(cardBox!.y + cardBox!.height).toBeLessThanOrEqual(navigationBox!.y);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await expect(card.locator("[data-pick]")).toHaveCount(2);
    await expect(card.getByRole("link", { name: "Matchup" })).toBeVisible();
  });

  test(`${path}: the first phone card clears a 34px home-indicator safe area`, async ({ page }) => {
    test.skip(path !== "/", "A graded week stacks two records above the slate, so only the upcoming week promises a first card above the navigation.");
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
    await page.getByRole("button", { name: "List", exact: true }).click();
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

test("phone cards keep venue beside the time and the line source through a filter rerender", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const card = page.locator("#game-3");
  await expect(card.getByText("Game details", { exact: true })).toHaveCount(0);
  await expect(card.getByText(/Los Angeles, CA/)).toBeVisible();
  await expect(card.getByText(/FanDuel/)).toBeVisible();
  await page.getByPlaceholder("Filter by team…").fill("Oregon");
  await expect(card.getByText(/Los Angeles, CA/)).toBeVisible();
  await expect(card.getByText(/FanDuel/)).toBeVisible();
});

test("collapsed biggest edges preserve every game anchor and selected category", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const biggestEdges = page.getByRole("region", { name: "Biggest edges" });
  await biggestEdges.locator("summary").click();
  // The collapsed and inline copies both render the links; only the shown copy counts.
  // Both categories render their links; only the selected category's column is shown.
  const shownAnchors = () =>
    biggestEdges.locator("a[href^='#game-']").filter({ visible: true }).evaluateAll((links) => links.map((link) => link.getAttribute("href")));
  // Five spread leans in the unchanged slate fixture.
  expect(await shownAnchors()).toEqual(["#game-3", "#game-9", "#game-1", "#game-8", "#game-5"]);
  await biggestEdges.getByRole("button", { name: "Totals", exact: true }).click();
  await expect(biggestEdges.getByRole("button", { name: "Totals", exact: true })).toHaveAttribute("aria-pressed", "true");
  // Five eligible total leans after switching category.
  expect(await shownAnchors()).toEqual(["#game-3", "#game-6", "#game-5", "#game-1", "#game-10"]);
  const firstAnchor = biggestEdges.locator("a[href^='#game-']").filter({ visible: true }).first();
  const target = await firstAnchor.getAttribute("href");
  await firstAnchor.click();
  expect(new URL(page.url()).hash).toBe(target);
});


test("biggest edges and highlights are open inline on desktop without a click", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  const biggestEdges = page.getByRole("region", { name: "Biggest edges" });
  await expect(biggestEdges.getByRole("heading", { name: "Biggest edges" })).toBeVisible();
  await expect(biggestEdges.getByRole("button", { name: "Totals", exact: true })).toBeHidden();
  await expect(biggestEdges.locator("a[href^='#game-']").filter({ visible: true })).toHaveCount(10);
  await page.goto("/?week=4");
  await expect(page.getByRole("region", { name: "Highlights" }).getByRole("heading", { name: "Highlights" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Highlights" }).locator("details")).toHaveCount(1);
  // One copy of the content: the summary is hidden on desktop and the content is forced open.
  await expect(page.getByRole("region", { name: "Highlights" }).locator("summary")).toBeHidden();
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

test("a graded week shows the week record beside the season record, with accuracy on wider screens", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?week=4");
  const record = page.getByRole("region", { name: "Record" });
  await expect(record.getByRole("heading", { name: "Season record before Week 4" })).toBeVisible();
  await expect(record.getByRole("heading", { name: /^Week \d+ record/ })).toBeVisible();
  await expect(record.getByRole("link", { name: "Season record" })).toHaveAttribute("href", "/model");
  // The accuracy line is dropped on phones to keep the slate close to the top.
  await expect(record.getByTestId("week-accuracy")).toBeHidden();
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(record.getByTestId("week-accuracy")).toContainText("95% interval coverage");
});

test("an upcoming week has no week record, and an in-progress week keeps phone cards inside the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("region", { name: "Record" }).getByRole("heading", { name: /^Week \d+ record/ })).toHaveCount(0);
  await page.goto("/?week=6");
  await expect(page.getByTestId("week-phase")).toHaveText("In progress");
  await expect(page.getByRole("region", { name: "Record" }).getByRole("heading", { name: "Week 6 record" })).toBeVisible();
  await expect(page.locator("li[id^='game-']")).toHaveCount(4);
  await expect(page.locator("details[open]")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
