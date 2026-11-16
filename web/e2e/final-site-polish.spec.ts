import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

test.use({ viewport: { width: 320, height: 568 } });

for (const theme of ["light", "dark"] as const) {
  test(`compact scatter dot outline in ${theme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: theme });
    await gotoHydrated(page, "/stats?chart=efficiency&week=3");
    const dot = page.locator('g[data-team] [data-mark="dot"] circle:last-child').first();
    const colors = await dot.evaluate((node) => ({
      stroke: getComputedStyle(node).stroke,
      width: getComputedStyle(node).strokeWidth,
      background: getComputedStyle(node.closest("svg")!.querySelector(":scope > rect")!).fill,
    }));
    expect(colors.width).toBe("1px");
    if (theme === "light") expect(colors.stroke).toBe(colors.background);
    else {
      const luminance = (color: string) => {
        const c = color.match(/\d+/g)!.slice(0, 3).map(Number).map((value) => {
          const channel = value / 255;
          return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
      };
      expect((luminance(colors.stroke) + 0.05) / (luminance(colors.background) + 0.05)).toBeGreaterThanOrEqual(3);
    }
  });
}

test("long matchup names wrap and native disclosures work at 320px", async ({ page }) => {
  await gotoHydrated(page, "/matchup/1");
  const tape = page.getByTestId("tale-of-the-tape");
  const headings = tape.locator(":scope > div:nth-child(2) > div > span.text-ink-primary");
  await expect(headings).toHaveCount(2);
  const names = ["University of Southern Mississippi", "North Carolina State University"];
  for (let i = 0; i < 2; i++) {
    const heading = headings.nth(i);
    await heading.locator("span").first().evaluate((node, name) => { node.textContent = name; }, names[i]);
    await expect(heading).toContainText(names[i]);
    const bounds = await heading.evaluate((node) => {
      const [name, role] = [...node.children].map((child) => child.getBoundingClientRect());
      return { nameBottom: name.bottom, roleTop: role.top, scrollWidth: node.scrollWidth, width: node.clientWidth };
    });
    expect(bounds.roleTop).toBeGreaterThanOrEqual(bounds.nameBottom - 1);
    expect(bounds.scrollWidth).toBeLessThanOrEqual(bounds.width);
    const fitsWords = await heading.evaluate((node) => {
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d")!;
      context.font = getComputedStyle(node).font;
      return ["Eastern", "Michigan", "Offense"].every((word) => context.measureText(word).width <= node.clientWidth);
    });
    expect(fitsWords).toBe(true);
  }
  await expect(tape.locator('[title="Model Offense Rank"]')).toBeVisible();
  await expect(tape.locator('[title="Model Defense Rank"]')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  for (const name of ["Full unit statistics", "Full rating breakdown"]) {
    const summary = page.locator("summary").filter({ hasText: name });
    const details = summary.locator("..");
    expect((await summary.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await expect(details).not.toHaveAttribute("open");
    await expect(summary.locator('svg[aria-hidden="true"]')).toBeVisible();
    await summary.focus();
    await page.keyboard.press("Enter");
    await expect(details).toHaveAttribute("open", "");
    await summary.click();
    await expect(details).not.toHaveAttribute("open");
  }
});
