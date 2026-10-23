import { expect, test } from "@playwright/test";
import { gotoHydrated } from "./helpers";

test.describe("mobile scatter inspection on the page", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

  for (const [width, height] of [[320, 568], [390, 844], [430, 932]]) {
    test(`the whole scatter fits the screen with readable labels and national geometry at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await page.goto("/stats?chart=efficiency&week=3");
      const chart = page.getByTestId("scatter-chart");
      await expect(chart).toBeVisible();
      await expect(page.getByTestId("scatter-scroll")).toHaveCount(0);
      await expect(page.getByText("Scroll chart horizontally")).toBeHidden();
      const svg = chart.locator("svg");
      // Portrait viewBox that follows the container width, so the scale is 1:1.
      await expect.poll(async () => {
        const [, , w, h] = (await svg.getAttribute("viewBox"))!.split(" ").map(Number);
        const box = (await svg.boundingBox())!;
        return Math.abs(w - box.width) <= 1 && h > w;
      }).toBe(true);
      await expect.poll(() => svg.evaluate((node) => {
        const text = [...node.querySelectorAll<SVGTextElement>("text[data-chart-label], [data-chart-label] text")];
        if (text.length === 0) return 0;
        return Math.min(...text.map((label) => {
          const matrix = label.getScreenCTM();
          if (!matrix) return 0;
          return parseFloat(getComputedStyle(label).fontSize) * Math.hypot(matrix.a, matrix.b);
        }));
      })).toBeGreaterThanOrEqual(11.99);
      // No horizontal scroll on the page or the chart, and every plotted team sits inside the viewport.
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      expect(await chart.evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);
      const marks = await page.locator("g[data-team] [data-mark]").evaluateAll((nodes) => nodes.map((node) => {
        const rect = node.getBoundingClientRect();
        return { left: rect.left, right: rect.right };
      }));
      expect(marks.length).toBeGreaterThan(5);
      for (const mark of marks) {
        expect(mark.left).toBeGreaterThanOrEqual(0);
        expect(mark.right).toBeLessThanOrEqual(width);
      }
      expect(await chart.getAttribute("data-x-domain")).toBeTruthy();
    });
  }

  test("touch detail lives outside horizontal scroll and empty tap clears only transient detail", async ({ page }) => {
    // The marks are in the server HTML; a tap before hydration selects nothing.
    await gotoHydrated(page, "/stats?chart=efficiency&week=3");
    const mark = page.locator('g[data-team="Alabama"]');
    // Mid-screen: the sticky chart bar and the bottom tab bar would otherwise cover marks near the edges.
    await mark.evaluate((node) => window.scrollBy(0, node.getBoundingClientRect().y - window.innerHeight / 2));
    const center = await mark.locator('[data-mark="dot"] circle').last().evaluate((node) => {
      const rect = node.getBoundingClientRect();
      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
    });
    await page.touchscreen.tap(center.x, center.y);
    const details = page.getByTestId("scatter-details");
    await expect(details).toContainText("Alabama");
    expect(await details.evaluate((node) => !!node.closest('[data-testid="scatter-scroll"]'))).toBe(false);
    // Tap selects locally on the chart without mutating the page URL highlight:
    await expect(page).not.toHaveURL(/team=Alabama/);
    // Tapping the explicit highlight button elevates the local selection to a persistent URL highlight:
    await details.getByRole("button", { name: "Highlight this team" }).click();
    await expect(page).toHaveURL(/team=Alabama/);
    // A touch must not leave the selection hook permanently in touch mode.
    await mark.focus();
    await mark.press("ArrowRight");
    const keyboardTeam = await page.evaluate(() => document.activeElement?.getAttribute("data-team"));
    await expect(details).toContainText(keyboardTeam!);
    const svg = page.getByTestId("scatter-chart").locator("svg");
    // The outer SVG margin contains no marks and clears transient detail while preserving URL highlight.
    await svg.dispatchEvent("pointerdown", { pointerId: 5, pointerType: "touch", clientX: 1, clientY: 1 });
    await svg.dispatchEvent("pointerup", { pointerId: 5, pointerType: "touch", clientX: 1, clientY: 1 });
    await expect(details).toHaveCount(0);
    await expect(page).toHaveURL(/team=Alabama/);
  });

  for (const [chart, week] of [["efficiency", 3], ["adjusted", 2], ["possession", 3]]) {
  test(`phones draw team dots on ${chart}; only the tapped and the highlighted team show logos`, async ({ page }) => {
    await gotoHydrated(page, `/stats?chart=${chart}&week=${week}&team=Michigan`);
    const teams = page.locator("g[data-team]");
    const total = await teams.count();
    expect(total).toBeGreaterThan(5);
    await expect(page.locator('g[data-team] [data-mark="dot"]')).toHaveCount(total - 1);
    await expect(page.locator('g[data-team="Michigan"] [data-mark="logo"]')).toHaveCount(1);
    await expect(page.locator('g[data-team="Michigan"] [data-mark="dot"]')).toHaveCount(0);
    expect(await page.locator('g[data-team] [data-mark="dot"] circle').last().evaluate((node) => node.getAttribute("r"))).toBe("4");
    // A tap on a dot (tap target is ~24px) selects the team and shows its logo on top.
    const target = (await page.locator('g[data-team] [data-mark="dot"]').first().evaluate((node) => node.closest("g[data-team]")!.getAttribute("data-team")))!;
    // Bring the dot to mid-screen: the fixed header and bottom tab bar would otherwise cover marks near the plot edges.
    await page.locator(`g[data-team="${target}"]`).evaluate((node) => window.scrollBy(0, node.getBoundingClientRect().y - window.innerHeight / 2));
    const dot = await page.locator(`g[data-team="${target}"] [data-mark="dot"] circle`).last().evaluate((node) => {
      const rect = node.getBoundingClientRect();
      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
    });
    await page.touchscreen.tap(dot.x + 3, dot.y + 3);
    await expect(page.getByTestId("scatter-details")).toContainText(target);
    await expect(page.locator('[data-testid="hover-mark"] [data-mark="logo"]')).toHaveCount(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
  }

  test("native scrolling and pointer cancellation cannot select a team", async ({ page }) => {
    await page.goto("/stats?chart=efficiency&week=3");
    const svg = page.getByTestId("scatter-chart").locator("svg");
    const mark = page.locator('g[data-team="Alabama"]');
    const point = await mark.locator('[data-mark="dot"]').evaluate((node) => {
      const rect = node.getBoundingClientRect();
      return { clientX: rect.x + rect.width / 2, clientY: rect.y + rect.height / 2 };
    });
    for (const cancellation of ["scroll", "pointercancel"]) {
      await svg.dispatchEvent("pointerdown", { ...point, pointerId: 4, pointerType: "touch" });
      if (cancellation === "scroll") await page.evaluate(() => document.dispatchEvent(new Event("scroll")));
      else await svg.dispatchEvent("pointercancel", { ...point, pointerId: 4, pointerType: "touch" });
      await svg.dispatchEvent("pointerup", { ...point, pointerId: 4, pointerType: "touch" });
      await mark.dispatchEvent("click", { detail: 1 });
      await expect(page).not.toHaveURL(/team=/);
      await expect(page.getByTestId("scatter-details")).toHaveCount(0);
    }
  });

  test("team finder exposes keyboard active options and 44px touch controls", async ({ page }) => {
    await page.goto("/stats?chart=efficiency&week=3");
    const search = page.getByTestId("team-search");
    await search.fill("a");
    const first = await search.getAttribute("aria-activedescendant");
    await search.press("ArrowDown");
    const next = await search.getAttribute("aria-activedescendant");
    expect(next).not.toBe(first);
    const option = page.locator(`[id="${next}"]`);
    await expect(option).toHaveAttribute("aria-selected", "true");
    const selectedTeam = await option.locator("span").first().innerText();
    expect((await option.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await search.press("Enter");
    await expect(search).toHaveValue(selectedTeam);
    await search.fill("Wyoming");
    await search.press("Enter");
    await expect(search).toHaveValue("Wyoming");
    await expect(page).toHaveURL(/team=Wyoming/);
    await search.fill("NoSuchTeam");
    await search.press("Enter");
    await expect(page).toHaveURL(/team=Wyoming/);
    await search.press("ArrowDown");
    await search.press("Escape");
    await expect(search).toBeFocused();
    await expect(search).toHaveAttribute("aria-expanded", "false");
    const clear = page.getByRole("button", { name: "Clear team highlight" });
    expect((await clear.boundingBox())!.width).toBeGreaterThanOrEqual(44);
    expect((await clear.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  });

  for (const [chart, week, width] of ["efficiency", "adjusted", "possession"].flatMap((c) => [320, 390, 430].map((w) => [c, c === "adjusted" ? 2 : 3, w] as const))) {
    test(`${chart} scatter axis labels and titles stay inside bounds and do not collide at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await page.goto(`/stats?chart=${chart}&week=${week}`);
      const svg = page.getByTestId("scatter-chart").locator("svg");
      await expect(svg).toBeVisible();

      const evaluation = await svg.evaluate((node) => {
        const svgRect = node.getBoundingClientRect();
        const xTitle = node.querySelector<SVGTextElement>('text[data-axis="x-title"]');
        const yTitle = node.querySelector<SVGTextElement>('text[data-axis="y-title"]');
        const xTicks = [...node.querySelectorAll<SVGTextElement>('text[data-axis="x-tick"]')];
        const yTicks = [...node.querySelectorAll<SVGTextElement>('text[data-axis="y-tick"]')];
        const allLabels = [...node.querySelectorAll<SVGTextElement>('text[data-chart-label="true"]')];

        const intersects = (r1: DOMRect, r2: DOMRect) =>
          !(r2.left >= r1.right || r2.right <= r1.left || r2.top >= r1.bottom || r2.bottom <= r1.top);

        let outOfBounds = 0;
        for (const label of allLabels) {
          const r = label.getBoundingClientRect();
          // Allow 1px tolerance for subpixel antialiasing
          if (r.left < svgRect.left - 1 || r.right > svgRect.right + 1 || r.top < svgRect.top - 1 || r.bottom > svgRect.bottom + 1) {
            outOfBounds++;
          }
        }

        let xCollisions = 0;
        if (xTitle) {
          const titleRect = xTitle.getBoundingClientRect();
          for (const tick of xTicks) {
            if (intersects(titleRect, tick.getBoundingClientRect())) xCollisions++;
          }
        }

        let yCollisions = 0;
        if (yTitle) {
          const titleRect = yTitle.getBoundingClientRect();
          for (const tick of yTicks) {
            if (intersects(titleRect, tick.getBoundingClientRect())) yCollisions++;
          }
        }

        return {
          xCollisions,
          yCollisions,
          outOfBounds,
          xTicksFound: xTicks.length,
          yTicksFound: yTicks.length,
          allLabelsFound: allLabels.length,
        };
      });

      expect(evaluation.xTicksFound).toBeGreaterThanOrEqual(3);
      expect(evaluation.yTicksFound).toBeGreaterThanOrEqual(4);
      expect(evaluation.allLabelsFound).toBeGreaterThanOrEqual(10);
      expect(evaluation.outOfBounds).toBe(0);
      expect(evaluation.xCollisions).toBe(0);
      expect(evaluation.yCollisions).toBe(0);
    });
  }

  test("landscape phone with touch displays details panel instead of floating hover tooltip", async ({ page }) => {
    // 844x390 landscape mobile viewport
    await page.setViewportSize({ width: 844, height: 390 });
    await page.goto("/stats?chart=efficiency&week=3");
    const mark = page.locator('g[data-team="Alabama"]');
    await mark.scrollIntoViewIfNeeded();
    const center = await mark.locator('[data-mark="logo"]').evaluate((node) => {
      const rect = node.getBoundingClientRect();
      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
    });
    await page.touchscreen.tap(center.x, center.y);
    const details = page.getByTestId("scatter-details");
    await expect(details).toBeVisible();
    await expect(details).toContainText("Alabama");
    await expect(page.getByTestId("chart-tooltip")).not.toBeVisible();
  });

  test("landscape tablet with touch displays details panel instead of floating hover tooltip", async ({ browser }) => {
    // 1024x768 landscape tablet with hasTouch: true (height > 500px, coarse pointer)
    const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, hasTouch: true });
    const page = await context.newPage();
    await page.goto("/stats?chart=efficiency&week=3");
    const mark = page.locator('g[data-team="Alabama"]');
    await mark.scrollIntoViewIfNeeded();
    const center = await mark.locator('[data-mark="logo"]').evaluate((node) => {
      const rect = node.getBoundingClientRect();
      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
    });
    await page.touchscreen.tap(center.x, center.y);
    const details = page.getByTestId("scatter-details");
    await expect(details).toBeVisible();
    await expect(details).toContainText("Alabama");
    await expect(page.getByTestId("chart-tooltip")).not.toBeVisible();
    await context.close();
  });
});
