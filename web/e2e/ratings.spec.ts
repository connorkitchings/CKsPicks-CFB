import { expect, test, type Locator, type Page } from "@playwright/test";

const fits = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const phoneSort = (page: Page) => page.getByLabel("Sort by", { exact: true });
const sortHeader = (page: Page, label: string) => page.getByRole("columnheader", { name: `Sort by ${label}`, exact: true });
const sortButton = (page: Page, label: string) => page.getByRole("button", { name: `Sort by ${label}`, exact: true });
const SORT_LABELS = ["Overall", "Offense", "Defense", "SOR", "SOS Played", "SOS Remaining", "SOS Full"];

// Returns a locator for one team's cell by column header name. The `#` cell is a td and the
// team is a th row header, so `td, th` in DOM order lines up with `thead th` indices.
const rowCells = async (page: Page, team: string) => {
  const row = page.getByRole("table").locator("tbody tr", { hasText: team });
  await expect(row).toHaveCount(1);
  const headers = (await page.getByRole("table").locator("thead th").allTextContents()).map((text) => text.replace(/[↑↓]/g, "").trim());
  const cells = row.locator("td, th");
  return (column: string) => {
    const index = headers.indexOf(column);
    if (index < 0) throw new Error(`No table column named "${column}"`);
    return cells.nth(index);
  };
};

