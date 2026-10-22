import { expect, test } from "@playwright/test";

test.describe("mobile scatter inspection on the page", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

  for (const width of [320, 390, 430]) {
    test(`essential scatter labels stay readable and geometry stays national at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/stats?chart=efficiency&week=3");
      const chart = page.getByTestId("scatter-chart");
      await expect(chart).toBeVisible();
      const svg = chart.locator("svg");
      await expect(svg).toHaveAttribute("viewBox", "0 0 1000 640");
      await expect.poll(() => svg.evaluate((node) => {
        const text = [...node.querySelectorAll<SVGTextElement>("text[data-chart-label], [data-chart-label] text")];
        if (text.length === 0) return 0;
        return Math.min(...text.map((label) => {
          const matrix = label.getScreenCTM();
          if (!matrix) return 0;
          return parseFloat(getComputedStyle(label).fontSize) * Math.hypot(matrix.a, matrix.b);
        }));
      })).toBeGreaterThanOrEqual(11.99);
      expect(await page.getByTestId("scatter-chart").evaluate((node) => node.getBoundingClientRect().width)).toBeGreaterThanOrEqual(760);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
  }

  test("touch detail lives outside horizontal scroll and empty tap clears only transient detail", async ({ page }) => {
    await page.goto("/stats?chart=efficiency&week=3");
    const mark = page.locator('g[data-team="Alabama"]');
    await mark.scrollIntoViewIfNeeded();
    const center = await mark.locator('[data-mark="logo"]').evaluate((node) => {
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

  test("native scrolling and pointer cancellation cannot select a team", async ({ page }) => {
    await page.goto("/stats?chart=efficiency&week=3");
    const svg = page.getByTestId("scatter-chart").locator("svg");
    const mark = page.locator('g[data-team="Alabama"]');
    const point = await mark.locator('[data-mark="logo"]').evaluate((node) => {
      const rect = node.getBoundingClientRect();
      return { clientX: rect.x + rect.width / 2, clientY: rect.y + rect.height / 2 };
    });
    for (const cancellation of ["scroll", "pointercancel"]) {
      await svg.dispatchEvent("pointerdown", { ...point, pointerId: 4, pointerType: "touch" });
      if (cancellation === "scroll") await page.getByTestId("scatter-scroll").dispatchEvent("scroll");
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

  for (const width of [320, 390, 430]) {
    test(`scatter axis labels and titles stay inside bounds and do not collide at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/stats?chart=efficiency&week=3");
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

      expect(evaluation.xTicksFound).toBeGreaterThanOrEqual(4);
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
