import { expect, test } from "@playwright/test";

for (const width of [320, 390, 430]) {
  test(`mobile chart settings reflow at ${width}px and retain local configuration`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/stats?chart=efficiency&week=3");
    const picker = page.getByTestId("chart-picker");
    const chips = picker.locator("a:visible");
    await expect(chips).toHaveCount(5);
    for (const chip of await chips.all()) expect((await chip.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await expect(page.getByTestId("team-search")).toBeVisible();
    await expect(page.getByTestId("conference-filter")).toHaveCount(1);
    await expect(page.getByTestId("conference-filter")).not.toBeVisible();
    await page.getByRole("button", { name: "Chart settings", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Chart settings", exact: true });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Close", exact: true })).toBeFocused();
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

test("week navigation closes the sheet and releases body styles", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/stats?chart=efficiency&week=3");
  await page.getByRole("button", { name: "Chart settings", exact: true }).click();
  await page.getByLabel("Through Week", { exact: true }).selectOption("2");
  await expect(page).toHaveURL(/week=2/);
  await expect(page.getByRole("dialog")).not.toBeVisible();
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
