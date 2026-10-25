import { expect, test } from "@playwright/test";

for (const width of [320, 390, 430]) {
  test(`mobile chart settings reflow at ${width}px and retain local configuration`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/stats?chart=efficiency&week=3");
    const select = page.getByTestId("chart-select");
    await expect(select.locator("option")).toHaveCount(5);
    expect((await select.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await expect(page.getByTestId("team-search")).toBeVisible();
    await expect(page.getByTestId("conference-filter")).toHaveCount(1);
    await expect(page.getByTestId("conference-filter")).not.toBeVisible();
    await page.getByRole("button", { name: "Chart settings", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Chart settings", exact: true });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: "Chart settings" })).toBeFocused();
    await expect(page.locator("body")).toHaveCSS("position", "fixed");
    await dialog.getByTestId("conference-filter").selectOption("SEC");
    await dialog.getByRole("button", { name: "Yards / Success", exact: true }).click();
    for (const control of await dialog.locator("button, select, a[aria-current]").all()) {
      expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Chart settings", exact: true })).toBeFocused();
    await expect(page.locator("body")).not.toHaveCSS("position", "fixed");
    await expect(page.getByTestId("chart-settings-summary")).toContainText("SEC");
    await expect(page.getByTestId("chart-settings-summary")).toContainText("Yards");
    await page.getByRole("button", { name: "Chart settings", exact: true }).click();
    await expect(dialog.getByTestId("conference-filter")).toHaveValue("SEC");
    await expect(dialog.getByRole("button", { name: "Yards / Success", exact: true })).toHaveAttribute("aria-pressed", "true");
    await dialog.getByRole("button", { name: "Close", exact: true }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
    await expect(page).not.toHaveURL(/inspector|settings=/);
  });
}

test("settings trigger is absent until hydration, never locks the body early, then opens the sheet", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  // Hold every script chunk so the server-rendered page stays un-hydrated.
  let release!: () => void;
  const hold = new Promise<void>((resolve) => { release = resolve; });
  await page.route(/\/_next\/static\/.*\.js/, async (route) => { await hold; await route.continue(); });
  await page.goto("/stats?chart=efficiency&week=3", { waitUntil: "domcontentloaded" });
  // The trigger is portalled into the sticky bar's slot by the client, so the server HTML has none to tap early.
  await expect(page.getByTestId("chart-picker")).toBeVisible();
  await expect(page.getByRole("button", { name: "Chart settings", exact: true })).toHaveCount(0);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator("body")).not.toHaveCSS("position", "fixed");
  release();
  const trigger = page.getByRole("button", { name: "Chart settings", exact: true });
  await expect(trigger).toBeEnabled();
  expect((await trigger.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await trigger.click();
  await expect(page.getByRole("dialog", { name: "Chart settings", exact: true })).toBeVisible();
  await expect(page.locator("body")).toHaveCSS("position", "fixed");
});

test("week navigation keeps the sheet open for consecutive adjustments, and close releases body styles", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/stats?chart=efficiency&week=3");
  await page.getByRole("button", { name: "Chart settings", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await page.getByLabel("Through Week", { exact: true }).selectOption("2");
  await expect(page).toHaveURL(/week=2/);
  // Sheet must remain open across in-sheet setting adjustments:
  await expect(dialog).toBeVisible();
  await expect(page.locator("body")).toHaveCSS("position", "fixed");
  // Explicit close dismisses the sheet and cleans up body styles:
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator("body")).not.toHaveCSS("position", "fixed");
  await expect(page.getByTestId("chart-settings-summary")).toContainText("Through Week 2");
});

test("resizing an open settings sheet restores desktop controls once", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/stats?chart=efficiency&week=3");
  await page.getByRole("button", { name: "Chart settings", exact: true }).click();
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByTestId("conference-filter")).toHaveCount(1);
  await expect(page.getByTestId("conference-filter")).toBeVisible();
  await expect(page.getByTestId("team-search")).toBeVisible();
  await expect(page.locator("body")).not.toHaveCSS("position", "fixed");
});
