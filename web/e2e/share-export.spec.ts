import { expect, test, type Page } from "@playwright/test";
import { gotoHydrated } from "./helpers";

// Fixture-mode chart page; the Share action behaves identically on every export surface.
const URL = "/stats?chart=efficiency&week=3";
const TITLE = "Efficiency vs explosiveness";
const WEEK_3 = "crest-efficiency-offense-2026-through-week-3.png";
const WEEK_2 = "crest-efficiency-offense-2026-through-week-2.png";

type Outcome = "ok" | "abort" | "expired" | "fail";
type ShareCall = { name: string; title: string; theme: "light" | "dark" };

/**
 * Web Share that reports file support and plays back one scripted outcome per call (then
 * succeeds): "abort" is the user dismissing the sheet, "expired" the user gesture having run
 * out while the image rendered, "fail" any other rejection. Every call is recorded with the
 * page theme at that moment.
 */
async function scriptShare(page: Page, outcomes: Outcome[]): Promise<void> {
  await page.addInitScript((script) => {
    const calls: ShareCall[] = [];
    const queue = [...script];
    Object.assign(window, { __shareCalls: calls });
    Object.defineProperty(navigator, "canShare", { value: () => true, configurable: true });
    Object.defineProperty(navigator, "share", {
      configurable: true,
      value: async (data: { files?: File[]; title?: string }) => {
        const theme = document.documentElement.classList.contains("dark") ? "dark" : "light";
        for (const file of data.files ?? []) calls.push({ name: file.name, title: data.title ?? "", theme });
        const next = queue.shift() ?? "ok";
        if (next === "abort") throw new DOMException("Share canceled", "AbortError");
        if (next === "expired") throw new DOMException("Must be handling a user gesture", "NotAllowedError");
        if (next === "fail") throw new DOMException("Share failed", "DataError");
      },
    });
  }, outcomes);
}

const shareCalls = (page: Page) => page.evaluate(() => (window as unknown as { __shareCalls: ShareCall[] }).__shareCalls);

/** Counts saved files without waiting on an event that must not happen. */
function countDownloads(page: Page): { names: string[] } {
  const seen = { names: [] as string[] };
  page.on("download", (download) => seen.names.push(download.suggestedFilename()));
  return seen;
}

const status = (page: Page) => page.getByTestId("chart-export").getByRole("status");
const share = (page: Page) => page.getByTestId("chart-share");

/** Holds the render at its font wait until `releaseRender()` runs, so the inputs can change mid-render. */
async function holdRender(page: Page): Promise<void> {
  await page.addInitScript(() => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    Object.assign(window, { __releaseRender: release });
    Object.defineProperty(document.fonts, "ready", { get: () => gate, configurable: true });
  });
}

const releaseRender = (page: Page) => page.evaluate(() => (window as unknown as { __releaseRender: () => void }).__releaseRender());

async function highlightMichigan(page: Page): Promise<void> {
  await expect(async () => {
    await page.getByTestId("team-highlight").selectOption("Michigan");
    // While an image renders, the offscreen export card holds a second copy of the chart; only the live one is checked.
    await expect(page.locator("xpath=//*[local-name()='g' and @data-team='Michigan' and not(ancestor::*[@data-testid='export-card'])]")).toHaveAttribute(
      "aria-pressed",
      "true",
      { timeout: 500 },
    );
  }).toPass();
}

/** Counts export cards ever mounted, so a card that renders and leaves between two polls is still seen. */
async function countExportCards(page: Page): Promise<void> {
  await page.addInitScript(() => {
    Object.assign(window, { __cards: 0 });
    new MutationObserver((records) => {
      for (const record of records)
        for (const node of record.addedNodes)
          if (node instanceof Element && (node.matches("[data-testid=export-card]") || node.querySelector("[data-testid=export-card]")))
            (window as unknown as { __cards: number }).__cards += 1;
    }).observe(document, { childList: true, subtree: true });
  });
}

const cardsMounted = (page: Page) => page.evaluate(() => (window as unknown as { __cards: number }).__cards);

/** Shares once with an expired gesture so an image is kept for the second tap. */
async function prepareReadyImage(page: Page): Promise<void> {
  await share(page).click();
  await expect(status(page)).toHaveText("Image ready: tap Share again");
  await expect(share(page)).toBeEnabled();
}


/** Clipboard that reports image support and records how the image promise of each write settled. */
async function stubClipboard(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const settled: string[] = [];
    Object.assign(window, { __clipboardSettled: settled });
    class FakeClipboardItem {
      constructor(public items: Record<string, Promise<Blob>>) {}
    }
    Object.defineProperty(window, "ClipboardItem", { value: FakeClipboardItem, configurable: true });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        write: async (items: FakeClipboardItem[]) => {
          try {
            await items[0].items["image/png"];
            settled.push("resolved");
          } catch {
            settled.push("rejected");
            throw new DOMException("Copy failed", "NotAllowedError");
          }
        },
      },
    });
  });
}

