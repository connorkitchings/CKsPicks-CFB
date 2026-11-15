import { expect, type Page } from "@playwright/test";

/** Navigates and waits for React to hydrate, so clicks on server-rendered controls are not dropped. */
export async function gotoHydrated(page: Page, url: string): Promise<void> {
  await page.goto(url);
  await page.locator('html[data-hydrated="true"]').waitFor({ state: "attached" });
}

/** Switches the chart to its table view, retrying a click that landed before hydration. */
export async function openTable(page: Page): Promise<void> {
  const toggle = page.getByTestId("table-toggle");
  await expect(async () => {
    // Re-click only while still closed so a slow re-render never toggles the table back off.
    if ((await toggle.getAttribute("aria-pressed")) === "false") await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "true", { timeout: 500 });
  }).toPass();
}

/**
 * Makes the browser report Web Share support for files and records what is shared, so the
 * Share action can be exercised: read it back with `sharedFiles`.
 */
export async function stubWebShare(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const shared: { name: string; type: string; title: string }[] = [];
    Object.assign(window, { __shared: shared });
    Object.defineProperty(navigator, "canShare", { value: () => true, configurable: true });
    Object.defineProperty(navigator, "share", {
      configurable: true,
      value: async (data: { files?: File[]; title?: string }) => {
        for (const file of data.files ?? []) shared.push({ name: file.name, type: file.type, title: data.title ?? "" });
      },
    });
  });
}

export async function sharedFiles(page: Page): Promise<{ name: string; type: string; title: string }[]> {
  return page.evaluate(() => (window as unknown as { __shared: { name: string; type: string; title: string }[] }).__shared ?? []);
}

/** The collapsible "Full unit statistics" disclosure on the matchup page (it holds the unit comparison table). */
export const unitStats = (page: Page) =>
  page.locator("details").filter({ has: page.locator("summary", { hasText: "Full unit statistics" }) });

/** The collapsible "Full rating breakdown" disclosure on the matchup page. */
export const ratingBreakdownDetails = (page: Page) =>
  page.locator("details").filter({ has: page.locator("summary", { hasText: "Full rating breakdown" }) });

/** Expands a native disclosure (a no-op when it is already open) and waits for its content. */
export async function openDetails(details: ReturnType<typeof unitStats>): Promise<void> {
  if ((await details.getAttribute("open")) === null) await details.locator("summary").first().click();
  await expect(details).toHaveAttribute("open", "");
}

/** Opens the unit statistics disclosure so its table can be queried by role. */
export async function openUnitStats(page: Page): Promise<void> {
  await openDetails(unitStats(page));
  await expect(unitStats(page).getByRole("table")).toBeVisible();
}

/** Picks which team's offense the matchup page compares (the single away/home selector). */
export async function selectOffense(page: Page, side: "away" | "home"): Promise<void> {
  const buttons = page.getByRole("group", { name: "Offense comparison" }).getByRole("button");
  const button = side === "away" ? buttons.first() : buttons.last();
  await expect(async () => {
    if ((await button.getAttribute("aria-pressed")) !== "true") await button.click();
    await expect(button).toHaveAttribute("aria-pressed", "true", { timeout: 500 });
  }).toPass();
}

/** The collapsed "Featured comparisons and weekly highlights" disclosure on Games (every viewport). */
export const featuredComparisons = (page: Page) =>
  page.locator("details").filter({ has: page.locator("summary", { hasText: "Featured comparisons and weekly highlights" }) });

/**
 * Opens the featured disclosure so Biggest edges, Underdog picks and Highlights can be queried.
 * On phones each card inside is its own collapsed disclosure; those stay closed for the caller.
 */
export async function openFeatured(page: Page): Promise<void> {
  await openDetails(featuredComparisons(page));
}

/** The collapsed "Season and weekly model record" disclosure at the bottom of Games. */
export const slateRecordDetails = (page: Page) =>
  page.locator("details").filter({ has: page.locator("summary", { hasText: "Season and weekly model record" }) });

/**
 * Opens the model record disclosure; on phones also opens the record card's own summary line, so
 * the headings and cells are visible at every width.
 */
export async function openRecord(page: Page): Promise<void> {
  await openDetails(slateRecordDetails(page));
  const summary = page.getByTestId("record-summary");
  if (await summary.isVisible()) await openDetails(page.getByRole("region", { name: "Record" }).locator("details"));
}
