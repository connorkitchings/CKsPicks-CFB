import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

test("status and presentation survive reload, browser history, historical week navigation and empty-filter recovery", async ({ page }) => {
  await gotoHydrated(page, "/?now=2026-10-20T12:00:00Z");
  const status = page.getByRole("group", { name: "Game status" });
  await status.getByRole("button", { name: "Results" }).click();
  await expect(page).toHaveURL(/status=results/);
  // Empty filter state recovery
  await expect(page.getByText("No games match these filters.")).toBeVisible();
  await page.getByRole("button", { name: "Show all games" }).click();
  await expect(page).toHaveURL(/status=all/);
  await expect(page.locator("li[id^='game-']")).toHaveCount(10);
  await page.reload();
  await expect(status.getByRole("button", { name: "All", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.goBack();
  await expect(status.getByRole("button", { name: "Results" })).toHaveAttribute("aria-pressed", "true");
  await page.goForward();
  await expect(status.getByRole("button", { name: "All", exact: true })).toHaveAttribute("aria-pressed", "true");

  // Historical week navigation opens All
  await status.getByRole("button", { name: "Upcoming" }).click();
  await expect(page).toHaveURL(/status=upcoming/);
  await page.locator("#week-select").selectOption("4");
  await expect(page).toHaveURL(/week=4/);
  await expect(page).toHaveURL(/status=all/);
  await expect(status.getByRole("button", { name: "All", exact: true })).toHaveAttribute("aria-pressed", "true");
});

test("card, list and market-comparison views show spread signs, totals and missing quotes without line-capture timestamps", async ({ page }) => {
  await gotoHydrated(page, "/");
  await expect(page.getByText("Forecast updated Sep 29, 7:24 PM ET", { exact: true })).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/line captured|captured unavailable|Sep 29, 5:15 PM ET/i);
  // Game 7 is missing total line
  await expect(page.locator("#game-7")).toContainText("No market line");

  // List view also omits line capture timestamps
  await page.getByRole("button", { name: "List", exact: true }).click();
  await expect(page.locator("body")).not.toContainText(/line captured|captured unavailable|Sep 29, 5:15 PM ET/i);

  // Market comparison view shows Spread and Total side by side without a target toggle
  await page.getByRole("group", { name: "Games analysis" }).getByRole("button", { name: "Model vs market" }).click();
  const marketRegion = page.getByRole("region", { name: "Model vs market" });
  await expect(marketRegion).toContainText("Spread is home margin in points (positive favors the home team; negative favors the away team); Total is combined points scored by both teams.");
  await expect(marketRegion).toContainText("10 of 10 filtered games have a comparable spread; 9 of 10 have a comparable total.");
  await expect(marketRegion).toContainText("Western Kentucky at Appalachian State");
  await expect(marketRegion).toContainText("Market Appalachian State -2.5 · Model Appalachian State -7.6");
  await expect(marketRegion).toContainText("DraftKings");
  await expect(marketRegion).not.toContainText("Line captured");
  await marketRegion.getByText(/Why 1 line is unavailable/).click();
  await expect(marketRegion).toContainText("LSU at Tennessee: Missing total line or model projection");
});

test("matchup deterministic facts, raw/adjusted evidence, completed context and lineage gates", async ({ page }) => {
  await gotoHydrated(page, "/matchup/1");
  await expect(page.getByRole("heading", { name: "What stands out" })).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/line captured|captured unavailable|Sep 29, 5:15 PM ET/i);
  const evidence = page.getByRole("region", { name: "Rating evidence" });
  await expect(evidence).toContainText("Raw PPP");
  await expect(evidence).toContainText("Adjusted PPP");
  await expect(evidence).toContainText("possessions · 20% prior weight");

  // Completed matchup shows frozen pregame context note
  await gotoHydrated(page, "/matchup/101");
  await expect(page.getByText("The forecast and supporting evidence below are frozen pregame context, not an actual-game statistical breakdown.")).toBeVisible();
});

test("awaiting action clears filters and reveals the target", async ({ page }) => {
  await gotoHydrated(page, "/?now=2026-10-20T12:00:00Z&status=results&q=nomatch&view=market");
  await page.getByRole("button", { name: /Awaiting published results/ }).click();
  await expect(page).toHaveURL(/status=all/);
  await expect(page).not.toHaveURL(/q=nomatch/);
  await expect(page.locator('[id^="game-"]').first()).toBeInViewport();
});

test("one offense selection controls factors, detail and export through resize", async ({ page }) => {
  await page.addInitScript(() => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    Object.assign(window, { __releaseFonts: release });
    Object.defineProperty(document.fonts, "ready", { get: () => gate, configurable: true });
  });
  await gotoHydrated(page, "/matchup/1");
  const selector = page.getByRole("group", { name: "Offense comparison" });
  const choice = selector.getByRole("button").nth(1);
  const name = (await choice.innerText()).trim();
  await choice.click();
  await expect(page.getByTestId("tale-of-the-tape")).toContainText(`${name} Offense`);
  await page.getByText("Full unit statistics", { exact: true }).click();
  await expect(page.getByRole("table", { name: new RegExp(`${name} Offense vs`) })).toBeVisible();
  await page.setViewportSize({ width: 320, height: 800 });
  await expect(choice).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("tale-of-the-tape")).not.toContainText("Tape Verdict");
  await page.getByTestId("share-download").click();
  const card = page.getByTestId("share-card");
  await expect(card).toContainText(`Selected offense: ${name}`);
  await expect(card).toHaveCSS("width", "1080px");
  await expect(card).toHaveCSS("height", "1350px");
  await page.evaluate(() => (window as unknown as { __releaseFonts: () => void }).__releaseFonts());
  await expect(page.getByTestId("share-controls")).toHaveAttribute("data-last-export", /2160.*2700/, { timeout: 15000 });
});

