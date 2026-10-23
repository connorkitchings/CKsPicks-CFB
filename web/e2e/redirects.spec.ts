import { expect, test } from "@playwright/test";

// Legacy URLs answer a 307 with the query string preserved.
const redirects = [
  ["/results?week=5", "/?week=5"],
  ["/results", "/"],
  ["/matchup", "/"],
  ["/matchup?week=5", "/?week=5"],
  ["/performance", "/model"],
  ["/methodology", "/model/method"],
  ["/charts", "/stats"],
  ["/charts?chart=x", "/stats?chart=x"],
  ["/charts/anything?chart=x&team=Alabama", "/stats/anything?chart=x&team=Alabama"],
] as const;

for (const [from, to] of redirects) {
  test(`${from} redirects to ${to} with a 307`, async ({ request }) => {
    const response = await request.get(from, { maxRedirects: 0 });
    expect(response.status()).toBe(307);
    const location = new URL(response.headers()["location"], "http://127.0.0.1");
    expect(location.pathname + location.search).toBe(to);
  });
}

test("/matchup/:id is not redirected", async ({ request }) => {
  const response = await request.get("/matchup/1", { maxRedirects: 0 });
  expect(response.status()).toBe(200);
});

test("/methodology keeps the elite-reference anchor in the browser", async ({ page }) => {
  await page.goto("/methodology#elite-reference");
  await expect(page).toHaveURL(/\/model\/method#elite-reference$/);
});
