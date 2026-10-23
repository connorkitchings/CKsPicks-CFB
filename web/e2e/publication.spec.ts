import { expect, test, type Locator, type Page } from "@playwright/test";

const fits = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

/** Kept for locators that may match a phone-only and an inline copy of the same text. */
const shown = (locator: Locator) => locator.filter({ visible: true });

for (const width of [375, 420]) {
  test(`market publication stays bounded and usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/?mode=market");

    const comparison = page.getByRole("table", { name: "Market and results" });
    await expect(comparison).toBeVisible();
    await expect(comparison.getByRole("columnheader", { name: "Market" })).toBeVisible();
    // The market fixture game is final, so its card carries the graded Bet Result column.
    await expect(comparison.getByRole("columnheader", { name: "Bet Result" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "2026 Season Record" })).toHaveCount(0);
    await expect(page.getByRole("table", { name: "Market and model comparison" })).toHaveCount(0);
    await expect(page.getByText("Blitzkrieg")).toHaveCount(0);
    await page.locator("#week-select-phone").focus();
    await expect(page.locator("#week-select-phone")).toBeFocused();
    await expect(page.getByText("1 / 3", { exact: true })).toHaveCount(0);
    await page.locator("#week-select-phone").selectOption("1");
    await expect(page).toHaveURL(/week=1/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}

test("navigation exposes active tabs", async ({ page }) => {
  await page.goto("/");

  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.getByRole("link", { name: "Games" })).toHaveAttribute("aria-current", "page");
  await expect(nav.getByRole("link", { name: "Ratings" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Model" })).toBeVisible();
  for (const retired of ["Picks", "Results", "Performance", "Method"]) {
    await expect(nav.getByRole("link", { name: retired })).toHaveCount(0);
  }
});

test.describe("upcoming week (/)", () => {
  test("shows the phase, record, top leans and the full slate", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Week 5", exact: true })).toBeVisible();
    await expect(page.getByTestId("week-phase")).toHaveText("Upcoming");
    await expect(page.getByRole("region", { name: "Record" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Biggest edges" })).toBeVisible();
    // Nothing is graded yet: no highlights, no week record, no result sorts.
    await expect(page.getByRole("region", { name: "Highlights" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: /^Week \d+ record/ })).toHaveCount(0);
    await expect(page.locator("#slate-sort option[value='worstResult']")).toHaveCount(0);
    await expect(page.getByPlaceholder("Filter by team…")).toBeVisible();
    // Season track record over each scored week's top-5 spread/total leans.
    await expect(shown(page.getByText(/2026: 7–3–0 \(\d+\.\d%\)/))).toBeVisible();
    // Every week is browsable: the final, upcoming and in-progress fixture weeks.
    await expect(page.locator("#week-select option")).toHaveText(["Week 4", "Week 5", "Week 6"]);
    // Only one main navigation on the page.
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toHaveCount(1);
  });

  test("status line shows run state without a retrospective flag", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("Blitzkrieg")).toBeVisible();
    await expect(page.getByText("Frozen before kickoff")).toBeVisible();
    await expect(page.getByText(/Run published Sep 29/)).toBeVisible();
    await expect(page.getByText("Retrospective replay", { exact: true })).toHaveCount(0);
  });

  test("shows each lean's direction and model prediction once, without a second market/model table", async ({ page }) => {
    await page.goto("/");

    // Edge sits in parentheses after the model's number; no separate "Edge" label.
    await expect(page.getByText("(+5.1)").first()).toBeVisible();
    await expect(page.getByText(/^Edge \d/)).toHaveCount(0);
    // Each bet cell: the pick with its sportsbook, then one line with the model's number and the edge.
    const appState = page.locator("#game-1");
    await expect(appState).toContainText("Appalachian State -2.5");
    await expect(appState).toContainText("DraftKings");
    await expect(appState).toContainText(/Model: [+-]?\d/);
    await expect(appState).toContainText("Under 57.5");
    await expect(appState).toContainText("Bovada");
    await expect(appState).toContainText("Model: 54.1");
    // Provider keys are shown as sportsbook names, inside the bet box.
    await expect(shown(page.locator("#game-3").getByText(/FanDuel/))).toBeVisible();
    // A game with no recorded source shows the model's number but no invented book.
    const oklahoma = page.locator("#game-9");
    await expect(oklahoma).toContainText("Oklahoma +4.0");
    await expect(oklahoma).toContainText(/Model: [+-]?\d/);
    await expect(oklahoma.getByText(/DraftKings|FanDuel|Bovada|BetMGM|ESPN Bet|Caesars/)).toHaveCount(0);
    // The per-card edge footnote and the Game details block are gone.
    await expect(page.getByText("The number in parentheses after the model is its edge")).toHaveCount(0);
    await expect(page.getByText("Game details", { exact: true })).toHaveCount(0);
    await expect(page.getByText(/wins by more than|loses by under|total above|total below|best line:/)).toHaveCount(0);
    // The old Market / Model grid is gone from the cards.
    await expect(page.locator("main").getByText("Market", { exact: true })).toHaveCount(0);
    await expect(page.locator("main").getByText("Model", { exact: true })).toHaveCount(0);
  });

  test("top of the page shows the season record, centered with no break-even bars", async ({ page }) => {
    await page.goto("/");

    const record = page.getByRole("region", { name: "Record" });
    await expect(record.getByRole("heading", { name: "Season record before Week 5" })).toBeVisible();
    await expect(record.getByRole("link", { name: "Season record" })).toHaveAttribute("href", "/model");
    await expect(record.getByText("93–103–3", { exact: true })).toBeVisible();
    await expect(record.getByText("47.4%")).toBeVisible();

    await expect(record.getByText(/pts vs 52\.4% break-even/)).toHaveCount(0);
    await expect(record.getByText(/Average miss/)).toHaveCount(0);
    await expect(record.getByText(/read it as a back-test/)).toHaveCount(0);
  });

  test("team filter, list view and an empty result work", async ({ page }) => {
    await page.goto("/");
    const games = page.locator("li[id^='game-']");
    await expect(games).toHaveCount(10);

    await page.getByPlaceholder("Filter by team…").fill("Oregon");
    await expect(games).toHaveCount(1);
    await expect(games.first()).toHaveAttribute("id", "game-3");

    await page.getByPlaceholder("Filter by team…").fill("zzz");
    await expect(games).toHaveCount(0);

    await page.getByPlaceholder("Filter by team…").fill("");
    await expect(games).toHaveCount(10);

    const confFilter = page.getByTestId("conference-filter");
    await expect(confFilter).toBeVisible();
    await confFilter.selectOption("Sun Belt");
    await expect(games).toHaveCount(1);
    await expect(games.first()).toHaveAttribute("id", "game-1");
    await confFilter.selectOption("all");
    await expect(games).toHaveCount(10);

    await page.getByRole("button", { name: "List", exact: true }).click();
    await expect(page.getByRole("button", { name: "List", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("button", { name: "Grid", exact: true })).toHaveAttribute("aria-pressed", "false");
    await expect(games).toHaveCount(10);
    expect(await fits(page)).toBe(true);
  });

  test("fits a 390px phone without horizontal scroll", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto("/");
    expect(await fits(page)).toBe(true);
  });
});

for (const path of ["/", "/?week=4"]) {
  test(`${path}: no home tag, and every game lists away on top and home on the bottom`, async ({ page }) => {
    await page.goto(path);

    // The "home" tag is gone; the bottom team is the home team.
    await expect(page.getByText("home", { exact: true })).toHaveCount(0);

    for (const view of ["Grid", "List"]) {
      await page.getByRole("button", { name: view, exact: true }).click();
      const pairs = await page.locator("li[id^='game-']").evaluateAll((cards) =>
        cards.map((card) => {
          const sides = [...card.querySelectorAll("[data-side]")];
          return {
            order: sides.map((el) => el.getAttribute("data-side")),
            awayAboveHome:
              sides.length === 2 &&
              sides[0].getBoundingClientRect().top < sides[1].getBoundingClientRect().top,
          };
        }),
      );
      expect(pairs.length).toBeGreaterThan(0);
      for (const pair of pairs) {
        expect(pair.order).toEqual(["away", "home"]);
        expect(pair.awayAboveHome).toBe(true);
      }
    }
  });
}

test.describe("game location next to the time", () => {
  test("picks cards show city and state, a neutral-site note, and nothing when unknown", async ({ page }) => {
    await page.goto("/");

    await expect(shown(page.locator("#game-3").getByText("· Los Angeles, CA"))).toBeVisible();
    await expect(shown(page.locator("#game-5").getByText("· State College, PA"))).toBeVisible();
    // Neutral-site game: location plus a note (the "home" team is arbitrary there).
    await expect(shown(page.locator("#game-8").getByText("· Orlando, FL"))).toBeVisible();
    await expect(shown(page.locator("#game-8").getByText("Neutral site"))).toBeVisible();
    await expect(shown(page.locator("#game-3").getByText("Neutral site"))).toHaveCount(0);
    // No recorded location: no placeholder text.
    await expect(page.locator("#game-2")).not.toContainText(/, [A-Z]{2}\b/);
    await expect(page.locator("#game-2").getByText("·")).toHaveCount(0);

    await page.getByRole("button", { name: "List", exact: true }).click();
    await expect(shown(page.locator("#game-3").getByText("Los Angeles, CA"))).toBeVisible();
    await expect(shown(page.locator("#game-8").getByText("· Neutral"))).toBeVisible();
  });

  test("graded cards show the venue beside the date", async ({ page }) => {
    await page.goto("/?week=4");

    await expect(shown(page.locator("#game-101").getByText("· Ann Arbor, MI"))).toBeVisible();
    await expect(shown(page.locator("#game-107").getByText("· Tallahassee, FL"))).toBeVisible();
    await page.getByRole("button", { name: "List", exact: true }).click();
    await expect(shown(page.locator("#game-101").getByText("Ann Arbor, MI"))).toBeVisible();
  });

  test("a long location truncates instead of overflowing a phone", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/");
    expect(await fits(page)).toBe(true);
  });
});

test.describe("long team names keep the full pick visible on a small phone", () => {
  test("picks: Appalachian State -2.5 is not truncated at 360px", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/");
    await expect(page.locator("#game-1").getByText("Appalachian State -2.5", { exact: true })).toBeVisible();
    const clipped = await page.locator("[data-pick]").evaluateAll((els) =>
      els.filter((el) => el.scrollWidth > el.clientWidth).map((el) => el.textContent),
    );
    expect(clipped).toEqual([]);
    expect(await fits(page)).toBe(true);
  });

  test("final week: Southern Mississippi +4.0 is not truncated at 360px", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/?week=4");
    await expect(page.locator("#game-108").getByText("Southern Mississippi +4.0", { exact: true })).toBeVisible();
    const clipped = await page.locator("[data-pick]").evaluateAll((els) =>
      els.filter((el) => el.scrollWidth > el.clientWidth).map((el) => el.textContent),
    );
    expect(clipped).toEqual([]);
    expect(await fits(page)).toBe(true);
  });
});

test("footer carries the team-logo trademark attribution", async ({ page }) => {
  for (const path of ["/", "/?week=4"]) {
    await page.goto(path);
    await expect(
      page.getByText("Team names and logos are trademarks of their respective schools and owners, shown for identification only."),
    ).toBeVisible();
  }
});

test.describe("final week (/?week=4)", () => {
  test("shows the phase, both records, highlights and the full slate", async ({ page }) => {
    await page.goto("/?week=4");

    await expect(page.getByRole("heading", { name: "Week 4", exact: true })).toBeVisible();
    await expect(page.getByTestId("week-phase")).toHaveText("Final");
    await expect(page.getByRole("region", { name: "Record" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Season record before Week 4" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Week 4 record" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Highlights" })).toBeVisible();
    // A finished week has no upcoming leans to rank.
    await expect(page.getByRole("region", { name: "Biggest edges" })).toHaveCount(0);
    await expect(page.getByRole("status")).toHaveText("Showing 9 of 9 games");
    await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Games" })).toHaveAttribute("aria-current", "page");
  });

  test("status line shows the scored run with a retrospective flag", async ({ page }) => {
    await page.goto("/?week=4");

    await expect(page.getByText("Scored")).toBeVisible();
    await expect(page.getByText("Retrospective replay", { exact: true })).toBeVisible();
  });

  test("the week record sits beside the season record; graded cards show the pick and the model's number", async ({ page }) => {
    await page.goto("/?week=4");

    const record = page.getByRole("region", { name: "Record" });
    await expect(shown(record.getByText("this slate · small sample"))).toBeVisible();
    await expect(shown(record.getByText("4–3–1"))).toBeVisible();
    await expect(record.getByText("93–103–3", { exact: true })).toBeVisible();
    await expect(record.getByText(/pts vs 52\.4% break-even/)).toHaveCount(0);
    await expect(record.getByText(/Live/)).toHaveCount(0);
    const ohioState = page.locator("li[id^='game-']").filter({ hasText: "Ohio State" }).first();
    await expect(ohioState).toContainText("Ohio State -6.0");
    await expect(ohioState).toContainText(/Model: [+-]?\d/);
    await expect(ohioState.getByText("Win", { exact: true }).first()).toBeVisible();
  });

  test("team search narrows the slate and cards show a graded badge", async ({ page }) => {
    await page.goto("/?week=4");

    const count = async () => {
      const text = (await page.getByText(/Showing \d+ of 9 games/).innerText()) ?? "";
      return Number(/Showing (\d+) of/.exec(text)?.[1]);
    };
    await page.getByPlaceholder("Filter by team…").fill("Ohio State");
    const filtered = await count();
    expect(filtered).toBe(1);
    await expect(page.locator("li[id^='game-']").first().getByText("Win", { exact: true }).first()).toBeVisible();

    await page.getByPlaceholder("Filter by team…").fill("");
    expect(await count()).toBe(9);
  });

  test("sort by biggest miss, list view and phone width all fit", async ({ page }) => {
    await page.goto("/?week=4");
    await page.locator("#slate-sort").selectOption("worstResult");
    await page.getByRole("button", { name: "List", exact: true }).click();
    expect(await fits(page)).toBe(true);

    await page.setViewportSize({ width: 390, height: 800 });
    await expect(page.getByRole("button", { name: "Grid", exact: true })).toBeHidden();
    await expect(page.locator("ul[data-layout]").first()).toHaveAttribute("data-layout", "grid");
    expect(await fits(page)).toBe(true);
  });

  test("week navigation moves between the final, upcoming and in-progress weeks", async ({ page }) => {
    await page.goto("/?week=4");
    await page.locator("#week-select").selectOption("5");
    await expect(page).toHaveURL(/week=5/);
    await expect(page.getByTestId("week-phase")).toHaveText("Upcoming");
    await page.locator("#week-select").selectOption("6");
    await expect(page.getByTestId("week-phase")).toHaveText("In progress");
  });
});

test.describe("in-progress week (/?week=6)", () => {
  test("shows leans for unplayed games and results for finished ones", async ({ page }) => {
    await page.goto("/?week=6");

    await expect(page.getByTestId("week-phase")).toHaveText("In progress");
    await expect(page.getByRole("region", { name: "Biggest edges" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Highlights" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Week 6 record" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Season record before Week 6" })).toBeVisible();
    await expect(page.locator("li[id^='game-']")).toHaveCount(4);

    // Finished games carry a graded badge and a Final marker; unplayed ones show neither.
    const finished = page.locator("#game-201");
    await expect(finished).toContainText("Final");
    await expect(finished.getByText("Win", { exact: true }).first()).toBeVisible();
    const upcoming = page.locator("#game-203");
    await expect(upcoming).not.toContainText("Final");
    await expect(upcoming.getByText(/^(Win|Loss|Push)$/)).toHaveCount(0);
    await expect(upcoming).toContainText(/Model: [+-]?\d/);
  });

  test("the week record counts only the graded games, and result sorts are offered", async ({ page }) => {
    await page.goto("/?week=6");

    const record = page.getByRole("region", { name: "Record" });
    // Both finished games covered the spread.
    await expect(shown(record.getByText("2–0–0"))).toBeVisible();
    await expect(page.locator("#slate-sort option[value='worstResult']")).toHaveCount(1);
    await page.locator("#slate-sort").selectOption("bestResult");
    await expect(page.locator("li[id^='game-']")).toHaveCount(4);
  });

  test("fits a 390px phone without horizontal scroll", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto("/?week=6");
    expect(await fits(page)).toBe(true);
  });
});