for (const width of [320, 390, 820, 1280]) {
  for (const theme of ["light", "dark"] as const) {
    test(`market comparisons fit ${width}px in ${theme} theme`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("theme", value), theme);
      await gotoHydrated(page, "/?view=market");
      const market = page.getByRole("region", { name: "Model vs market" });
      await expect(market).toContainText("Market Appalachian State -2.5 · Model Appalachian State -7.6");
      await expect(market).toContainText("Missing total line or model projection");
      await expect(market.getByRole("img").first()).toHaveAttribute("aria-label", /spread/);
      await expect(market.getByRole("img").nth(1)).toHaveAttribute("aria-label", /total points/);
      const summary = market.locator("summary");
      expect((await summary.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      await page.screenshot({ path: `/private/tmp/market-comparison-${width}-${theme}.png`, fullPage: true });
    });
  }
}

test("market-only publication never exposes model comparisons", async ({ page }) => {
  await gotoHydrated(page, "/?mode=market&view=market");
  await expect(page.getByRole("region", { name: "Model vs market" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Model vs market" })).toHaveCount(0);
});

test("missing both comparisons stays explained and empty filters remain usable", async ({ page }) => {
  await gotoHydrated(page, "/?view=market&fixture=no-comparisons");
  const market = page.getByRole("region", { name: "Model vs market" });
  await expect(market).toContainText("9 of 10 filtered games have a comparable spread; 8 of 10 have a comparable total.");
  await expect(market.locator("article").filter({ hasText: "Western Kentucky at Appalachian State" })).toHaveCount(0);
  const summary = market.locator("summary");
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(market).toContainText("Western Kentucky at Appalachian State: Missing spread line or model projection");
  await expect(market).toContainText("Western Kentucky at Appalachian State: Missing total line or model projection");
  await page.keyboard.press("Space");
  await expect(market.locator("details")).not.toHaveAttribute("open", "");
  await page.getByPlaceholder("Filter by team…").fill("Western Kentucky");
  await expect(market).toContainText("0 of 1 filtered games have a comparable spread; 0 of 1 have a comparable total.");
  await expect(market.getByRole("status")).toHaveText("No comparable forecasts and lines for these filters.");
  await expect(market.locator("article")).toHaveCount(0);
});