test.describe("mobile team ratings", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the sort select lists every sortable column", async ({ page }) => {
    await page.goto("/ratings");
    await expect(phoneSort(page).locator("option")).toHaveText(SORT_LABELS);
    await expect(page.getByRole("group", { name: "Rating category" })).toHaveCount(0);
    await expect(page.getByRole("group", { name: "Résumé sort" })).toHaveCount(0);
  });

  test("each sort promotes its own value and preserves national rank when filtered", async ({ page }) => {
    await page.goto("/ratings");
    const list = page.getByRole("list", { name: "Team ratings list" });
    // Each case selects a value different from the current one; a same-value select is not a user action.
    const cases = [
      { option: "Offense", team: "Ohio State", primary: "Offense+4.80" },
      { option: "Defense", team: "Appalachian State", primary: "Defense+3.60" },
      { option: "SOR", team: "Ohio State", primary: "SOR#1" },
      { option: "SOS Full", team: "Southern Mississippi", primary: "SOS Full#1" },
      { option: "Overall", team: "Texas", primary: "Overall+5.50" },
    ];
    for (const entry of cases) {
      await phoneSort(page).selectOption({ label: entry.option });
      const first = list.getByRole("listitem").first();
      await expect(first).toContainText(entry.team);
      await expect(first.getByTestId("primary-rating")).toHaveText(entry.primary);
    }
    await phoneSort(page).selectOption({ label: "Offense" });
    await page.getByRole("searchbox", { name: "Search teams" }).fill("Appalachian State");
    await expect(list.getByRole("listitem")).toHaveCount(1);
    await expect(list.getByLabel("National rank 3")).toBeVisible();
    await page.getByRole("searchbox", { name: "Search teams" }).fill("no matching team");
    await expect(page.getByRole("status")).toContainText("No teams match");
    await page.getByRole("button", { name: "Clear search", exact: true }).last().click();
    await expect(list.getByRole("listitem")).toHaveCount(4);
  });

  test("phone cards link team names to team pages with 44px targets", async ({ page }) => {
    await page.goto("/ratings");
    const link = page.getByRole("list", { name: "Team ratings list" }).getByRole("link", { name: "Appalachian State", exact: true });
    await expect(link).toHaveAttribute("href", "/teams/Appalachian%20State");
    expect((await link.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await link.click();
    await expect(page).toHaveURL(/\/teams\/Appalachian%20State$/);
    await expect(page.getByRole("heading", { level: 1, name: "App State" })).toBeVisible();
  });

  test("phone cards show FBS W-L, SOR rank and SOS ranks without WAA or raw SOS values", async ({ page }) => {
    await page.goto("/ratings?period=current");
    const texas = page.getByRole("list", { name: "Team ratings list" }).getByRole("listitem").first();
    await expect(texas).toContainText("FBS W-L 4–0");
    await expect(texas).toContainText("SOR #2");
    // Current period Played, Remaining and Full ranks for Texas are each third of four.
    await expect(texas).toContainText("SOS #3 / #3 / #3 (Played / Remaining / Full)");
    await expect(texas).not.toContainText("WAA");
    await expect(texas).not.toContainText("±");
    await expect(texas).not.toContainText("81.2");
    await expect(texas).not.toContainText("56.5");
  });

  test("period changes preserve live search and sort and update frozen values", async ({ page }) => {
    await page.goto("/ratings?season=2026");
    await page.getByRole("searchbox", { name: "Search teams" }).fill("Texas");
    await phoneSort(page).selectOption({ label: "Offense" });
    await page.getByLabel("Rating period", { exact: true }).selectOption({ label: "Post-Week 3" });
    await expect(page).toHaveURL(/sort=offense/);
    await expect(page).toHaveURL(/q=Texas/);
    await expect(page).toHaveURL(/season=2026/);
    await expect(page.getByRole("searchbox", { name: "Search teams" })).toHaveValue("Texas");
    await expect(phoneSort(page)).toHaveValue("offense");
    await expect(page.getByTestId("primary-rating")).toHaveText("Offense+3.20");
    await expect(page.getByText(/Evidence cutoff: Sep 22, 2026/)).toBeVisible();
    await page.getByLabel("Rating period", { exact: true }).selectOption({ label: "Preseason" });
    await expect(page.getByTestId("primary-rating")).toHaveText("Offense+3.00");
    await expect(page.getByText("Preseason baseline priors before 2026 kickoff.", { exact: true })).toBeVisible();
  });

  test("phone search, sort and period controls are at least 44px tall", async ({ page }) => {
    await page.goto("/ratings");
    for (const control of [
      page.getByRole("searchbox", { name: "Search teams" }),
      phoneSort(page),
      page.getByLabel("Rating period", { exact: true }),
    ]) {
      const box = await control.boundingBox();
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
    }
  });

  for (const width of [320, 360, 390, 430, 639, 640, 768, 1024, 1280]) {
    test(`loaded ratings and period controls fit ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/ratings");
      await expect(page.getByRole("heading", { name: "Team ratings" })).toBeVisible();
      if (width < 640) {
        await expect(page.getByLabel("Rating period", { exact: true })).toBeVisible();
        await expect(phoneSort(page)).toBeVisible();
        await expect(page.getByRole("navigation", { name: "Ratings timeline" })).toBeHidden();
        await expect(page.getByRole("list", { name: "Team ratings list" })).toContainText("Southern Mississippi");
      } else {
        await expect(page.getByLabel("Rating period", { exact: true })).toBeHidden();
        await expect(phoneSort(page)).toBeHidden();
        await expect(page.getByRole("navigation", { name: "Ratings timeline" })).toBeVisible();
        await expect(page.getByRole("table")).toContainText("Southern Mississippi");
      }
      expect(await fits(page)).toBe(true);
    });
  }
});

test.describe("desktop team ratings", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("the timeline keeps live search and the selected column across periods", async ({ page }) => {
    await page.goto("/ratings");
    await page.getByRole("searchbox", { name: "Search teams" }).fill("Appalachian");
    await sortButton(page, "Defense").click();
    await expect(sortHeader(page, "Defense")).toHaveAttribute("aria-sort", "descending");
    await page.getByRole("navigation", { name: "Ratings timeline" }).getByRole("link", { name: "Post-Week 3" }).click();
    await expect(page).toHaveURL(/sort=defense/);
    await expect(page).toHaveURL(/q=Appalachian/);
    await expect(page.getByRole("searchbox", { name: "Search teams" })).toHaveValue("Appalachian");
    await expect(sortHeader(page, "Defense")).toHaveAttribute("aria-sort", "descending");
    await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(1);
    await expect(page.getByRole("navigation", { name: "Ratings timeline" }).getByRole("link", { name: "Post-Week 3" })).toHaveAttribute("aria-current", "page");
  });

  test("a reversed direction survives a period change and a reload", async ({ page }) => {
    await page.goto("/ratings");
    // Overall opens best-first, so a second click on the active column reverses it.
    await sortButton(page, "Overall").click();
    await expect(sortHeader(page, "Overall")).toHaveAttribute("aria-sort", "ascending");
    await page.getByRole("navigation", { name: "Ratings timeline" }).getByRole("link", { name: "Post-Week 3" }).click();
    await expect(page).toHaveURL(/sort=overall/);
    await expect(page).toHaveURL(/dir=asc/);
    await expect(page.getByRole("table").locator("tbody tr").nth(0)).toContainText("Southern Mississippi");
    await expect(sortHeader(page, "Overall")).toHaveAttribute("aria-sort", "ascending");

    await page.reload();
    await expect(sortHeader(page, "Overall")).toHaveAttribute("aria-sort", "ascending");
    await expect(page.getByRole("table").locator("tbody tr").nth(0)).toContainText("Southern Mississippi");
  });

  test("desktop sort, search and period controls are at least 36px tall", async ({ page }) => {
    await page.goto("/ratings");
    for (const label of SORT_LABELS) {
      const box = await sortButton(page, label).boundingBox();
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(36);
    }
    const period = page.getByRole("navigation", { name: "Ratings timeline" }).getByRole("link", { name: "Post-Week 3" });
    expect((await period.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(36);
    expect((await page.getByRole("searchbox", { name: "Search teams" }).boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(36);
    await expect(phoneSort(page)).toBeHidden();
  });
});

test.describe("résumé columns", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  const rows = (page: Page) => page.getByRole("table").locator("tbody tr");
  const expectSortState = async (locator: Locator, state: "ascending" | "descending" | "none") => {
    await expect(locator).toHaveAttribute("aria-sort", state);
  };

  test("table headers are ordered as specified with no uncertainty or WAA column", async ({ page }) => {
    await page.goto("/ratings");
    const headers = page.getByRole("table").locator("thead th");
    // Sortable headers carry a direction arrow in their text on the active column, so match by prefix.
    await expect(headers).toHaveText([
      /^#$/, /^Team$/, /^Overall/, /^Offense/, /^Defense/, /^FBS W-L$/, /^SOR/, /^SOS Played/, /^SOS Remaining/, /^SOS Full/,
    ]);
    await expect(page.getByRole("columnheader", { name: "WAA", exact: true })).toHaveCount(0);
    await expect(page.getByRole("columnheader", { name: "Overall uncertainty" })).toHaveCount(0);
    await expect(page.getByRole("columnheader", { name: "±", exact: true })).toHaveCount(0);
    await expect(page.getByRole("columnheader", { name: "FBS W-L", exact: true })).toHaveAttribute("title", "Record against FBS opponents the period rates; FCS games are excluded.");
    await expect(sortHeader(page, "SOR")).toHaveAttribute("title", "Strength of record rank: 1 is the strongest résumé.");
    for (const label of ["SOS Played", "SOS Remaining", "SOS Full"]) {
      await expect(sortHeader(page, label)).toHaveAttribute("title", "Schedule difficulty rank among FBS teams (1 is hardest), measured against an average FBS team.");
    }
    await expect(page.getByRole("link", { name: "elite", exact: true })).toHaveAttribute("href", "/model/method#elite-reference");
    // Team names link to team pages in the desktop table.
    await expect(page.getByRole("table").getByRole("link", { name: "Texas", exact: true })).toHaveAttribute("href", "/teams/Texas");
    await expect(page.getByText("SOS ranks schedule difficulty for an average FBS team (1 is hardest).")).toBeVisible();
    await expect(page.getByRole("group", { name: "Rating category" })).toHaveCount(0);
    await expect(page.getByRole("group", { name: "Résumé sort" })).toHaveCount(0);
  });

  test("each sortable header is a button with aria-sort and a 36px target", async ({ page }) => {
    await page.goto("/ratings");
    await expectSortState(sortHeader(page, "Overall"), "descending");
    for (const label of SORT_LABELS.slice(1)) {
      await expectSortState(sortHeader(page, label), "none");
    }
    for (const label of SORT_LABELS) {
      await expect(page.getByRole("columnheader", { name: `Sort by ${label}`, exact: true }).getByRole("button", { name: `Sort by ${label}`, exact: true })).toBeVisible();
    }
  });

  test("the first click opens each column best-first and a second click reverses it", async ({ page }) => {
    await page.goto("/ratings");
    await expect(rows(page).nth(0)).toContainText("Texas");

    await sortButton(page, "Overall").click();
    await expectSortState(sortHeader(page, "Overall"), "ascending");
    await expect(rows(page).nth(0)).toContainText("Southern Mississippi");
    await sortButton(page, "Overall").click();
    await expectSortState(sortHeader(page, "Overall"), "descending");
    await expect(rows(page).nth(0)).toContainText("Texas");

    await sortButton(page, "Offense").click();
    await expectSortState(sortHeader(page, "Offense"), "descending");
    await expectSortState(sortHeader(page, "Overall"), "none");
    await expect(rows(page).nth(0)).toContainText("Ohio State");

    await sortButton(page, "Defense").click();
    await expect(rows(page).nth(0)).toContainText("Appalachian State");
  });

  test("SOR sorts rank 1 first and keeps a null SOR last in both directions", async ({ page }) => {
    await page.goto("/ratings");
    await sortButton(page, "SOR").click();
    await expectSortState(sortHeader(page, "SOR"), "ascending");
    await expect(rows(page).nth(0)).toContainText("Ohio State");
    await expect(rows(page).nth(1)).toContainText("Texas");
    await expect(rows(page).nth(2)).toContainText("Appalachian State");
    await expect(rows(page).nth(3)).toContainText("Southern Mississippi");

    await sortButton(page, "SOR").click();
    await expectSortState(sortHeader(page, "SOR"), "descending");
    await expect(rows(page).nth(0)).toContainText("Appalachian State");
    await expect(rows(page).nth(2)).toContainText("Ohio State");
    await expect(rows(page).nth(3)).toContainText("Southern Mississippi");
  });

  test("SOS Full sorts hardest schedule (rank 1) first", async ({ page }) => {
    await page.goto("/ratings");
    // Full ranks (current period): Southern Mississippi 1, Appalachian State 2, Texas 3, Ohio State 4.
    await sortButton(page, "SOS Full").click();
    await expectSortState(sortHeader(page, "SOS Full"), "ascending");
    await expect(rows(page).nth(0)).toContainText("Southern Mississippi");
    await expect(rows(page).nth(1)).toContainText("Appalachian State");
    await expect(rows(page).nth(2)).toContainText("Texas");
    await expect(rows(page).nth(3)).toContainText("Ohio State");

    await sortButton(page, "SOS Full").click();
    await expectSortState(sortHeader(page, "SOS Full"), "descending");
    await expect(rows(page).nth(0)).toContainText("Ohio State");
  });

  test("SOS cells show ranks with the raw average in a title", async ({ page }) => {
    await page.goto("/ratings");
    const texas = await rowCells(page, "Texas");
    await expect(texas("Overall")).toHaveText("+5.50");
    await expect(texas("FBS W-L")).toHaveText("4–0");
    await expect(texas("SOR")).toHaveText("#2");
    await expect(texas("SOR")).toHaveAttribute("title", "SOR 81.2");
    await expect(texas("SOS Played")).toHaveText("#3");
    await expect(texas("SOS Played")).toHaveAttribute("title", "SOS Played 52.6");
    await expect(texas("SOS Remaining")).toHaveText("#3");
    await expect(texas("SOS Remaining")).toHaveAttribute("title", "SOS Remaining 58.4");
    await expect(texas("SOS Full")).toHaveText("#3");
    await expect(texas("SOS Full")).toHaveAttribute("title", "SOS Full 56.5");

    const ohioState = await rowCells(page, "Ohio State");
    await expect(ohioState("FBS W-L")).toHaveText("3–1");
    await expect(ohioState("SOR")).toHaveText("#1");
    await expect(ohioState("SOR")).toHaveAttribute("title", "SOR 93.7");
    await expect(ohioState("SOS Full")).toHaveText("#4");

    // Fewer than 3 completed FBS games: SOR is null and renders as a dash with no score title.
    const southernMiss = await rowCells(page, "Southern Mississippi");
    await expect(southernMiss("FBS W-L")).toHaveText("1–1");
    await expect(southernMiss("SOR")).toHaveText("—");
    await expect(southernMiss("SOR")).not.toHaveAttribute("title", /SOR/);
  });

  test("the keyboard opens a sort with Enter and reverses it with Space", async ({ page }) => {
    await page.goto("/ratings");
    const button = sortButton(page, "SOS Played");
    await button.press("Enter");
    await expectSortState(sortHeader(page, "SOS Played"), "ascending");
    await expect(rows(page).nth(0)).toContainText("Southern Mississippi");
    await button.press("Space");
    await expectSortState(sortHeader(page, "SOS Played"), "descending");
    await expect(rows(page).nth(0)).toContainText("Ohio State");
  });

  test("a focused sort header shows a visible focus ring", async ({ page }) => {
    await page.goto("/ratings");
    const button = sortButton(page, "SOR");
    await button.focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab");
    await expect(button).toBeFocused();
    const outline = await button.evaluate((element) => {
      const style = getComputedStyle(element);
      return { width: style.outlineWidth, style: style.outlineStyle };
    });
    expect(outline).toEqual({ width: "2px", style: "solid" });
  });

  test("?sort=sor selects the SOR sort on load and after reload", async ({ page }) => {
    await page.goto("/ratings?sort=sor");
    await expectSortState(sortHeader(page, "SOR"), "ascending");
    await expect(rows(page).nth(0)).toContainText("Ohio State");

    await page.reload();
    await expectSortState(sortHeader(page, "SOR"), "ascending");
    await expect(rows(page).nth(0)).toContainText("Ohio State");
  });

  test("?dir=desc reverses the SOR sort on load", async ({ page }) => {
    await page.goto("/ratings?sort=sor&dir=desc");
    await expectSortState(sortHeader(page, "SOR"), "descending");
    await expect(rows(page).nth(0)).toContainText("Appalachian State");
  });

  test("the legacy ?sort=sos value opens SOS Full", async ({ page }) => {
    await page.goto("/ratings?sort=sos&dir=desc");
    await expectSortState(sortHeader(page, "SOS Full"), "descending");
    await expect(rows(page).nth(0)).toContainText("Ohio State");
  });

  test("the removed ?sort=waa value and an unknown dir fall back to Overall best-first", async ({ page }) => {
    await page.goto("/ratings?sort=waa&dir=sideways");
    await expectSortState(sortHeader(page, "Overall"), "descending");
    await expect(rows(page).nth(0)).toContainText("Texas");
  });

  test("conference filter narrows rows while preserving national rank and rank-tier badges", async ({ page }) => {
    await page.goto("/ratings");
    await expect(rows(page).first().locator("[data-rank-chip]").first()).toBeVisible();
    const filter = page.getByTestId("conference-filter");
    await expect(filter).toBeVisible();

    await filter.selectOption("Sun Belt");
    await expect(rows(page)).toHaveCount(2);
    await expect(rows(page).nth(0)).toContainText("Appalachian State");
    await expect(rows(page).nth(1)).toContainText("Southern Mississippi");

    const appState = await rowCells(page, "Appalachian State");
    // National overall position #3 and SOR #3 are preserved when filtered to Sun Belt.
    await expect(appState("#")).toHaveText("3");
    await expect(appState("SOR")).toHaveText("#3");
    await expect(appState("SOS Full")).toHaveText("#2");

    await filter.selectOption("all");
    await expect(rows(page)).toHaveCount(4);
  });
});

test.describe("release without résumé rows", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("renders dashes and no ranks for résumé columns, hides the résumé note, and logs no errors", async ({ page }) => {
    const problems: string[] = [];
    page.on("pageerror", (error) => problems.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") problems.push(message.text());
    });

    // `no-resume` is the fixture period that serves ratings without résumé rows.
    await page.goto("/ratings?period=no-resume");
    await expect(page.getByRole("heading", { name: "Team ratings" })).toBeVisible();
    await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(4);
    await expect(page.getByRole("columnheader", { name: "FBS W-L", exact: true })).toBeVisible();
    await expect(sortHeader(page, "SOR")).toBeVisible();

    const texas = await rowCells(page, "Texas");
    await expect(texas("Overall")).toHaveText("+5.50");
    await expect(texas("FBS W-L")).toHaveText("—");
    await expect(texas("SOR")).toHaveText("—");
    await expect(texas("SOS Played")).toHaveText("—");
    await expect(texas("SOS Remaining")).toHaveText("—");
    await expect(texas("SOS Full")).toHaveText("—");
    await expect(page.getByRole("table").locator("tbody")).not.toContainText(/#\d/);

    await expect(page.getByRole("group", { name: "Résumé sort" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "elite", exact: true })).toBeHidden();
    await expect(page.getByText("SOS ranks schedule difficulty")).toBeHidden();
    expect(problems).toEqual([]);
  });
});

test.describe("rank color scale", () => {
  // Computed colors may be oklab/srgb strings; rasterize one pixel to compare plain sRGB channels.
  const rgb = (page: Page, value: string) => page.evaluate((css) => {
    const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true })!;
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, 1, 1);
    ctx.fillStyle = css;
    ctx.fillRect(0, 0, 1, 1);
    return Array.from(ctx.getImageData(0, 0, 1, 1).data.slice(0, 3));
  }, value);

  for (const scheme of ["light", "dark"] as const) {
    test(`rank 1 is greener than the last rank in ${scheme} mode, with the rank as the chip text`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/ratings");
      const bodyRows = page.getByRole("table").locator("tbody tr");
      await expect(bodyRows.first()).toBeVisible();
      const count = await bodyRows.count();
      const first = bodyRows.first().locator("[data-rank-chip]").first();
      const last = bodyRows.nth(count - 1).locator("[data-rank-chip]").first();
      await expect(first).toHaveText("1");
      await expect(last).toHaveText(String(count));

      const style = (chip: Locator) => chip.evaluate((el) => {
        const s = getComputedStyle(el);
        return { background: s.backgroundColor, border: s.borderTopColor, color: s.color };
      });
      const [best, worst] = [await style(first), await style(last)];
      expect(best.background).not.toBe(worst.background);
      const [bestR, bestG] = await rgb(page, best.background);
      const [worstR, worstG] = await rgb(page, worst.background);
      expect(bestG - bestR).toBeGreaterThan(worstG - worstR);
      expect(await rgb(page, best.border)).not.toEqual(await rgb(page, worst.border));
      // Text stays the ink color on every chip: the hue never carries the text.
      expect(best.color).toBe(worst.color);
      expect(best.color).toBe(await page.locator("body").evaluate((el) => getComputedStyle(el).color));
    });
  }
});
