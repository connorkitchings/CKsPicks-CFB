import { expect, test, type Page } from "@playwright/test";

const target = (page: Page) => page.getByRole("group", { name: "Pick target" });

/** Matches the `sm` breakpoint, below which ResponsiveDisclosure collapses. */
const isPhone = (page: Page) => (page.viewportSize()?.width ?? 1280) < 640;

async function expectUniqueIds(page: Page) {
  const ids = await page.locator("[id]").evaluateAll(nodes => nodes.map(node => node.id));
  expect(ids.filter((id, i) => ids.indexOf(id) !== i)).toEqual([]);
}

test.describe("model section", () => {
  test("record page marks its tab current and has unique ids", async ({ page }) => {
    await page.goto("/model");
    const tabs = page.getByRole("navigation", { name: "Model sections" });
    await expect(tabs.getByRole("link", { name: "Record" })).toHaveAttribute("aria-current", "page");
    await expect(tabs.getByRole("link", { name: "How it works" })).toHaveAttribute("href", "/model/method");
    await expect(tabs.getByRole("link", { name: "How it works" })).not.toHaveAttribute("aria-current", "page");
    await expectUniqueIds(page);
  });

  test("method page links back, keeps the elite-reference anchor and has unique ids", async ({ page }) => {
    await page.goto("/model/method");
    await expect(page.getByRole("heading", { level: 1, name: "How the model works" })).toBeVisible();
    const tabs = page.getByRole("navigation", { name: "Model sections" });
    await expect(tabs.getByRole("link", { name: "How it works" })).toHaveAttribute("aria-current", "page");
    for (const link of await tabs.getByRole("link").all()) {
      expect((await link.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
    await expect(page.locator("#elite-reference")).toHaveCount(1);
    await expect(page.getByRole("heading", { name: "Elite reference" })).toBeVisible();
    await expectUniqueIds(page);
    await tabs.getByRole("link", { name: "Record" }).click();
    await expect(page).toHaveURL(/\/model$/);
  });

  test("method page fits the viewport at 320px", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.goto("/model/method#elite-reference");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  });
});

test.describe("model page is accuracy-only", () => {
  test("leads with separate records, keeps diagnostics collapsed on phones", async ({ page }) => {
    await page.goto("/model");
    await expect(page.getByRole("heading", { name: "Season record & performance" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "2026 V5 cumulative record" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Designated prospective V5 performance" })).toHaveCount(0);

    const summary = page.getByRole("region", { name: "Forecast accuracy summary", exact: true });
    await expect(summary.getByRole("button", { name: /Spread/ })).toContainText("1–1–1");
    await expect(summary.getByRole("button", { name: /Totals/ })).toContainText("1–1–1");
    await expect(summary.getByText("50.0%", { exact: true })).toHaveCount(2);
    await expect(summary.getByText("-2.4 pp vs 52.4% break-even", { exact: true })).toHaveCount(2);
    await expect(page.locator("details[open]")).toHaveCount(0);
    await expect(page.getByText("Graded picks audit")).toHaveCount(0);

    // Phones collapse diagnostics behind the summary; wider screens show them inline.
    if (isPhone(page)) await page.getByText("Season-wide forecast diagnostics", { exact: true }).filter({ visible: true }).click();
    const accuracy = page.getByRole("region", { name: "Forecast accuracy", exact: true }).filter({ visible: true });
    await expect(accuracy.getByText("Spread MAE", { exact: true })).toBeVisible();
    await expect(accuracy.getByText("Total 95% interval", { exact: true })).toBeVisible();
    await expect(accuracy.getByText("4.5 pts", { exact: true })).toBeVisible();
    await target(page).getByRole("button", { name: "Totals", exact: true }).click();
    await expect(accuracy.getByText("4.5 pts", { exact: true })).toBeVisible();

    for (const banned of [/\bROI\b/, /profit/i, /\bunits?\b/i, /net return/i, /closing line/i, /-110/, /\d\.\d+u\b/]) {
      await expect(page.locator("body").getByText(banned)).toHaveCount(0);
    }
  });

  test("target filter narrows weekly records", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/model");
    await target(page).getByRole("button", { name: "Totals", exact: true }).click();
    await expect(page.getByRole("columnheader", { name: "Total (W-L-P)" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Spread (W-L-P)" })).toHaveCount(0);
    await target(page).getByRole("button", { name: "Spreads", exact: true }).click();
    await expect(page.getByRole("columnheader", { name: "Spread (W-L-P)" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Total (W-L-P)" })).toHaveCount(0);
  });

  for (const width of [320, 390, 640, 1280]) {
    test(`summary and weekly links stay usable at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/model");
      await expect(page.getByRole("heading", { name: "Season record & performance" })).toBeVisible();
      const weekly = page.getByRole("region", { name: "Weekly accuracy breakdown" });
      const link = weekly.getByRole("link", { name: "Week 0", exact: true }).filter({ visible: true });
      await expect(link).toHaveAttribute("href", "/?week=0");
      const box = await link.boundingBox();
      // Phone rows are 44px touch targets; the desktop table link stays compact.
      if (isPhone(page)) expect(box!.height).toBeGreaterThanOrEqual(44);
      else expect(box!.height).toBeLessThanOrEqual(40);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    });
  }
});
