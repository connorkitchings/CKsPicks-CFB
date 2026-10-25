import { expect, test, type Page } from "@playwright/test";
import { gotoHydrated } from "./helpers";

const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);

/** Bounding box of a team-page card, found by the id of its heading. */
async function card(page: Page, id: string) {
  const b = await page.locator(`section[aria-labelledby="${id}"]`).boundingBox();
  if (!b) throw new Error(`no box for ${id}`);
  return b;
}

async function hero(page: Page) {
  const b = await page.getByTestId("team-hero").boundingBox();
  if (!b) throw new Error("no hero box");
  return b;
}

const heading = (page: Page, name: string) => page.getByRole("heading", { level: 2, name, exact: true });
const weeklyRatings = (page: Page) => page.getByText("Weekly ratings", { exact: true });

test.describe("team pages (fixture mode)", () => {
  test("the desktop hero spans the page above a main column and a side column", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await gotoHydrated(page, "/teams/Texas");
    await expect(page.getByRole("heading", { level: 1, name: "Texas" })).toBeVisible();
    await expect(page).toHaveTitle(/Texas · Team page/);
    await expect(page.getByRole("link", { name: "← All ratings" })).toHaveAttribute("href", "/ratings");

    const h = await hero(page);
    const schedule = await card(page, "team-games");
    const gameLog = await card(page, "team-game-log");
    const trend = await card(page, "team-rating-trend");
    const resume = await card(page, "team-resume");
    const unit = await card(page, "team-unit-profile");

    for (const below of [schedule, gameLog, trend, resume, unit]) expect(below.y).toBeGreaterThanOrEqual(h.y + h.height - 1);
    expect(h.width).toBeGreaterThanOrEqual(schedule.width + trend.width);
    for (const main of [schedule, gameLog]) {
      for (const side of [trend, resume, unit]) expect(main.x + main.width).toBeLessThanOrEqual(side.x + 1);
    }
    expect(schedule.width).toBeGreaterThan(trend.width);
    expect(gameLog.y).toBeGreaterThan(schedule.y);
    expect(resume.y).toBeGreaterThan(trend.y);
    expect(unit.y).toBeGreaterThan(resume.y);
    expect(await noOverflow(page)).toBe(true);
  });

  test("the desktop schedule is a lines-and-results table with its record line", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await gotoHydrated(page, "/teams/Texas");
    await expect(heading(page, "Schedule · lines and results")).toBeVisible();
    const table = page.getByRole("table", { name: "Lines and results" });
    await expect(table).toBeVisible();
    await expect(page.getByRole("list", { name: "Schedule" })).toBeHidden();
    const record = page.getByTestId("schedule-record");
    await expect(record).toContainText("ATS (W–L) 2–1–1 · 67% cover");
    await expect(record).toContainText("O/U (Over–Under) 1–3 · 25% over");
    await expect(record).not.toContainText("Model picked the winner");
    await expect(table.getByRole("columnheader")).toHaveText(["Wk", "Date", "Opponent", "Line", "Total", "Result", "ATS", "O/U", "Matchup"]);
    await expect(table.getByTestId("schedule-next-row")).toContainText("Ohio State");
  });

  test("the desktop model card lists each pick with its mark and the model record", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await gotoHydrated(page, "/teams/Texas");
    await expect(heading(page, "Model on this team")).toBeVisible();
    const schedule = await card(page, "team-games");
    const model = await card(page, "team-model");
    const gameLog = await card(page, "team-game-log");
    expect(model.y).toBeGreaterThanOrEqual(schedule.y + schedule.height - 1);
    expect(gameLog.y).toBeGreaterThanOrEqual(model.y + model.height - 1);
    const table = page.getByRole("table", { name: "Model picks" });
    await expect(table.getByRole("columnheader")).toHaveText(["Wk", "Opponent", "ATS pick", "O/U pick", "Winner"]);
    const row = (name: string) => table.getByRole("row").filter({ hasText: name });
    await expect(row("Ohio State").first()).toContainText("Texas -2.5");
    await expect(row("Ohio State").first().getByRole("img", { name: "Hit" })).toHaveCount(2);
    await expect(row("Ohio State").first().getByRole("img", { name: "Miss" })).toHaveCount(1);
    await expect(row("Georgia")).toContainText("Texas -6.5");
    await expect(row("Georgia").getByRole("img", { name: "Miss" })).toHaveCount(2);
    await expect(row("Georgia").getByRole("img", { name: "Hit" })).toHaveCount(1);
    await expect(row("Alabama")).toContainText("No pick");
    await expect(row("LSU").getByRole("img", { name: "Push" })).toHaveCount(1);
    expect(await noOverflow(page)).toBe(true);
    await expect(row("Rice")).toContainText("No line");
    const record = page.getByTestId("model-record");
    await expect(record).toContainText("ATS (W–L) 1–1–1 · 50%");
    await expect(record).toContainText("O/U 1–2 · 33%");
    await expect(record).toContainText("Model picked the winner 2–1 · 67%");
    await expect(page.getByText("Model picks use the pregame forecast for each game. Display only — not betting advice.")).toBeVisible();
  });

  test("on desktop both unit sections show their rows without a tap", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await gotoHydrated(page, "/teams/Texas");
    await expect(page.getByTestId("unit-offense").getByRole("term").first()).toBeVisible();
    await expect(page.getByTestId("unit-defense").getByRole("term").first()).toBeVisible();
    await expect(page.getByTestId("unit-full-stats").getByText("Full stats (12)")).toBeVisible();
  });

  for (const width of [390, 320]) {
    test(`the phone page is one column in order and fits at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await gotoHydrated(page, "/teams/Texas");
      await expect(page.getByTestId("app-bar").getByRole("link", { name: "Back to ratings" })).toHaveAttribute("href", "/ratings");
      await expect(page.getByTestId("app-bar-title")).toHaveText("TEX");
      await expect(page.getByRole("link", { name: "← All ratings" })).toBeHidden();
      await expect(page.getByRole("heading", { level: 1, name: "Texas" })).toBeVisible();

      const ids = ["team-games", "team-model", "team-game-log", "team-rating-trend", "team-resume", "team-unit-profile"];
      const boxes = [await hero(page)];
      for (const id of ids) boxes.push(await card(page, id));
      for (let i = 1; i < boxes.length; i++) {
        expect(boxes[i].y, `${ids[i - 1]} below the previous module`).toBeGreaterThanOrEqual(boxes[i - 1].y + boxes[i - 1].height - 1);
        expect(Math.abs(boxes[i].x - boxes[0].x), `${ids[i - 1]} aligned with the hero`).toBeLessThanOrEqual(2);
      }
      await expect(page.getByRole("table", { name: "Lines and results" })).toBeHidden();
      await expect(page.getByRole("list", { name: "Schedule" }).getByRole("listitem")).toHaveCount(6);
      await expect(page.getByLabel("Next game")).toContainText(/at\s*Ohio State/);
      const picks = page.getByRole("list", { name: "Model picks" });
      await expect(picks).toBeVisible();
      await expect(page.getByRole("table", { name: "Model picks" })).toBeHidden();
      await expect(picks.getByRole("listitem")).toHaveCount(6);
      const overflowing = await picks.evaluate((el) => [...el.querySelectorAll("li")].filter((li) => li.scrollWidth > li.clientWidth).length);
      expect(overflowing, "model rows fit without sideways scrolling").toBe(0);
      expect(await noOverflow(page)).toBe(true);
    });
  }

  test("the next-game card skips a game that kicked off without a score", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    // Texas's week 4 game (Sep 26) is past and unscored; week 5 (Oct 3) is still ahead.
    await gotoHydrated(page, "/teams/Texas?now=2026-09-30T12:00:00Z");
    await expect(page.getByLabel("Next game")).toContainText(/vs\s*Rice/);
    await expect(page.getByLabel("Next game")).not.toContainText("Ohio State");
    // Once every remaining game has passed, the card is hidden.
    await gotoHydrated(page, "/teams/Texas?now=2026-10-20T12:00:00Z");
    await expect(page.getByLabel("Next game")).toHaveCount(0);
  });

  test("every module is present for a team with games", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await gotoHydrated(page, "/teams/Texas");
    const summary = page.getByTestId("team-hero");
    await expect(summary.getByTitle("Offense rating and rank")).toBeVisible();
    await expect(summary.getByTestId("rating-change")).toBeVisible();
    await expect(page.getByLabel("Next game")).toContainText(/at\s*Ohio State/);
    for (const name of ["Schedule · lines and results", "Model on this team", "Game log", "Rating trend", "Résumé", "Unit profile"]) await expect(heading(page, name)).toBeVisible();
    const resume = page.locator('section[aria-labelledby="team-resume"]');
    for (const label of ["Strength of record", /^SOS played \(\d+\)$/, /^SOS remaining \(\d+\)$/, "SOS full season", "Wins above average"]) {
      await expect(resume.getByRole("term").filter({ hasText: label })).toBeVisible();
    }
    await expect(page.getByTestId("unit-offense")).toBeVisible();
    await expect(page.getByTestId("unit-defense")).toBeVisible();
    await expect(page.getByTestId("unit-full-stats")).toBeVisible();
    await expect(weeklyRatings(page)).toBeVisible();
  });

  test("the game log toggles between success rate and points", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await gotoHydrated(page, "/teams/Texas");
    const toggle = page.getByTestId("game-log-measure");
    const chart = (name: RegExp) => page.getByRole("img", { name });
    await expect(chart(/^Success rate by game/)).toBeVisible();
    await toggle.getByRole("button", { name: "Points" }).click();
    await expect(chart(/^Points by game/)).toBeVisible();
    await expect(chart(/^Success rate by game/)).toHaveCount(0);
    await toggle.getByRole("button", { name: "Success rate" }).click();
    await expect(chart(/^Success rate by game/)).toBeVisible();
  });

  test("the rating trend toggles between rating and rank", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await gotoHydrated(page, "/teams/Texas");
    const toggle = page.getByTestId("trend-measure");
    const chart = (name: RegExp) => page.getByRole("img", { name });
    await expect(chart(/^Overall rating by week/)).toBeVisible();
    await toggle.getByRole("button", { name: "Rank" }).click();
    await expect(chart(/^Overall rank by week/)).toBeVisible();
    await expect(chart(/^Overall rating by week/)).toHaveCount(0);
    await toggle.getByRole("button", { name: "Rating" }).click();
    await expect(chart(/^Overall rating by week/)).toBeVisible();
  });

  test("on a phone the unit sections start closed and open on tap", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await gotoHydrated(page, "/teams/Texas");
    for (const id of ["unit-offense", "unit-defense"]) {
      const section = page.getByTestId(id);
      await expect(section).not.toHaveAttribute("open", "");
      await expect(section.locator("summary")).toContainText(/PPA\/poss\s*[-−]?\d/);
      await expect(section.getByRole("term").first()).toBeHidden();
      await section.locator("summary").click();
      await expect(section).toHaveAttribute("open", "");
      await expect(section.getByRole("term").first()).toBeVisible();
    }
  });

  test("the weekly ratings disclosure reveals the history table", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await gotoHydrated(page, "/teams/Texas");
    const table = page.getByRole("table").filter({ has: page.getByRole("columnheader", { name: "Week" }) });
    await expect(table).toBeHidden();
    await weeklyRatings(page).click();
    await expect(table).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Overall" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Uncertainty" })).toBeVisible();
    await expect(table.getByRole("row")).toHaveCount(3);
  });

  for (const width of [1280, 390, 320]) {
    test(`the weekly ratings table fits its card at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await gotoHydrated(page, "/teams/Texas");
      await weeklyRatings(page).click();
      const table = page.getByRole("table").filter({ has: page.getByRole("columnheader", { name: "Week" }) });
      await expect(table).toBeVisible();
      const fits = await table.evaluate((el) => {
        const box = el.closest("[data-card]") as HTMLElement;
        const cell = el.querySelector("tbody td") as HTMLElement;
        return { scroll: box.scrollWidth <= box.clientWidth, oneLine: cell.getBoundingClientRect().height < 48 };
      });
      expect(fits.scroll, "the card has nothing to scroll sideways").toBe(true);
      expect(fits.oneLine, "the week cell stays on one line").toBe(true);
      await expect(table.getByRole("cell", { name: "Wk 1" })).toBeVisible();
      expect(await noOverflow(page)).toBe(true);
    });
  }

  test("Matchup links from the hero and the schedule open the matchup", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await gotoHydrated(page, "/teams/Texas");
    await page.getByLabel("Next game").getByTestId("matchup-link").click();
    await expect(page).toHaveURL(/\/matchup\/\d+/);

    await gotoHydrated(page, "/teams/Texas");
    await page.getByTestId("schedule-matchup-link").first().click();
    await expect(page).toHaveURL(/\/matchup\/\d+/);

    await page.setViewportSize({ width: 390, height: 844 });
    await gotoHydrated(page, "/teams/Texas");
    await page.getByRole("list", { name: "Schedule" }).getByTestId("matchup-link").first().click();
    await expect(page).toHaveURL(/\/matchup\/\d+/);
  });

  for (const width of [1280, 390]) {
    test(`a team without games shows its hero, résumé and notices at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await gotoHydrated(page, "/teams/Ohio%20State");
      await expect(page.getByRole("heading", { level: 1, name: "Ohio State" })).toBeVisible();
      await expect(page.getByTestId("team-hero")).toBeVisible();
      await expect(heading(page, "Résumé")).toBeVisible();
      await expect(page.getByText("Unit stats are not available right now.")).toBeVisible();
      await expect(page.getByLabel("Next game")).toHaveCount(0);
      await expect(weeklyRatings(page)).toHaveCount(0);
      expect(await noOverflow(page)).toBe(true);
      expect(errors).toEqual([]);
    });
  }

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
