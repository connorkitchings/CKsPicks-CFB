import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 568 }]) {
  test.describe(`phone model page at ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport, hasTouch: true });

    test("the first KPI card sits near the top, with a summary and no duplicate headings", async ({ page }) => {
      await gotoHydrated(page, "/model");
      const spread = page.getByRole("region", { name: "Forecast accuracy summary", exact: true }).locator("[data-card]").filter({ hasText: "Spread" });
      await expect(spread).toBeVisible();
      expect((await spread.boundingBox())!.y).toBeLessThan(330);
      await expect(page.getByTestId("model-summary")).toHaveText(/^2026 · V5 · \d+ graded weeks?$/);
      // The hand-rolled eyebrow is hidden; the summary line carries "2026 · V5".
      await expect(page.getByText("2026 · V5", { exact: true }).filter({ visible: true })).toHaveCount(0);
      await expect(page.getByRole("region", { name: "Forecast accuracy summary", exact: true })).toBeVisible();
      await expect(page.locator("details[open]")).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test("the Record / How it works tabs stay directly under the app bar after an 800px scroll", async ({ page }) => {
      await gotoHydrated(page, "/model");
      const tabs = page.getByRole("navigation", { name: "Model sections" });
      await page.mouse.wheel(0, 800);
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
      const bar = (await page.getByTestId("app-bar").boundingBox())!;
      await expect.poll(async () => Math.abs((await tabs.boundingBox())!.y - (bar.y + bar.height))).toBeLessThanOrEqual(1);
    });

    test("there is no target selector and every week card shows both targets", async ({ page }) => {
      await gotoHydrated(page, "/model");
      await expect(page.getByRole("group", { name: "Pick target" })).toHaveCount(0);
      await expect(page.getByRole("button", { name: "All Picks" })).toHaveCount(0);
      const weekly = page.getByRole("region", { name: "Weekly accuracy breakdown" });
      await expect(weekly.getByText("Spread", { exact: true }).first()).toBeVisible();
      await expect(weekly.getByText("Total", { exact: true }).first()).toBeVisible();
      await expect(weekly.getByText(/Average miss/)).toHaveCount(0);
    });


    test("the trend, comparison cards and week cards fit without horizontal scroll", async ({ page }) => {
      await gotoHydrated(page, "/model");
      await expect(page.getByTestId("record-trend-chart")).toBeVisible();
      await expect(page.getByTestId("market-spread")).toBeVisible();
      await expect(page.getByText("In progress", { exact: true }).filter({ visible: true })).toHaveCount(1);
      await page.getByTestId("table-toggle").click();
      await expect(page.getByTestId("chart-table")).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test("the record trend draws break-even and shares one y-axis across panels", async ({ page }) => {
      await gotoHydrated(page, "/model");
      const spread = page.getByTestId("record-trend-spread");
      const total = page.getByTestId("record-trend-total");
      await expect(spread.locator("[data-break-even]")).toHaveCount(1);
      await expect(total.locator("[data-break-even]")).toHaveCount(1);
      const yTicks = (svg: typeof spread) => svg.locator("text").filter({ hasText: /^\d+%$/ }).allTextContents();
      const [a, b] = [await yTicks(spread), await yTicks(total)];
      expect(a[0]).toBe(b[0]);
      expect(a.at(-1)).toBe(b.at(-1));
    });

    test("the record trend labels render at 12px or more and the break-even label sits at the left", async ({ page }) => {
      await gotoHydrated(page, "/model");
      for (const id of ["record-trend-spread", "record-trend-total"]) {
        const svg = page.getByTestId(id);
        await expect.poll(async () => {
          const [, , w] = (await svg.getAttribute("viewBox"))!.split(" ").map(Number);
          return Math.abs(w - (await svg.boundingBox())!.width) <= 1;
        }).toBe(true);
        await expect.poll(() => svg.evaluate((node) => Math.min(...[...node.querySelectorAll<SVGTextElement>("text")].map((label) => {
          const matrix = label.getScreenCTM();
          return matrix ? parseFloat(getComputedStyle(label).fontSize) * Math.hypot(matrix.a, matrix.b) : 0;
        })))).toBeGreaterThanOrEqual(11.99);
        const line = (await svg.locator("[data-break-even]").boundingBox())!;
        const box = (await svg.locator("text", { hasText: /^52\.4%$/ }).boundingBox())!;
        expect(box.x).toBeLessThan(line.x + line.width / 2);
        expect(box.y + box.height).toBeLessThanOrEqual(line.y + 2);
      }
    });

    test("the error scatter labels render at 12px or more and stay inside the svg", async ({ page }) => {
      await gotoHydrated(page, "/model");
      for (const target of ["spread", "total"]) {
        await page.getByTestId(`error-target-${target}`).click();
        const svg = page.getByTestId("error-scatter");
        await expect(svg).toHaveAttribute("aria-label", new RegExp(`^${target === "spread" ? "Spread" : "Totals"} absolute error`));
        // The phone layout swaps in after hydration; wait for the measured width to settle before probing.
        await expect.poll(() => svg.evaluate((node) => node.isConnected && node.getBoundingClientRect().width > 0)).toBe(true);
        await svg.scrollIntoViewIfNeeded();
        await expect.poll(async () => {
          const [, , w] = (await svg.getAttribute("viewBox"))!.split(" ").map(Number);
          return Math.abs(w - (await svg.boundingBox())!.width) <= 1;
        }).toBe(true);
        await expect.poll(() => svg.evaluate((node) => Math.min(...[...node.querySelectorAll<SVGTextElement>("text")].map((label) => {
          const matrix = label.getScreenCTM();
          return matrix ? parseFloat(getComputedStyle(label).fontSize) * Math.hypot(matrix.a, matrix.b) : 0;
        })))).toBeGreaterThanOrEqual(11.99);
        const outside = await svg.evaluate((node) => {
          const frame = node.getBoundingClientRect();
          return [...node.querySelectorAll<SVGTextElement>("text")].map((label) => ({ label, box: label.getBoundingClientRect() }))
            .filter(({ box }) => box.left < frame.left - 0.5 || box.right > frame.right + 0.5 || box.top < frame.top - 0.5 || box.bottom > frame.bottom + 0.5)
            .map(({ label }) => label.textContent);
        });
        expect(outside).toEqual([]);
      }
    });

    test("the explainers live in one collapsed disclosure", async ({ page }) => {
      await gotoHydrated(page, "/model");
      const explainer = page.getByText(/Win rate excludes pushes/).filter({ visible: true });
      await expect(explainer).toHaveCount(0);
      await page.getByText("About this record", { exact: true }).click();
      await expect(explainer).toHaveCount(1);
    });
  });
}
