import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

test("global team search supports canonical aliases, keyboard navigation, empty results and Escape", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await gotoHydrated(page, "/model");
  const finder = page.getByRole("combobox", { name: "Find a team" });
  await finder.fill("San Jose");
  await expect(page.getByRole("option", { name: "San José State", exact: true })).toBeVisible();
  await finder.press("Escape");
  await expect(page.getByRole("listbox", { name: "Matching teams" })).toHaveCount(0);
  await expect(finder).toBeFocused();
  await finder.fill("not-a-real-college");
  await expect(page.locator("[aria-live=polite]").filter({ hasText: "No matching team" })).toHaveCount(1);
  await expect(page.getByRole("listbox", { name: "Matching teams" })).toHaveCount(0);
  await finder.press("Enter");
  await expect(page).toHaveURL(/\/model$/);
  await finder.fill("Michigan");
  const options = page.getByRole("listbox", { name: "Matching teams" }).getByRole("option");
  await expect(options.first()).toHaveText("Michigan");
  await finder.press("ArrowDown");
  await expect(finder).toHaveAttribute("aria-activedescendant", await options.nth(1).getAttribute("id") as string);
  await finder.press("ArrowUp");
  await finder.press("Enter");
  await expect(page).toHaveURL(/\/teams\/Michigan\?season=2026$/);
});

for (const width of [320, 640, 1280]) {
  for (const theme of ["light", "dark"] as const) {
    test(`shared shell at ${width}px in ${theme} theme`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("theme", value), theme);
      await gotoHydrated(page, "/model");
      await expect(page.locator("html")).toHaveCSS("color-scheme", theme);
      const navigation = page.getByRole("navigation", { name: "Main navigation", exact: true });
      await expect(navigation).toHaveCount(1);
      await expect(navigation.getByRole("link")).toHaveText(["Games", "Teams", "Graphs", "Model"]);
      await expect(navigation.getByRole("link", { name: "Teams", exact: true })).toHaveAttribute("href", "/teams");
      await expect(navigation.getByRole("link", { name: "Model", exact: true })).toHaveAttribute("aria-current", "page");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      const box = (await navigation.boundingBox())!;
      if (width < 640) {
        expect(box.y + box.height).toBeCloseTo(900, 0);
        await page.getByRole("button", { name: "Menu", exact: true }).click();
        const dialog = page.getByRole("dialog", { name: "Menu", exact: true });
        const finder = dialog.getByRole("combobox", { name: "Find a team" });
        await finder.fill("Connecticut");
        await expect(dialog.getByRole("option", { name: "UConn", exact: true })).toBeVisible();
        await finder.press("Escape");
        await expect(dialog).toBeVisible();
        await expect(finder).toBeFocused();
        await finder.press("Escape");
        await expect(dialog).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Menu", exact: true })).toBeFocused();
      } else {
        const header = (await page.getByRole("banner").boundingBox())!;
        expect(box.y).toBeGreaterThanOrEqual(header.y);
        expect(box.y + box.height).toBeLessThanOrEqual(header.y + header.height);
        await expect(page.getByRole("banner").getByRole("combobox", { name: "Find a team" })).toBeVisible();
      }
      await page.screenshot({ path: testInfo.outputPath(`shell-${width}-${theme}.png`) });
    });
  }
}

test("keyboard search keeps the active option visible without mouse scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await gotoHydrated(page, "/model");
  const finder = page.getByRole("combobox", { name: "Find a team" });
  await finder.fill("state");
  const list = page.getByRole("listbox", { name: "Matching teams" });
  const options = list.getByRole("option");
  const count = await options.count();
  expect(count).toBeGreaterThan(6);
  const assertVisibleInList = async (index: number) => {
    const listBox = (await list.boundingBox())!;
    const optionBox = (await options.nth(index).boundingBox())!;
    expect(optionBox.y).toBeGreaterThanOrEqual(listBox.y);
    expect(optionBox.y + optionBox.height).toBeLessThanOrEqual(listBox.y + listBox.height);
    await expect(finder).toHaveAttribute("aria-activedescendant", (await options.nth(index).getAttribute("id"))!);
    await expect(finder).toBeFocused();
  };
  await expect(page.locator("[aria-live=polite]").filter({ hasText: /teams found/ })).toHaveCount(1);
  for (let i = 1; i < count; i++) await finder.press("ArrowDown");
  await assertVisibleInList(count - 1);
  const scrollBeforeHover = await list.evaluate((element) => element.scrollTop);
  await options.first().dispatchEvent("mouseover");
  expect(await list.evaluate((element) => element.scrollTop)).toBe(scrollBeforeHover);
  for (let i = 1; i < count; i++) await finder.press("ArrowUp");
  await assertVisibleInList(0);
  await finder.press("Escape");
  await expect(list).toHaveCount(0);
  await expect(finder).toBeFocused();
});
