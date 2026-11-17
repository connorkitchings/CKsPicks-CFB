import { expect, test } from "@playwright/test";

const SUFFIX = " · Stratum CFB";

/** One entry per route family: the exact document title (the brand is appended by the root layout). */
const ROUTES: [path: string, page: string][] = [
  ["/?week=5", "Week 5 Games"],
  ["/teams", "Teams"],
  ["/model", "Model"],
  ["/model/method", "How the model works"],
  ["/teams/Texas", "Texas"],
  ["/stats?chart=efficiency", "Efficiency vs explosiveness graph"],
  ["/stats?chart=adjusted", "Adjusted PPA/play graph"],
  ["/stats?chart=downs", "Situational downs graph"],
  ["/stats?chart=finishing-drives", "Finishing drives graph"],
  ["/stats?chart=possession", "Possession efficiency graph"],
  ["/stats?chart=net-success", "Net success rate graph"],
  ["/stats?chart=game-log", "Game log graph"],
];

const NOT_FOUND: string[] = ["/matchup/999999999", "/teams/Not_A_Team", "/no-such-route"];

const content = (page: import("@playwright/test").Page, selector: string) =>
  page.locator(selector).first().getAttribute("content");

test.describe("per-route metadata", () => {
  test("every route family has its own title, description and share tags", async ({ page }) => {
    const titles = new Set<string>();
    for (const [path, name] of ROUTES) {
      await page.goto(path);
      const title = `${name}${SUFFIX}`;
      await expect(page, path).toHaveTitle(title);
      expect(await content(page, 'meta[property="og:title"]'), path).toBe(title);
      expect(await content(page, 'meta[name="twitter:title"]'), path).toBe(title);
      expect(await content(page, 'meta[name="description"]'), path).toBeTruthy();
      expect(await content(page, 'meta[property="og:description"]'), path).toBeTruthy();
      expect(await content(page, 'meta[property="og:url"]'), path).toContain(new URL(page.url()).pathname);
      for (const tag of ['meta[name="description"]', 'meta[property="og:title"]']) {
        expect(await content(page, tag), `${path} ${tag} must not say V5`).not.toMatch(/\bV5\b/);
      }
      titles.add(title);
    }
    expect(titles.size).toBe(ROUTES.length);
  });

  test("a matchup link previews as that game, not the home page", async ({ page }) => {
    await page.goto("/matchup/1");
    const title = await page.title();
    expect(title).toMatch(/^.+ at .+ · Stratum CFB$/);
    expect(await content(page, 'meta[property="og:title"]')).toBe(title);
    expect(await content(page, 'meta[property="og:url"]')).toContain("/matchup/1");
  });

  for (const path of NOT_FOUND) {
    test(`${path} is titled "Page not found"`, async ({ page }) => {
      await page.goto(path);
      await expect(page).toHaveTitle(`Page not found${SUFFIX}`);
      expect(await content(page, 'meta[property="og:title"]')).toBe(`Page not found${SUFFIX}`);
    });
  }
});
