import { expect, test } from "@playwright/test";
import sharp from "sharp";
import { gotoHydrated, openUnitStats, selectOffense, sharedFiles, stubWebShare, unitStats } from "./helpers";

test.describe("matchup page (fixture mode)", () => {
  test("mismatched publication lineage hides model sections and disables sharing", async ({ page }) => {
    await stubWebShare(page);
    await page.goto("/matchup/987656");
    await expect(page.getByRole("status", { name: "Team stats" })).toContainText("provenance is unavailable");
    await expect(page.getByRole("table")).toHaveCount(0);
    await expect(page.getByRole("region", { name: "How the ratings are built" })).toHaveCount(0);
    await expect(page.getByTestId("model-rating")).toHaveCount(0);
    await expect(page.getByTestId("forecast-grid")).toContainText("Market");
    await expect(page.getByTestId("forecast-grid")).not.toContainText("Model");
    const controls = page.getByTestId("matchup-summary-header").getByTestId("share-controls");
    await expect(controls.getByTestId("share-download")).toBeDisabled();
    await expect(controls.getByTestId("share-button")).toBeDisabled();
    for (const button of await controls.getByRole("button").all()) await expect(button).toBeDisabled();
  });

  test("shows both unit tables: 12 grouped metrics, ties, an unranked zero and unranked dashes", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    await expect(page.getByRole("region", { name: "Team stats" })).toBeVisible();
    // The full statistics are collapsed until opened, and show only the selected offense's comparison.
    await expect(unitStats(page).getByRole("table")).toHaveCount(0);
    await openUnitStats(page);
    await expect(unitStats(page).getByRole("table")).toHaveCount(1);
    const first = unitStats(page).getByRole("table").first();
    await expect(first).toHaveAccessibleName(/Offense vs .* Defense/);
    for (const section of ["Core possession efficiency", "Situational / down and distance", "Drive context"]) {
      await expect(first.getByText(section)).toBeVisible();
    }
    for (const label of ["Points/possession", "PPA/possession", "PPA/play", "Pass PPA/play"]) {
      const escaped = label.replace(/[/]/g, "\\/");
      await expect(first.locator("td").filter({ hasText: new RegExp(`^${escaped}`) }).first()).toBeVisible();
    }
    // Plays/possession and non-offense points are stored but not shown.
    await expect(page.getByText("Non-offense pts/game")).toHaveCount(0);
    await expect(page.getByText("Plays/possession")).toHaveCount(0);
    await expect(first.locator("tbody tr").filter({ has: page.locator("td") })).toHaveCount(12);
    await expect(page.getByText(/FBS opponents only; regulation play, garbage time excluded/)).toBeVisible();
    await expect(page.getByText("#null")).toHaveCount(0);
    // Ties show as T-N; unranked rows (no sample or an exact zero) show a dash with a "Not ranked" tooltip.
    await expect(page.getByText(/^T-\d+$/).first()).toBeVisible();
    await expect(first.getByTitle("Not ranked").first()).toBeVisible();
  });

  test("section headers are centered across the table", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    await openUnitStats(page);
    const table = unitStats(page).getByRole("table").first();
    const tableBox = await table.boundingBox();
    for (const label of ["Core possession efficiency", "Situational / down and distance", "Drive context"]) {
      const header = table.locator("th[scope='rowgroup']", { hasText: label });
      await expect(header).toHaveCSS("text-align", "center");
      const textBox = await header.evaluate((el) => {
        const range = document.createRange();
        range.selectNodeContents(el);
        const r = range.getBoundingClientRect();
        return { x: r.x, width: r.width };
      });
      expect(Math.abs(textBox.x + textBox.width / 2 - (tableBox!.x + tableBox!.width / 2))).toBeLessThan(4);
    }
  });

  test("an exact zero shows its value but no rank", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    await openUnitStats(page);
    const row = unitStats(page)
      .getByRole("table")
      .first()
      .locator("tr", { hasText: "Explosive plays" });
    await expect(row.locator("[data-value=defense]")).toHaveText("0.0%");
    await expect(row.getByTitle("Not ranked")).toHaveCount(2);
  });

  test("no edge bars, edge summaries or legend are drawn (kept in code for later)", async ({ page }) => {
    await page.goto("/matchup/1");
    await expect(page.getByTestId("edge-summary")).toHaveCount(0);
    await expect(page.getByTestId("edge-legend")).toHaveCount(0);
    await expect(page.locator("[data-edge], [data-strength]")).toHaveCount(0);
    await expect(page.getByText(/Edge:/)).toHaveCount(0);
    await expect(page.getByText(/darker means a bigger gap/)).toHaveCount(0);
  });

  test("table headers stack the logo above the name above Offense/Defense, centered", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    await openUnitStats(page);
    const heads = unitStats(page).getByRole("table").first().locator("xpath=ancestor::div[1]").locator("h3");
    await expect(heads).toHaveCount(2);
    const first = unitStats(page).getByRole("table").first().locator("xpath=ancestor::div[1]");
    const block = first.locator("div.flex-col").first();
    const img = await block.locator("img").first().boundingBox();
    const name = await block.locator("h3").boundingBox();
    const role = await block.locator("span").first().boundingBox();
    expect(img!.y + img!.height).toBeLessThanOrEqual(name!.y + 2); // logo above name
    expect(name!.y + name!.height).toBeLessThanOrEqual(role!.y + 2); // name above role
    const box = await block.boundingBox();
    const center = (b: { x: number; width: number }) => b.x + b.width / 2;
    for (const part of [img!, name!, role!]) {
      expect(Math.abs(center(part) - center(box!))).toBeLessThan(3); // centered
    }
    await expect(block).toContainText("Offense");
  });

  test("one selector drives a single unit table at every width, with synchronized section collapse", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await gotoHydrated(page, "/matchup/1");
    await openUnitStats(page);
    const tables = unitStats(page).getByRole("table");
    await expect(tables).toHaveCount(1);
    const box = await tables.boundingBox();
    expect(box!.width).toBeGreaterThan(430); // room for values, ranks and metric labels

    // Collapsing a secondary section hides its rows and the collapse survives switching offenses.
    const sitButton = tables.getByRole("button", { name: /Situational \/ down and distance/ });
    await expect(sitButton).toHaveAttribute("aria-expanded", "true");
    await sitButton.click();
    await expect(sitButton).toHaveAttribute("aria-expanded", "false");
    await expect(tables.locator("tbody tr").filter({ has: page.locator("td") })).toHaveCount(6);
    const awayName = await tables.getAttribute("aria-label");
    await selectOffense(page, "home");
    await expect(tables).not.toHaveAttribute("aria-label", awayName!);
    await expect(tables.getByRole("button", { name: /Situational \/ down and distance/ })).toHaveAttribute("aria-expanded", "false");
    await expect(tables.locator("tbody tr").filter({ has: page.locator("td") })).toHaveCount(6);
    await tables.getByRole("button", { name: /Situational \/ down and distance/ }).click();
    await expect(tables.locator("tbody tr").filter({ has: page.locator("td") })).toHaveCount(12);
    await selectOffense(page, "away");
    await expect(tables).toHaveAttribute("aria-label", awayName!);

    await page.setViewportSize({ width: 390, height: 900 });
    await gotoHydrated(page, "/matchup/1");
    await openUnitStats(page);
    const selectors = page.getByRole("group", { name: "Offense comparison" });
    const away = selectors.getByRole("button").first();
    const home = selectors.getByRole("button").last();
    await expect(away).toHaveAttribute("aria-pressed", "true");
    await expect(home).toHaveAttribute("aria-pressed", "false");
    const firstName = await tables.getAttribute("aria-label");
    await selectOffense(page, "home");
    await expect(away).toHaveAttribute("aria-pressed", "false");
    await expect(tables).not.toHaveAttribute("aria-label", firstName!);
    await expect(tables.locator("thead th")).toHaveCount(3);
    await expect(tables.locator("tbody tr").filter({ has: page.locator("td") })).toHaveCount(12);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    // The selection survives resizing, and the selector stays available at every width.
    for (const width of [1024, 1023]) {
      await page.setViewportSize({ width, height: 900 });
      await expect(tables).toHaveCount(1);
      await expect(selectors).toBeVisible();
      await expect(home).toHaveAttribute("aria-pressed", "true");
    }
    await selectOffense(page, "away");
    await expect(tables).toHaveAttribute("aria-label", firstName!);
  });

  test("top of the page: records, venue, rating labels, a real Updated time, no duplicate system name", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    await openUnitStats(page);
    const away = page.locator("[data-side='away']");
    await expect(away).toContainText(/Away · \d+-\d+/);
    await expect(page.locator("[data-side='home']")).toContainText(/Home · \d+-\d+/);
    await expect(away.getByTestId("model-rating")).toHaveText(/^Model Rank\s*#\d+$/);
    // No rating numbers in the hero (the rating breakdown section below shows them); offense and defense ranks live in the table headers, not the hero.
    await expect(away).not.toContainText("Model Offense");
    await expect(away).not.toContainText("V5 rank");
    await expect(page.locator("[data-side]").getByText(/Rating [+−]\d/)).toHaveCount(0);
    const first = unitStats(page).getByRole("table").first().locator("xpath=ancestor::div[1]");
    await expect(first.getByTestId("unit-offense-rank")).toHaveText(/^Model Offense Rank\s*#\d+$/);
    await expect(first.getByTestId("unit-defense-rank")).toHaveText(/^Model Defense Rank\s*#\d+$/);
    await expect(page.getByTestId("unit-offense-rank")).toHaveCount(1);
    await expect(page.getByTestId("unit-defense-rank")).toHaveCount(1);
    const facts = page.getByTestId("game-facts");
    await expect(facts).toContainText(/, [A-Z]{2}|Neutral site/); // venue
    await expect(facts).not.toContainText("Blitzkrieg");
    // The forecast update time is stated in the data context (the app bar no longer repeats it), and it is not the kickoff.
    await expect(page.getByLabel("Data context")).toContainText(/Forecast updated Sep (29|30)/);
    await expect(page.getByLabel("Data context")).toContainText("not a live feed");
    await expect(page.locator("#matchup-header")).toHaveText(/ at /);
    await expect(page.locator("#matchup-header")).toHaveClass(/sr-only/);
    // The forecast box shows market and model lines only; no model-minus-market edge numbers.
    await expect(page.getByText("Forecast & Lines")).toBeVisible();
    await expect(page.getByTitle("Model minus market")).toHaveCount(0);
    // The model bet names the side without the word "Lean".
    await expect(page.getByTestId("forecast-grid")).not.toContainText("Lean");
    // Spread and Total columns line up: every value in a column shares one center line.
    const grid = page.getByTestId("forecast-grid");
    await expect(grid.getByText("Spread", { exact: true })).toBeVisible();
    await expect(grid.getByText("Total", { exact: true })).toBeVisible();
    await expect(grid.getByText("DraftKings", { exact: true })).toBeVisible();
    await expect(grid.getByText("Bovada", { exact: true })).toBeVisible();
    // The notes explain the offense-versus-defense comparison, which comes before the collapsed full statistics.
    const notes = await page.getByTestId("matchup-notes").boundingBox();
    const statsBox = await unitStats(page).boundingBox();
    expect(notes!.y + notes!.height).toBeLessThanOrEqual(statsBox!.y + 2);
    // Coverage, the allowed-defense convention and the rank cohort in one note; no "before this game".
    await expect(page.getByTestId("matchup-notes")).toHaveText(/^Statistics through Week \d+\. FBS opponents only; regulation play, garbage time excluded; raw, not opponent-adjusted\. Defense values are allowed\. Ranks among \d+ teams; T = tied\.$/);
    await expect(page.getByText("before this game")).toHaveCount(0);
    // One way back at the bottom (the top already has "← Week N games").
    await expect(page.getByRole("link", { name: /^Return to Week/ })).toHaveCount(0);
    await expect(page.getByRole("link", { name: /^← Week \d+ games$/ })).toHaveAttribute("href", /^\/\?week=\d+$/);
    await expect(page.getByRole("link", { name: /^All Week \d+ games$/ })).toBeVisible();

    await expect(page).toHaveTitle(/ at .* · Matchup/);
  });

  test("loaded matchups fit phones and tablets with teams above forecasts, and between them from lg", async ({ page }) => {
    for (const width of [320, 360, 390, 430, 639, 640, 768, 1024, 1280]) {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/matchup/1");
      // The offense-versus-defense comparison is always present; the full tables are collapsed.
      await expect(page.getByTestId("tale-of-the-tape")).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      const { away, home, forecast } = await page.evaluate(() => {
        const box = (selector: string) => {
          const rect = document.querySelector(selector)!.getBoundingClientRect();
          return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
        };
        return {
          away: box("[data-side=away]"),
          home: box("[data-side=home]"),
          forecast: box('[data-testid="forecast-grid"]'),
        };
      });
      expect(Math.abs(away!.y - home!.y)).toBeLessThan(2);
      if (width < 1024) {
        expect(forecast!.y).toBeGreaterThan(Math.max(away!.y + away!.height, home!.y + home!.height));
      } else {
        // From lg the forecast sits in the centre column, level with the teams.
        expect(forecast!.x).toBeGreaterThan(away!.x + away!.width);
        expect(forecast!.x + forecast!.width).toBeLessThan(home!.x);
        expect(forecast!.y).toBeLessThan(Math.max(away!.y + away!.height, home!.y + home!.height));
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      if (width < 640) {
        for (const action of await page.getByTestId("share-controls").getByRole("button").all()) {
          expect((await action.boundingBox())!.height).toBeGreaterThanOrEqual(44);
        }
      }
    }
  });

  test("phone unit controls support keyboard selection without changing forecast values", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/matchup/1");
    // The route streams; wait for the content to replace the loading shell before reading text.
    await expect(page.getByTestId("forecast-grid")).toBeVisible();
    const forecast = await page.getByTestId("forecast-grid").innerText();
    const controls = page.getByRole("group", { name: "Offense comparison" });
    const home = controls.getByRole("button").last();
    await home.focus();
    await page.keyboard.press("Enter");
    await expect(home).toHaveAttribute("aria-pressed", "true");
    expect(await page.getByTestId("forecast-grid").innerText()).toBe(forecast);
    await expect(page.locator("main#main-content")).toHaveAttribute("tabindex", "-1");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/ at /);
  });

  test("completed and missing-line games preserve scores and explicit line absence on phones", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 844 });
    await page.goto("/matchup/101");
    await expect(page.locator("[data-side=away]")).toContainText("Final Score");
    await expect(page.locator("[data-side=home]")).toContainText("Final Score");
    await expect(page.getByTestId("forecast-grid")).toContainText("Model lean");
    await expect(page.getByTestId("forecast-grid")).not.toContainText("Model Bet");
    // Completed matchups keep frozen pregame evidence and say so.
    await expect(page.getByText(/frozen pregame context, not an actual-game statistical breakdown/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.goto("/matchup/7");
    await expect(page.getByTestId("forecast-grid")).toContainText("—");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });

  test("is noindex and unknown games show the not-found page", async ({ page }) => {
    await page.goto("/matchup/1");
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
    // Unknown ids render the 404 page.
    await page.goto("/matchup/987654");
    await expect(page.getByText("This page could not be found")).toBeVisible();
    await expect(page.getByRole("region", { name: "Team stats" })).toHaveCount(0);
    await page.goto("/matchup/abc");
    await expect(page.getByText("This page could not be found")).toBeVisible();
  });

  test("unknown and invalid game ids return HTTP 404; known games return 200", async ({ request }) => {
    expect((await request.get("/matchup/1")).status()).toBe(200);
    expect((await request.get("/matchup/987654")).status()).toBe(404);
    expect((await request.get("/matchup/abc")).status()).toBe(404);
    expect((await request.get("/matchup/0")).status()).toBe(404);
    expect((await request.get("/matchup/99999999999999999999")).status()).toBe(404);
  });

  test("the Games week view lists the week's games and links to each breakdown", async ({ page }) => {
    await page.goto("/?week=5");
    await expect(page.getByRole("heading", { name: "Week 5 games", exact: true })).toBeVisible();
    await expect(page.locator("#week-select")).toHaveValue("5");
    const links = page.locator("a[href^='/matchup/']");
    expect(await links.count()).toBeGreaterThan(3);
    await links.first().click();
    await expect(page).toHaveURL(/\/matchup\/\d+$/);
    await expect(page.getByRole("region", { name: "Team stats" })).toBeVisible();
    await page.getByRole("link", { name: /All Week \d+ games/ }).click();
    await expect(page).toHaveURL(/\/\?week=\d+&status=all$/);
  });

  test("the Games week view fits a phone", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/?week=5");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });

  test("game cards carry a Matchup button that opens the breakdown; team names link from Teams and matchup pages but not slate cards", async ({ page }) => {
    await page.goto("/");
    const home = page.getByTestId("matchup-link");
    expect(await home.count()).toBeGreaterThanOrEqual(1);
    await expect(home.first()).toHaveAttribute("href", /^\/matchup\/\d+$/);
    // The slate fixture ids are the ones the matchup fixtures know, so click through there.
    await page.goto("/");
    await page.getByTestId("matchup-link").first().click();
    await expect(page).toHaveURL(/\/matchup\/\d+$/);
    await expect(page.getByRole("region", { name: "Team stats" })).toBeVisible();
    // The hero names and the matchup footer link to team pages (a name appears in both).
    await expect(page.locator("main a[href^='/teams/']").first()).toBeVisible();
    expect(await page.locator("[data-side] a[href^='/teams/']").count()).toBe(2);
    expect(await page.locator("main a[href^='/teams/']").count()).toBe(4);
    // Slate cards never link to team pages.
    await page.goto("/");
    expect(await page.getByTestId("matchup-link").count()).toBeGreaterThanOrEqual(1);
    expect(await page.locator("a[href^='/teams/']").count()).toBe(0);
    await page.goto("/?week=4");
    expect(await page.getByTestId("matchup-link").count()).toBeGreaterThanOrEqual(1);
    expect(await page.locator("a[href^='/teams/']").count()).toBe(0);
    await page.goto("/teams");
    expect(await page.locator("a[href^='/teams/']").count()).toBeGreaterThan(0);
  });

  test("slate cards also carry the Matchup button", async ({ page }) => {
    await page.goto("/");
    expect(await page.getByTestId("matchup-link").count()).toBeGreaterThan(3);
    await page.goto("/?week=4");
    expect(await page.getByTestId("matchup-link").count()).toBeGreaterThan(3);
  });

  test("no page footer shows a GitHub source link", async ({ page }) => {
    for (const url of ["/", "/?week=4", "/teams", "/model", "/matchup/1", "/model/method"]) {
      await page.goto(url);
      await expect(page.locator("a[href*='github.com']")).toHaveCount(0);
      await expect(page.locator("footer")).toHaveCount(1);
      await expect(page.locator("footer a")).toHaveCount(0);
      await expect(page.locator("footer")).not.toContainText(/Source:|github\.com/);
    }
  });

  test("share: download exports a fixed 1080x1350 card at 2x, and the card fits its canvas", async ({ page }) => {
    // The button is in the server HTML; a click before hydration is silently dropped.
    await gotoHydrated(page, "/matchup/1");
    await expect(page.getByTestId("share-download")).toBeVisible();
    // The card exists only while an image is being made.
    await expect(page.getByTestId("share-card")).toHaveCount(0);

    const attached = page.waitForSelector("[data-testid=share-card]", { state: "attached" });
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("share-download").click()]);
    const card = await attached;
    const fit = await card.evaluate((el) => ({
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
      text: el.textContent ?? "",
    }));
    // overflow is hidden on the card, so content taller than the canvas shows up as scrollHeight > clientHeight.
    expect(fit.scrollHeight).toBeLessThanOrEqual(fit.clientHeight);
    expect(fit.scrollWidth).toBeLessThanOrEqual(fit.clientWidth);
    expect(fit.text).toMatch(/Biggest mismatches/);
    expect(fit.text).toMatch(/(offense|defense) by \d+ spots?/);
    expect(fit.text).toContain("Forecast & Lines");
    expect(fit.text).toContain("Stratum CFB");
    expect(fit.text).not.toContain("Crest");
    expect(fit.text).not.toMatch(/Key factors|Tape Verdict/);
    expect(fit.text).not.toMatch(/Lean|Model minus market/);

    expect(download.suggestedFilename()).toMatch(/^stratum-.+-at-.+-2026-week-\d+\.png$/);
    const meta = await sharp(await download.path()).metadata();
    expect([meta.format, meta.width, meta.height]).toEqual(["png", 2160, 2700]);
    await expect(page.getByRole("status")).toHaveText("Image saved");
    await expect(page.getByTestId("share-card")).toHaveCount(0);
  });

  test("export actions match the charts: icon buttons with tooltips, 44px targets on phones, Web Share when supported", async ({ page }) => {
    await stubWebShare(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/matchup/1");
    const controls = page.getByTestId("share-controls");
    const download = controls.getByRole("button", { name: "Download PNG", exact: true });
    await expect(download).toHaveText("");
    await expect(controls.getByRole("button", { name: "Share", exact: true })).toBeVisible();
    for (const button of await controls.getByRole("button").all()) {
      expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
    // The same tooltip-on-focus behaviour as the chart export buttons.
    const tooltip = page.getByTestId("share-download-tooltip");
    await expect(tooltip).toHaveCSS("opacity", "0");
    await download.focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab");
    await expect(tooltip).toHaveText("Download PNG");
    await expect(tooltip).toHaveCSS("opacity", "1");
    // Share hands the PNG to the browser's share sheet under the matchup's file name and title.
    await page.getByTestId("share-button").click();
    await expect.poll(async () => (await sharedFiles(page)).length).toBe(1);
    const [file] = await sharedFiles(page);
    expect(file.name).toMatch(/^stratum-.+-at-.+-2026-week-\d+\.png$/);
    expect(file.type).toBe("image/png");
    expect(file.title).toMatch(/ at /);
    await expect(page.getByTestId("share-card")).toHaveCount(0);
  });

  test("share: the card is not part of the page until used, and the page tables are unchanged", async ({ page }) => {
    await gotoHydrated(page, "/matchup/1");
    await openUnitStats(page);
    await expect(unitStats(page).getByRole("table")).toHaveCount(1);
    await expect(page.getByTestId("share-card")).toHaveCount(0);
    await expect(page.getByText("Biggest mismatches")).toHaveCount(0);
  });
});

test.describe("stored stat rows that break their contract", () => {
  test("show an explicit unavailable state, not 'not published' and not partial stats", async ({ page }) => {
    await page.goto("/matchup/987655");
    const stats = page.getByRole("region", { name: "Team stats" });
    await expect(stats).toContainText("Team stats are temporarily unavailable.");
    await expect(page.getByText("Team stats are not published for this game yet.")).toHaveCount(0);
    await expect(page.getByTestId("matchup-notes")).toHaveCount(0);
  });

  test("a healthy matchup never shows the unavailable copy", async ({ page }) => {
    await page.goto("/matchup/1");
    await expect(page.getByText("Team stats are temporarily unavailable.")).toHaveCount(0);
    await expect(page.getByTestId("matchup-notes")).toHaveCount(1);
  });
});
