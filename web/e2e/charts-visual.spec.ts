import { expect, test } from "@playwright/test";

// Opt-in fixture-only review artifacts; all files live in ignored test-results/.
// CFB_CHART_VISUALS=1 npm run test:ui -- e2e/charts-visual.spec.ts --workers=1
const enabled = process.env.CFB_CHART_VISUALS === "1";
const charts = [
  { kind: "net-success", query: "chart=net-success&week=3", testId: "net-success-chart" },
  { kind: "efficiency", query: "chart=efficiency&fixture=slate&week=3&team=Alabama", testId: "scatter-chart" },
  { kind: "adjusted", query: "chart=adjusted&week=3&team=Alabama", testId: "scatter-chart" },
  { kind: "schedule", query: "chart=schedule&fixture=schedule&week=3", testId: "schedule-chart" },
  { kind: "trajectory", query: "chart=trajectory&team=Alabama", testId: "trajectory-chart" },
  { kind: "game-log", query: "chart=game-log&team=Alabama", testId: "game-log-chart" },
] as const;

test("capture all chart fixtures and desktop PNG exports in both themes", async ({ page }, testInfo) => {
  test.skip(!enabled, "Set CFB_CHART_VISUALS=1 to create the optional visual review artifacts.");
  test.setTimeout(180_000);
  for (const theme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: theme });
    for (const viewport of [{ width: 1280, height: 1000 }, { width: 390, height: 900 }]) {
      await page.setViewportSize(viewport);
      for (const chart of charts) {
        const name = `${chart.kind}-${theme}-${viewport.width}`;
        await page.goto(`/charts?${chart.query}`);
        await expect(page.getByTestId(chart.testId)).toBeVisible();
        await page.waitForLoadState("networkidle");
        await expect(page.locator("html")).toHaveClass(theme === "dark" ? /dark/ : /^(?!.*dark)/);
        if (chart.kind === "schedule") {
          // The large fixture includes both 15-team ends and an extra middle highlight.
          const teams = (await page.getByTestId("team-highlight").locator("option").allTextContents()).slice(2);
          await page.getByTestId("team-highlight").selectOption(teams[19]);
          await expect(page.getByTestId("schedule-chart").locator("g[data-team]")).toHaveCount(31);
        }
        await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: true });
        if (viewport.width === 1280) {
          const downloadEvent = page.waitForEvent("download");
          await page.getByTestId("chart-download").click();
          const download = await downloadEvent;
          await download.saveAs(testInfo.outputPath(`${chart.kind}-${theme}-export.png`));
          const raw = await page.getByTestId("chart-export").getAttribute("data-last-export");
          const report = JSON.parse(raw ?? "{}");
          expect(report.width).toBe(2000);
          expect(report.decoded).toBe(report.logos);
          expect(report.logos).toBeGreaterThan(0);
        }
        if (chart.kind === "trajectory") {
          // Keep the national capture above and also inspect a conference's endpoint logos.
          await page.getByTestId("conference-filter").selectOption("SEC");
          await expect(page.getByTestId("trajectory-endpoint").first()).toBeVisible();
          await page.screenshot({ path: testInfo.outputPath(`${name}-conference.png`), fullPage: true });
          // Stress the endpoint rail separately with the 40-team synthetic group.
          await page.goto("/charts?chart=trajectory&fixture=schedule");
          await expect(page.getByTestId("trajectory-chart")).toBeVisible();
          await page.getByTestId("conference-filter").selectOption("Fixture");
          await expect(page.getByTestId("trajectory-endpoint")).toHaveCount(40);
          await page.screenshot({ path: testInfo.outputPath(`${name}-dense-conference.png`), fullPage: true });
        }
      }
    }
  }
});
