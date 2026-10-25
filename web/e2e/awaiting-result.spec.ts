import { expect, test } from "@playwright/test";

// Week 5 is the unscored fixture week (10 games, one with a placeholder midnight kickoff on Oct 1);
// week 6 has two scored games and two unscored ones. `?now=` is honored only in UI test mode.
const WEEK_5_OVER = "2026-10-20T12:00:00Z";

test("a past unscored week reads Awaiting results and tags every game", async ({ page }) => {
  await page.goto(`/?now=${WEEK_5_OVER}`);
  const phase = page.getByTestId("week-phase");
  await expect(phase).toHaveText("Awaiting results");
  await expect(phase).toHaveAttribute("data-status", "awaiting");
  await expect(phase).toHaveAttribute("data-phase", "upcoming");
  await expect(page.getByTestId("awaiting-tag")).toHaveCount(10);
});

test("a partly scored past week is in progress and tags only its unscored games", async ({ page }) => {
  await page.goto(`/?week=6&now=${WEEK_5_OVER}`);
  await expect(page.getByTestId("week-phase")).toHaveText("In progress");
  await expect(page.getByTestId("awaiting-tag")).toHaveCount(2);
});

test("the awaiting tag also shows in the list layout", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`/?now=${WEEK_5_OVER}`);
  await page.locator('html[data-hydrated="true"]').waitFor({ state: "attached" });
  await page.getByRole("button", { name: "List" }).click();
  await expect(page.locator('ul[data-layout="list"]').first()).toBeVisible();
  await expect(page.getByTestId("awaiting-tag")).toHaveCount(10);
});

test("the awaiting tag fits on a 320px phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto(`/?now=${WEEK_5_OVER}`);
  await expect(page.getByTestId("awaiting-tag").first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
});

test("a game with a placeholder kickoff shows Time TBD, never 12:00 AM", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Time TBD")).toHaveCount(1);
  await expect(page.getByText(/12:00 AM/)).toHaveCount(0);
});

test("a Time TBD game is not awaiting until its Eastern day is over", async ({ page }) => {
  // Oct 1, 4 PM ET: the placeholder game's day is still running; only the Sep 26 game is past kickoff.
  await page.goto("/?now=2026-10-01T20:00:00Z");
  await expect(page.getByTestId("week-phase")).toHaveText("In progress");
  await expect(page.getByTestId("awaiting-tag")).toHaveCount(1);
});

test("the default clock shows no awaiting tags", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("week-phase")).toHaveText("Upcoming");
  await expect(page.getByTestId("awaiting-tag")).toHaveCount(0);
});

test("an unparseable now falls back to the default clock", async ({ page }) => {
  await page.goto("/?now=tomorrow");
  await expect(page.getByTestId("week-phase")).toHaveText("Upcoming");
});

test("the matchup hero tags a past unscored game, and only that", async ({ page }) => {
  await page.goto(`/matchup/1?now=${WEEK_5_OVER}`);
  await expect(page.getByTestId("awaiting-tag")).toHaveCount(1);
  await expect(page.getByTestId("awaiting-tag")).toHaveText("Awaiting result");
  await page.goto("/matchup/1");
  await expect(page.getByTestId("awaiting-tag")).toHaveCount(0);
  await page.goto(`/matchup/101?now=${WEEK_5_OVER}`);
  await expect(page.getByText(/Final: \d+–\d+/)).toBeVisible();
  await expect(page.getByTestId("awaiting-tag")).toHaveCount(0);
});

test("the matchup awaiting tag fits on a 320px phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto(`/matchup/1?now=${WEEK_5_OVER}`);
  await expect(page.getByTestId("awaiting-tag")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
});