const clipboardSettled = (page: Page) => page.evaluate(() => (window as unknown as { __clipboardSettled: string[] }).__clipboardSettled);

/** Leaves the chart page client-side, which unmounts its export actions. */
async function leaveChartPage(page: Page): Promise<void> {
  await page.locator("a[href^='/ratings']:visible").first().click();
  await expect(page).toHaveURL(/\/ratings/);
  await expect(page.getByTestId("chart-export")).toHaveCount(0);
}

test.describe("share and export", () => {
  test("a share that loses its gesture is kept and shared on the next tap", async ({ page }) => {
    await scriptShare(page, ["expired"]);
    const downloads = countDownloads(page);
    await gotoHydrated(page, URL);
    await prepareReadyImage(page);
    await share(page).click();
    await expect.poll(async () => (await shareCalls(page)).length).toBe(2);
    const [first, second] = await shareCalls(page);
    expect(first).toMatchObject({ name: WEEK_3, title: TITLE });
    expect(second).toMatchObject({ name: WEEK_3, title: TITLE });
    expect(downloads.names).toEqual([]);
    await expect(status(page)).not.toHaveText(/could not/i);
  });

  test("changing the week after the image is ready shares a new image, never the old one", async ({ page }) => {
    await scriptShare(page, ["expired"]);
    await gotoHydrated(page, URL);
    await prepareReadyImage(page);
    await page.locator("#week-select").selectOption("2");
    await expect(page).toHaveURL(/week=2/);
    await expect(page.locator("g[data-team]").first()).toBeVisible();
    await share(page).click();
    await expect.poll(async () => (await shareCalls(page)).at(-1)?.name).toBe(WEEK_2);
    const names = (await shareCalls(page)).map((call) => call.name);
    expect(names.at(-1)).toBe(WEEK_2);
    // A stale reuse would have re-sent the Week 3 file straight away, with no new render.
    expect(names.filter((name) => name === WEEK_3).length).toBeLessThanOrEqual(1);
  });

  test("highlighting a team after the image is ready renders a new image", async ({ page }) => {
    await scriptShare(page, ["expired"]);
    await countExportCards(page);
    await gotoHydrated(page, URL);
    await prepareReadyImage(page);
    const shareCountBefore = (await shareCalls(page)).length;
    await expect(async () => {
      await page.getByTestId("team-highlight").selectOption("Michigan");
      await expect(page.locator("g[data-team='Michigan']")).toHaveAttribute("aria-pressed", "true", { timeout: 500 });
    }).toPass();
    // The kept image has no highlight: tapping must prepare a fresh one (the card is mounted again).
    const cardsBefore = await cardsMounted(page);
    await share(page).click();
    await expect.poll(() => cardsMounted(page)).toBeGreaterThan(cardsBefore);
    await expect.poll(async () => (await shareCalls(page)).length).toBe(shareCountBefore + 1);
  });

  test("switching theme after the image is ready renders a new image in the new theme", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await scriptShare(page, ["expired"]);
    await countExportCards(page);
    await gotoHydrated(page, URL);
    await prepareReadyImage(page);
    await page.evaluate(() => document.documentElement.classList.add("dark"));
    const cardsBefore = await cardsMounted(page);
    await share(page).click();
    await expect.poll(() => cardsMounted(page)).toBeGreaterThan(cardsBefore);
    await expect.poll(async () => (await shareCalls(page)).length).toBe(2);
    expect((await shareCalls(page)).map((call) => call.theme)).toEqual(["light", "dark"]);
  });

  test("dismissing the share sheet on the first attempt saves nothing and shows no error", async ({ page }) => {
    await scriptShare(page, ["abort"]);
    const downloads = countDownloads(page);
    await gotoHydrated(page, URL);
    await share(page).click();
    await expect.poll(async () => (await shareCalls(page)).length).toBe(1);
    await expect(share(page)).toBeEnabled();
    await expect(status(page)).toHaveText("");
    expect(downloads.names).toEqual([]);
    // Back to idle: the next tap starts a fresh share instead of a "tap again" retry.
    await share(page).click();
    await expect.poll(async () => (await shareCalls(page)).length).toBe(2);
    expect(downloads.names).toEqual([]);
  });

  test("dismissing the share sheet on the retry saves nothing and shows no error", async ({ page }) => {
    await scriptShare(page, ["expired", "abort"]);
    const downloads = countDownloads(page);
    await gotoHydrated(page, URL);
    await prepareReadyImage(page);
    await share(page).click();
    await expect.poll(async () => (await shareCalls(page)).length).toBe(2);
    await expect(share(page)).toBeEnabled();
    await expect(status(page)).toHaveText("");
    expect(downloads.names).toEqual([]);
  });

  test("a genuine failure on the retry falls back to downloading the image", async ({ page }) => {
    await scriptShare(page, ["expired", "fail"]);
    await gotoHydrated(page, URL);
    await prepareReadyImage(page);
    const download = page.waitForEvent("download");
    await share(page).click();
    expect((await download).suggestedFilename()).toBe(WEEK_3);
    await expect(status(page)).toHaveText("Image saved");
  });

  test("changing the chart mid-render says so, saves nothing and shares nothing", async ({ page }) => {
    await scriptShare(page, []);
    await holdRender(page);
    const downloads = countDownloads(page);
    await gotoHydrated(page, URL);
    await share(page).click();
    await expect(status(page)).toHaveText("Creating image…");
    await highlightMichigan(page);
    await releaseRender(page);
    await expect(status(page)).toHaveText("The chart changed. Tap again.");
    await expect(status(page)).not.toHaveText(/could not/i);
    await expect(share(page)).toBeEnabled();
    expect(await shareCalls(page)).toEqual([]);
    expect(downloads.names).toEqual([]);
  });

  test("changing the chart mid-download says so and saves nothing", async ({ page }) => {
    await holdRender(page);
    const downloads = countDownloads(page);
    await gotoHydrated(page, URL);
    await page.getByTestId("chart-download").click();
    await expect(status(page)).toHaveText("Creating image…");
    await highlightMichigan(page);
    await releaseRender(page);
    await expect(status(page)).toHaveText("The chart changed. Tap again.");
    await expect(status(page)).not.toHaveText(/could not/i);
    expect(downloads.names).toEqual([]);
  });

  test("changing the highlight after a gesture failure clears the stale 'Image ready' text", async ({ page }) => {
    await scriptShare(page, ["expired"]);
    await gotoHydrated(page, URL);
    await prepareReadyImage(page);
    await highlightMichigan(page);
    await expect(status(page)).toHaveText("");
    await expect(status(page)).not.toHaveText(/Image ready/);
  });

  test("leaving the page mid-share never calls navigator.share", async ({ page }) => {
    await scriptShare(page, []);
    await holdRender(page);
    const downloads = countDownloads(page);
    const errors: Error[] = [];
    page.on("pageerror", (error) => errors.push(error));
    await gotoHydrated(page, URL);
    await share(page).click();
    await expect(status(page)).toHaveText("Creating image…");
    await leaveChartPage(page);
    await releaseRender(page);
    await page.waitForTimeout(1000);
    expect(await shareCalls(page)).toEqual([]);
    expect(downloads.names).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("leaving the page mid-download saves nothing", async ({ page }) => {
    await holdRender(page);
    const downloads = countDownloads(page);
    const errors: Error[] = [];
    page.on("pageerror", (error) => errors.push(error));
    await gotoHydrated(page, URL);
    await page.getByTestId("chart-download").click();
    await expect(status(page)).toHaveText("Creating image…");
    await leaveChartPage(page);
    await releaseRender(page);
    await page.waitForTimeout(1000);
    expect(downloads.names).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("leaving the page mid-copy never completes the clipboard write", async ({ page }) => {
    await stubClipboard(page);
    await holdRender(page);
    const errors: Error[] = [];
    page.on("pageerror", (error) => errors.push(error));
    await gotoHydrated(page, URL);
    await page.getByTestId("chart-copy").click();
    await expect(status(page)).toHaveText("Creating image…");
    await leaveChartPage(page);
    await releaseRender(page);
    await expect.poll(() => clipboardSettled(page)).toEqual(["rejected"]);
    await page.waitForTimeout(500);
    expect(await clipboardSettled(page)).toEqual(["rejected"]);
    expect(errors).toEqual([]);
  });

  test("control: a share and a copy started the same way, without leaving, complete", async ({ page }) => {
    await scriptShare(page, []);
    await stubClipboard(page);
    await holdRender(page);
    await gotoHydrated(page, URL);
    await page.getByTestId("chart-copy").click();
    await expect(status(page)).toHaveText("Creating image…");
    await releaseRender(page);
    await expect.poll(() => clipboardSettled(page)).toEqual(["resolved"]);
    await expect(share(page)).toBeEnabled();
    await share(page).click();
    await expect.poll(async () => (await shareCalls(page)).length).toBe(1);
    expect((await shareCalls(page))[0]).toMatchObject({ name: WEEK_3 });
  });
});
