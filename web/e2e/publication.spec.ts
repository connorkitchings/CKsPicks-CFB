import { expect, test } from "@playwright/test";

const fits = (page: import("@playwright/test").Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

for (const width of [375, 420]) {
  test(`market publication stays bounded and usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/?mode=market");

    const comparison = page.getByRole("table", { name: "Market and results" });
    await expect(comparison).toBeVisible();
    await expect(comparison.getByRole("columnheader", { name: "Market" })).toBeVisible();
    // Picks is forward-looking: results belong to the Results tab.
    await expect(comparison.getByRole("columnheader", { name: "Bet Result" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "2026 Season Record" })).toHaveCount(0);
    await expect(page.getByRole("table", { name: "Market and model comparison" })).toHaveCount(0);
    await expect(page.getByText("Blitzkrieg")).toHaveCount(0);
    await page.locator("#week-select").focus();
    await expect(page.locator("#week-select")).toBeFocused();
    await expect(page.getByText("1 / 3", { exact: true })).toHaveCount(0);
    await page.locator("#week-select").selectOption("1");
    await expect(page).toHaveURL(/week=1/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}

test("market results tab keeps the Bet Result column", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await page.goto("/results?mode=market");

  const comparison = page.getByRole("table", { name: "Market and results" }).first();
  await expect(comparison).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Market" })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "Bet Result" })).toBeVisible();
});

test("navigation exposes active tabs", async ({ page }) => {
  await page.goto("/");

  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.getByRole("link", { name: "Picks" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Results" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Ratings" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Performance" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Method" })).toHaveCount(0);
});

test.describe("picks slate (/)", () => {
  test("shows record, top leans and the full slate", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("region", { name: "Record" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Best bets" })).toBeVisible();
    await expect(page.getByPlaceholder("Filter by team…")).toBeVisible();
    // Season track record over each scored week's top-5 spread/total leans.
    await expect(page.getByText(/Best bets: 7–3–0 this season/)).toBeVisible();
    // Single-week fixture: no week selector on the slate.
    await expect(page.locator("#week-select")).toHaveCount(0);
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

    // Edge sits in parentheses next to the pick; no separate "Edge" label.
    await expect(page.getByText("(5.1)").first()).toBeVisible();
    await expect(page.getByText(/^Edge \d/)).toHaveCount(0);
    // One line under the pick: just the model's prediction, no explanatory sentence.
    await expect(page.getByText(/^model: Appalachian State by 7\.6 · best line: DraftKings$/).first()).toBeVisible();
    await expect(page.getByText(/^model: 54\.1 · best line: Bovada$/).first()).toBeVisible();
    // Provider keys are shown as sportsbook names.
    await expect(page.getByText(/best line: FanDuel/).first()).toBeVisible();
    // A game with no recorded source shows the model's number but no invented book.
    await expect(page.locator("#game-9").getByText("model: Oklahoma by 2.0", { exact: true })).toBeVisible();
    await expect(page.locator("#game-9").getByText(/best line/)).toHaveCount(0);
    await expect(page.getByText(/wins by more than|loses by under|total above|total below/)).toHaveCount(0);
    // The old Market / Model grid is gone from the cards.
    await expect(page.getByText("Market", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Model", { exact: true })).toHaveCount(0);
  });

  test("top of the page shows the season record, centered with no break-even bars", async ({ page }) => {
    await page.goto("/");

    const record = page.getByRole("region", { name: "Record" });
    await expect(record.getByRole("heading", { name: "How the model is doing" })).toBeVisible();
    await expect(record.getByText(/Season \(\d+ games\)/)).toBeVisible();
    await expect(record.getByText("93–103–3")).toBeVisible();
    await expect(record.getByText("47.4%")).toBeVisible();
    await expect(record.getByText("196 decided")).toBeVisible();
    await expect(record.getByText(/pts vs 52\.4% break-even/)).toHaveCount(0);
    await expect(record.getByText(/Average miss/)).toHaveCount(0);
    await expect(record.getByText(/read it as a back-test/)).toHaveCount(0);
  });

  test("leans only, sort and list view work", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("button", { name: /Leans only/ }).click();
    await expect(page.getByText("Showing 8 of 10 games")).toBeVisible();

    await page.locator("#slate-sort").selectOption("bestEdge");
    // Flat list, biggest edge first (Oregon @ USC total edge 8.7).
    await expect(page.locator("li[id^='game-']").first()).toHaveAttribute("id", "game-3");

    await page.getByRole("button", { name: "list", exact: true }).click();
    await expect(page.getByRole("button", { name: "list", exact: true })).toHaveAttribute("aria-pressed", "true");
    expect(await fits(page)).toBe(true);
  });

  test("fits a 390px phone without horizontal scroll", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto("/");
    expect(await fits(page)).toBe(true);
  });
});

for (const path of ["/", "/results"]) {
  test(`${path}: no home tag, and every game lists away on top and home on the bottom`, async ({ page }) => {
    await page.goto(path);

    // The "home" tag is gone; the bottom team is the home team.
    await expect(page.getByText("home", { exact: true })).toHaveCount(0);

    for (const view of ["grid", "list"]) {
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

    await expect(page.locator("#game-3").getByText("· Los Angeles, CA")).toBeVisible();
    await expect(page.locator("#game-5").getByText("· State College, PA")).toBeVisible();
    // Neutral-site game: location plus a note (the "home" team is arbitrary there).
    await expect(page.locator("#game-8").getByText("· Orlando, FL")).toBeVisible();
    await expect(page.locator("#game-8").getByText("Neutral site")).toBeVisible();
    await expect(page.locator("#game-3").getByText("Neutral site")).toHaveCount(0);
    // No recorded location: no placeholder text.
    await expect(page.locator("#game-2")).not.toContainText(/, [A-Z]{2}\b/);
    await expect(page.locator("#game-2").getByText("·")).toHaveCount(0);

    await page.getByRole("button", { name: "list", exact: true }).click();
    await expect(page.locator("#game-3").getByText("Los Angeles, CA")).toBeVisible();
    await expect(page.locator("#game-8").getByText("· Neutral")).toBeVisible();
  });

  test("results cards show the venue beside the date", async ({ page }) => {
    await page.goto("/results");

    await expect(page.locator("#game-101").getByText("· Ann Arbor, MI")).toBeVisible();
    await expect(page.locator("#game-107").getByText("· Tallahassee, FL")).toBeVisible();
    await page.getByRole("button", { name: "list", exact: true }).click();
    await expect(page.locator("#game-101").getByText("Ann Arbor, MI")).toBeVisible();
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

  test("results: Southern Mississippi +4.0 is not truncated at 360px", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/results");
    await expect(page.locator("#game-108").getByText("Southern Mississippi +4.0", { exact: true })).toBeVisible();
    const clipped = await page.locator("[data-pick]").evaluateAll((els) =>
      els.filter((el) => el.scrollWidth > el.clientWidth).map((el) => el.textContent),
    );
    expect(clipped).toEqual([]);
    expect(await fits(page)).toBe(true);
  });
});

test("footer carries the team-logo trademark attribution", async ({ page }) => {
  for (const path of ["/", "/results"]) {
    await page.goto(path);
    await expect(
      page.getByText("Team names and logos are trademarks of their respective schools and owners, shown for identification only."),
    ).toBeVisible();
  }
});

test.describe("results slate (/results)", () => {
  test("shows week and season records, highlights and the full slate", async ({ page }) => {
    await page.goto("/results");

    await expect(page.getByRole("region", { name: "Record" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Week 4" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Highlights" })).toBeVisible();
    await expect(page.getByText("Showing 9 of 9 games")).toBeVisible();
    await expect(page.getByRole("link", { name: "Results" })).toHaveAttribute("aria-current", "page");
  });

  test("status line shows the scored run with a retrospective flag", async ({ page }) => {
    await page.goto("/results");

    await expect(page.getByText("Scored")).toBeVisible();
    await expect(page.getByText("Retrospective replay", { exact: true })).toBeVisible();
  });

  test("weekly record sits beside the season record; finals read from the pick's side", async ({ page }) => {
    await page.goto("/results");

    const record = page.getByRole("region", { name: "Record" });
    await expect(record.getByText(/small sample/)).toBeVisible();
    await expect(record.getByText("4–3–1")).toBeVisible();
    await expect(record.getByText(/pts vs 52\.4% break-even/)).toHaveCount(0);
    await expect(record.getByText(/Live/)).toHaveCount(0);
    await expect(page.getByText(/model: Ohio State by 8\.6 · final: won by 7/).first()).toBeVisible();
  });

  test("team search narrows the results slate and cards show a graded badge", async ({ page }) => {
    await page.goto("/results");

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
    await page.goto("/results");
    await page.locator("#slate-sort").selectOption("worstResult");
    await page.getByRole("button", { name: "list", exact: true }).click();
    expect(await fits(page)).toBe(true);

    await page.setViewportSize({ width: 390, height: 800 });
    await page.getByRole("button", { name: "grid", exact: true }).click();
    expect(await fits(page)).toBe(true);
  });
});
