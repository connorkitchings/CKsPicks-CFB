import { expect, test, type Page } from "@playwright/test";
import { gotoHydrated } from "./helpers";

/**
 * Touch-target sweep: on touch devices (phone and tablet width, `pointer: coarse`) every visible
 * interactive element, including links inside prose, has a hit area at least 44px tall. Compact
 * sizes are gated on the `pointer-fine:` variant, so a tablet must not fall back to them.
 */

const ROUTES = [
  ["Games", "/"],
  ["Teams", "/teams"],
  ["Teams résumé list", "/teams?group=resume"],
  ["Team page", "/teams/Texas"],
  ["Matchup", "/matchup/1"],
  ["Graphs", "/stats?chart=efficiency&week=3"],
  ["Model", "/model"],
  ["Model method", "/model/method"],
] as const;

const VIEWPORTS = [
  { width: 390, height: 844 },
  { width: 820, height: 1180 },
] as const;

const INTERACTIVE = "a[href], button, summary, select, input:not([type=hidden]), textarea, [role=tab], [role=button], [role=checkbox], [role=switch], [role=combobox]";

const MIN_HEIGHT = 44;
const MIN_WIDTH = 24;
const TOLERANCE = 0.5;

/**
 * Genuine exemptions. `match` is tested against `tag "label" WxH`.
 */
const ALLOW_LIST: readonly { route: string; match: RegExp; reason: string }[] = [
  // From `sm:` up the unit-section summary is a static heading: UnitDetails removes it from the tab
  // order (tabindex -1) and cancels its click, so it is not an interactive target at 820px.
  { route: "Team page", match: /^summary "(Offense|Defense)/, reason: "static heading from sm:, not toggleable" },
];

async function undersized(page: Page): Promise<string[]> {
  return page.evaluate(({ selector, minHeight, minWidth, tolerance }) => {
    const found: string[] = [];
    for (const el of document.querySelectorAll(selector)) {
      const style = getComputedStyle(el);
      if (style.visibility === "hidden" || style.display === "none") continue;
      if (el.closest("svg, [hidden], dialog:not([open]), [aria-hidden=true], [inert]")) continue;
      // An inline link that wraps counts by its tallest line box.
      const rects = [...el.getClientRects()].filter((rect) => rect.width > 0 && rect.height > 0);
      if (rects.length === 0) continue;
      const height = Math.max(...rects.map((rect) => rect.height));
      const width = Math.max(...rects.map((rect) => rect.width));
      // Visually hidden (sr-only skip link before focus, sr-only form controls): clipped to a 1px box.
      if (width <= 1 || height <= 1) continue;
      if (height + tolerance < minHeight || width + tolerance < minWidth) {
        const label = el.getAttribute("aria-label") ?? el.textContent?.trim().slice(0, 40) ?? "";
        found.push(`${el.tagName.toLowerCase()} "${label}" ${Math.round(width)}x${Math.round(height)}`);
      }
    }
    return found;
  }, { selector: INTERACTIVE, minHeight: MIN_HEIGHT, minWidth: MIN_WIDTH, tolerance: TOLERANCE });
}

for (const viewport of VIEWPORTS) {
  test.describe(`touch targets at ${viewport.width}px`, () => {
    test.use({ viewport, hasTouch: true });

    for (const [title, url] of ROUTES) {
      test(`${title}: every interactive element is at least 44px tall`, async ({ page }) => {
        await gotoHydrated(page, url);
        expect(await page.evaluate(() => matchMedia("(pointer: coarse)").matches), "touch emulation reports a coarse pointer").toBe(true);
        const failures = (await undersized(page)).filter(
          (entry) => !ALLOW_LIST.some((rule) => rule.route === title && rule.match.test(entry)),
        );
        expect(failures, `${title} at ${viewport.width}px`).toEqual([]);
      });
    }
  });
}
