import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

/** Automated WCAG 2 A/AA scan: no serious or critical violation on any main route in either theme. */

const ROUTES = [
  ["Games", "/"],
  ["Teams", "/teams"],
  ["Team page", "/teams/Texas"],
  ["Matchup", "/matchup/1"],
  ["Graphs", "/stats?chart=efficiency&week=3"],
  ["Model", "/model"],
  ["Model method", "/model/method"],
] as const;

for (const theme of ["light", "dark"] as const) {
  test.describe(`axe in ${theme} theme`, () => {
    for (const [title, url] of ROUTES) {
      test(`${title}: no serious or critical WCAG A/AA violations`, async ({ page }) => {
        await page.addInitScript((value) => localStorage.setItem("theme", value), theme);
        await gotoHydrated(page, url);
        const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
        const blocking = violations
          .filter((v) => v.impact === "serious" || v.impact === "critical")
          .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => `${n.target.join(" ")} ${n.html.slice(0, 200)}`).join(" || ")}`);
        expect(blocking, `${title} in ${theme} theme`).toEqual([]);
      });
    }
  });
}
