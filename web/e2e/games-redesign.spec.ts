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

test("card, list and market-comparison views show exact quote capture timestamps, spread signs, totals and missing quotes", async ({ page }) => {
  await gotoHydrated(page, "/");
  // Forecast updated timestamp is distinct from quote capture timestamp
  await expect(page.getByText("Forecast updated Sep 29, 7:24 PM ET", { exact: true })).toBeVisible();
  // Card view: game 1 has DraftKings/Bovada quotes captured at 5:15 PM ET; game 2 has no quote timestamp ("unavailable")
  await expect(page.locator("#game-1")).toContainText("Line captured: Sep 29, 5:15 PM ET");
  await expect(page.locator("#game-2")).toContainText("Line captured: unavailable");
  // Game 7 is missing total line
  await expect(page.locator("#game-7")).toContainText("No market line");

  // List view shows quote capture timestamps too
  await page.getByRole("button", { name: "List", exact: true }).click();
  await expect(page.locator("#game-1")).toContainText("Line captured: Sep 29, 5:15 PM ET");
  await expect(page.locator("#game-2")).toContainText("Line captured: unavailable");

  // Market comparison view
  await page.getByRole("group", { name: "Games analysis" }).getByRole("button", { name: "Model vs market" }).click();
  const marketRegion = page.getByRole("region", { name: "Model vs market" });
  await expect(marketRegion).toContainText("Home margin in points: positive favors the home team; negative favors the away team.");
  await expect(marketRegion).toContainText("Western Kentucky at Appalachian State");
  await expect(marketRegion).toContainText("Market +2.5 · Model +7.6");
  await expect(marketRegion).toContainText("DraftKings · Line captured: Sep 29, 5:15 PM ET");
  await expect(marketRegion).toContainText("Line captured: unavailable");

  // Switch to Total in Market comparison: LSU at Tennessee is listed under unavailable
  await marketRegion.getByRole("group", { name: "Market comparison target" }).getByRole("button", { name: "Total" }).click();
  await expect(marketRegion).toContainText("Combined points scored by both teams.");
  await expect(marketRegion).toContainText("9 of 10 filtered games have both a forecast and selected line.");
  await marketRegion.getByText(/Why 1 games are unavailable/).click();
  await expect(marketRegion).toContainText("LSU at Tennessee: Missing total line or model projection");
});

test("matchup deterministic facts, raw/adjusted evidence, completed context and lineage gates", async ({ page }) => {
  await gotoHydrated(page, "/matchup/1");
  await expect(page.getByRole("heading", { name: "What stands out" })).toBeVisible();
  await expect(page.getByText("Spread line captured: Sep 29, 5:15 PM ET · Total line captured: Sep 29, 5:15 PM ET")).toBeVisible();
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
