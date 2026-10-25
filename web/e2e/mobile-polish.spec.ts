import { expect, test, type Page } from "@playwright/test";
import { gotoHydrated } from "./helpers";

const PAGES = [
  ["Games", "/"],
  ["Ratings", "/ratings"],
  ["Graphs", "/stats?chart=efficiency&week=3"],
  ["Model", "/model"],
  ["Matchup", "/matchup/1"],
] as const;
const VIEWPORTS = [{ width: 390, height: 844 }, { width: 320, height: 568 }];

const INTERACTIVE = "a[href], button, summary, select, input:not([type=hidden]), [role=tab], [role=button]";

/**
 * Visible interactive controls under 44px in either dimension inside `root`. Exempt: inline text
 * links (WCAG's in-sentence exception), the screen-reader-only skip link and marks drawn inside a
 * chart SVG (their targets are the chart's own contract).
 */
async function undersized(page: Page, root: string): Promise<string[]> {
  return page.evaluate(({ root, selector }) => {
    const found: string[] = [];
    for (const el of document.querySelector(root)!.querySelectorAll(selector)) {
      const box = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      if (box.width <= 1 || box.height <= 1 || style.visibility === "hidden" || style.display === "inline") continue;
      if (el.closest("svg, [hidden], dialog:not([open])")) continue;
      if (box.width < 43.5 || box.height < 43.5) {
        const name = el.getAttribute("aria-label") ?? el.textContent?.trim().slice(0, 30) ?? "";
        found.push(`${el.tagName.toLowerCase()} "${name}" ${Math.round(box.width)}x${Math.round(box.height)}`);
      }
    }
    return found;
  }, { root, selector: INTERACTIVE });
}

for (const viewport of VIEWPORTS) {
  test.describe(`phone polish at ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport, hasTouch: true });

    for (const [title, url] of PAGES) {
      test(`${title}: every control on the page is at least 44px tall and wide`, async ({ page }) => {
        await gotoHydrated(page, url);
        expect(await undersized(page, "body")).toEqual([]);
      });
    }

    test("the menu and filter sheets hold only 44px controls", async ({ page }) => {
      const sheets: [url: string, trigger: string, dialog: string][] = [
        ["/", "app-menu-button", "app-menu-dialog"],
        ["/", "slate-filters-button", "slate-filters-dialog"],
        ["/ratings", "ratings-filters-button", "ratings-filters-dialog"],
        ["/stats?chart=efficiency&week=3", "app-menu-button", "app-menu-dialog"],
      ];
      for (const [url, trigger, dialog] of sheets) {
        await gotoHydrated(page, url);
        await page.getByTestId(trigger).click();
        await expect(page.getByTestId(dialog)).toBeVisible();
        expect(await undersized(page, `[data-testid="${dialog}"]`), `${dialog} on ${url}`).toEqual([]);
        await page.keyboard.press("Escape");
        await expect(page.getByTestId(dialog)).toBeHidden();
      }
      await gotoHydrated(page, "/stats?chart=efficiency&week=3");
      await page.getByRole("button", { name: "Chart settings" }).click();
      await expect(page.getByTestId("chart-settings-dialog")).toBeVisible();
      expect(await undersized(page, '[data-testid="chart-settings-dialog"]')).toEqual([]);
    });

    test("all five pages share one horizontal padding and one vertical rhythm", async ({ page }) => {
      const layouts: Record<string, unknown> = {};
      for (const [title, url] of PAGES) {
        await gotoHydrated(page, url);
        layouts[title] = await page.evaluate(() => {
          const main = document.querySelector("main")!;
          const box = main.getBoundingClientRect();
          const style = getComputedStyle(main);
          const firstChild = [...main.children].find((child) => getComputedStyle(child).position !== "absolute")!;
          const firstCard = main.querySelector("[data-card]")!.getBoundingClientRect();
          return {
            left: box.left,
            width: box.width,
            paddingLeft: style.paddingLeft,
            paddingRight: style.paddingRight,
            paddingTop: style.paddingTop,
            paddingBottom: style.paddingBottom,
            // Gap below the first section: flex gap (Ratings) or the space-y margin (the rest).
            sectionGap: (parseFloat(style.rowGap) || 0) + parseFloat(getComputedStyle(firstChild).marginBottom),
            firstCardLeft: Math.round(firstCard.left),
          };
        });
      }
      for (const [title] of PAGES) {
        expect(layouts[title], title).toEqual({
          left: 0,
          width: viewport.width,
          paddingLeft: "16px",
          paddingRight: "16px",
          paddingTop: "8px",
          paddingBottom: "16px",
          sectionGap: 8,
          firstCardLeft: 16,
        });
      }
    });
  });
}

test.describe("press feedback and reduced motion", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

  /** Presses (mouse down, no release), waits for any transition to settle, returns the control's opacity and transform, then cancels the click. */
  async function pressed(page: Page, selector: string) {
    const target = page.locator(selector).first();
    const box = (await target.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    try {
      return await target.evaluate(async (el) => {
        await Promise.all(el.getAnimations().map((animation) => animation.finished));
        return { opacity: getComputedStyle(el).opacity, transform: getComputedStyle(el).transform };
      });
    } finally {
      await page.mouse.move(0, 0); // leaving before release cancels the click
      await page.mouse.up();
    }
  }

  test("a pressed phone control dims and shrinks slightly", async ({ page }) => {
    await gotoHydrated(page, "/");
    for (const selector of ['[data-testid="app-menu-button"]', "li[id^='game-'] a[href^='/matchup']"]) {
      const state = await pressed(page, selector);
      expect(state.opacity, selector).toBe("0.7");
      expect(state.transform, selector).toBe("matrix(0.985, 0, 0, 0.985, 0, 0)");
    }
  });

  test("a pressed control is untouched from 640px up", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 800 });
    await gotoHydrated(page, "/ratings");
    const state = await pressed(page, 'a[href^="/teams/"]:visible');
    expect(state).toEqual({ opacity: "1", transform: "none" });
  });

  test.describe("with reduced motion", () => {
    test.beforeEach(async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
    });

    test("a pressed control still dims but does not move", async ({ page }) => {
      await gotoHydrated(page, "/");
      expect(await pressed(page, '[data-testid="app-menu-button"]')).toEqual({ opacity: "0.7", transform: "none" });
    });

    test("sheets, bars and disclosures run no transition or animation", async ({ page }) => {
      await gotoHydrated(page, "/");
      await page.getByTestId("app-menu-button").click();
      const dialog = page.getByTestId("app-menu-dialog");
      await expect(dialog).toBeVisible();
      const motion = await page.evaluate(() => {
        const durations = (el: Element) => {
          const style = getComputedStyle(el);
          return [...style.transitionDuration.split(", "), ...style.transitionDelay.split(", ")].every((value) => parseFloat(value) === 0);
        };
        const nodes = [
          document.querySelector('[data-testid="app-menu-dialog"]')!,
          document.querySelector('[data-testid="app-bar"]')!,
          document.querySelector("dialog button")!,
          document.querySelector("details, summary")!,
        ];
        return {
          transitionsOff: nodes.map(durations),
          running: document.getAnimations().filter((animation) => animation.playState === "running").length,
          smoothScroll: getComputedStyle(document.documentElement).scrollBehavior,
        };
      });
      expect(motion).toEqual({ transitionsOff: [true, true, true, true], running: 0, smoothScroll: "auto" });
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();
    });
  });
});
