import fs from "node:fs";
import { expect, test, type Page } from "@playwright/test";

// Fixture: 17-team roster (Wyoming has no games), net-success weeks 0-3, efficiency and
// adjusted "Through Week" 2-3. See src/test/fixtures/charts.ts.
const PLOTTED = 16;
const SEC_TEAMS = 4;

function pngSize(path: string): { width: number; height: number } {
  const bytes = fs.readFileSync(path);
  expect(bytes.subarray(1, 4).toString("ascii")).toBe("PNG");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

async function exportPng(page: Page): Promise<{ file: string; report: { logos: number; decoded: number }; capture: { teams: string[]; games: string[]; text: string } }> {
  // The static card exists only during capture. Observe it from mount to download,
  // so transient keyboard decorations cannot silently leak into the saved PNG.
  await page.evaluate(() => {
    const root = document.querySelector('[data-testid="chart-export"]')!;
    const probe = { seen: false, rings: 0, focusStops: 0, teams: [] as string[], games: [] as string[], text: "" };
    const observer = new MutationObserver(() => {
      const svg = root.querySelector("div[aria-hidden] svg");
      if (!svg) return;
      probe.seen = true;
      probe.teams = [...svg.querySelectorAll("g[data-team]")].map((node) => node.getAttribute("data-team")!);
      probe.games = [...svg.querySelectorAll("g[data-game]")].map((node) => node.getAttribute("data-game")!);
      probe.text = root.querySelector("[data-testid=export-card]")?.textContent ?? "";
      probe.rings = Math.max(probe.rings, svg.querySelectorAll(".focus-ring").length);
      probe.focusStops = Math.max(probe.focusStops, svg.querySelectorAll("[tabindex]").length);
    });
    observer.observe(root, { childList: true, subtree: true });
    (window as typeof window & { chartCaptureProbe?: () => typeof probe }).chartCaptureProbe = () => {
      observer.disconnect();
      return probe;
    };
  });
  const download = page.waitForEvent("download");
  await page.getByTestId("chart-download").click();
  const file = await (await download).path();
  const capture = await page.evaluate(() => {
    const state = window as typeof window & { chartCaptureProbe?: () => { seen: boolean; rings: number; focusStops: number; teams: string[]; games: string[]; text: string } };
    const result = state.chartCaptureProbe!();
    delete state.chartCaptureProbe;
    return result;
  });
  expect(capture).toMatchObject({ seen: true, rings: 0, focusStops: 0 });
  const raw = await page.getByTestId("chart-export").getAttribute("data-last-export");
  return { file, report: JSON.parse(raw ?? "{}"), capture };
}

test.describe("team charts", () => {
  test("net success bars render one bar per game with logos and score labels", async ({ page }) => {
    await page.goto("/charts");
    await expect(page.getByRole("heading", { name: "Team charts" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "Net success rate" })).toBeVisible();
    await expect(page.getByTestId("chart-description")).toHaveText("Each game's winner minus loser success rate, in percentage points.");
    await expect(page.getByTestId("chart-subtitle")).toHaveClass(/sr-only/);
    await expect(page.getByTestId("chart-credit")).toHaveText("Concept by Parker Fleming: “Did We Really Get Beat That Bad?”");
    const chart = page.getByTestId("net-success-chart");
    await expect(chart).toBeVisible();
    // Latest week (3) has 8 games: 8 bars, each with a winner and a loser mark.
    await expect(chart.locator("g[data-game]")).toHaveCount(8);
    await expect(chart.locator("g[data-game]").first().locator("g[data-mark='logo']")).toHaveCount(2);
    await expect(page.locator("main").getByText(/\b[A-Z]{2,6} \d+-\d+\b/).first()).toBeVisible();
  });

  test("hidden charts are absent from the picker and their URLs fall back to net success", async ({ page }) => {
    // Hidden by `ready: false` in src/lib/chart-config.ts.
    for (const hidden of ["schedule", "trajectory", "rating-trajectory"]) {
      await page.goto(`/charts?chart=${hidden}&team=Alabama`);
      await expect(page.getByRole("heading", { level: 2, name: "Net success rate" })).toBeVisible();
      await expect(page.getByTestId("net-success-chart")).toBeVisible();
      await expect(page.getByTestId("chart-picker").getByRole("link")).toHaveText([
        "Net success rate", "Efficiency vs explosiveness", "Adjusted PPA/play", "Possession efficiency", "Game log",
      ]);
    }
  });

  test("scatter shows 'Through Week N' and a week switch changes the window", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    await expect(page.getByText("Offense · 2026 · FBS vs FBS · Through Week 3").first()).toBeVisible();
    await expect(page.locator("#week-select")).toHaveValue("3");
    await expect(page.getByRole("option", { name: "Through Week 2" })).toHaveCount(1);
    await page.locator("#week-select").selectOption("2");
    await expect(page).toHaveURL(/week=2/);
    await expect(page.getByTestId("chart-subtitle")).toContainText("Through Week 2");
    await expect(page.getByText("Success Rate").first()).toBeVisible();
    // A `charts_v2` release defaults the y axis to the 20+ yard play rate.
    await expect(page.getByText("20+ Yard Play Rate", { exact: true })).toBeVisible();
    await expect(page.getByTestId("average-lines")).toBeVisible();
  });

  test("switching tabs from a net-success Week 0 or 1 URL coerces the week", async ({ page }) => {
    for (const requested of [0, 1]) {
      await page.goto(`/charts?chart=net-success&week=${requested}`);
      await expect(page.getByText(`Week ${requested} · 2026 · FBS vs FBS`).first()).toBeVisible();
      await page.getByRole("link", { name: "Efficiency vs explosiveness", exact: true }).click();
      await expect(page).toHaveURL(/chart=efficiency/);
      await expect(page).toHaveURL(/week=2/);
      await expect(page.locator("#week-select")).toHaveValue("2");
      await page.getByRole("link", { name: "Adjusted PPA/play" }).click();
      await expect(page).toHaveURL(/chart=adjusted/);
      await expect(page).toHaveURL(/week=2/);
      await expect(page.getByTestId("corner-labels")).toBeVisible();
    }
  });

  test("adjusted chart has dashed averages and corner labels but no diagonals or in-chart note", async ({ page }) => {
    await page.goto("/charts?chart=adjusted&week=3");
    await expect(page.getByText("Better offense / Better defense")).toBeVisible();
    await expect(page.getByText("Lower offense / Higher defense allowed")).toBeVisible();
    await expect(page.getByTestId("average-lines")).toBeVisible();
    await expect(page.locator("[data-iso-net]")).toHaveCount(0);
    await expect(page.getByTestId("scatter-chart").getByText(/^Relative to/)).toHaveCount(0);
    await expect(page.getByText(/corner labels are relative to them/)).toBeVisible();
  });

  test("conference filtering removes excluded points and preserves national geometry", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    const marks = page.locator("g[data-team]");
    await expect(marks).toHaveCount(PLOTTED);
    const alabama = page.locator("g[data-team='Alabama'] image").first();
    const position = await alabama.evaluate((node) => [node.getAttribute("x"), node.getAttribute("y")]);
    const averages = await page.getByTestId("average-lines").innerHTML();
    const domains = await page.getByTestId("scatter-chart").evaluate((node) => [node.getAttribute("data-x-domain"), node.getAttribute("data-y-domain")]);
    await page.getByTestId("conference-filter").selectOption("SEC");
    await expect(marks).toHaveCount(SEC_TEAMS);
    await expect(page.locator("g[data-team='Michigan']")).toHaveCount(0);
    expect(await alabama.evaluate((node) => [node.getAttribute("x"), node.getAttribute("y")])).toEqual(position);
    expect(await page.getByTestId("average-lines").innerHTML()).toEqual(averages);
    expect(await page.getByTestId("scatter-chart").evaluate((node) => [node.getAttribute("data-x-domain"), node.getAttribute("data-y-domain")])).toEqual(domains);
    await page.getByTestId("conference-filter").selectOption("p4");
    await expect(marks).toHaveCount(13);
  });

  test("net-success group filtering includes a game when either team qualifies", async ({ page }) => {
    await page.goto("/charts?chart=net-success&week=3");
    await expect(page.getByTestId("team-search")).toHaveCount(0);
    await page.getByTestId("conference-filter").selectOption("SEC");
    // Week 3 has one SEC matchup and two cross-conference games.
    const bars = page.locator("g[data-game]");
    await expect(bars).toHaveCount(3);
    for (const label of await bars.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("aria-label")!))) {
      expect(label).toMatch(/Alabama|Georgia|Texas|LSU/);
    }
  });

  test("highlight persists independently of tooltips and toggles by dropdown, click, Enter and Space", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    const michigan = page.locator("g[data-team='Michigan']");
    const boise = page.locator("g[data-team='Boise State']");
    const select = page.getByTestId("team-highlight");
    await page.getByTestId("team-search").fill("Michigan");
    await select.selectOption("Michigan");
    await expect(michigan).toHaveAttribute("aria-pressed", "true");
    await boise.hover();
    await expect(page.getByTestId("chart-tooltip")).toContainText("Boise State");
    await expect(michigan).toHaveAttribute("aria-pressed", "true");
    await boise.focus();
    await expect(page.getByTestId("chart-tooltip")).toContainText("Boise State");
    await expect(michigan).toHaveAttribute("aria-pressed", "true");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("chart-tooltip")).toHaveCount(0);
    await expect(page.getByTestId("highlight-status")).toContainText("Michigan");
    await michigan.click();
    await expect(page.getByTestId("highlight-status")).toHaveCount(0);
    await michigan.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("highlight-status")).toContainText("Michigan");
    await page.keyboard.press("Space");
    await expect(page.getByTestId("highlight-status")).toHaveCount(0);
    await select.selectOption("Michigan");
    await expect(michigan).toHaveAttribute("aria-pressed", "true");
    await select.selectOption("Michigan");
    await expect(michigan).toHaveAttribute("aria-pressed", "false");
    await select.selectOption("Michigan");
    await select.selectOption("");
    await expect(michigan).toHaveAttribute("aria-pressed", "false");
    await select.selectOption("Michigan");
    await page.getByTestId("conference-filter").selectOption("SEC");
    await expect(page.getByTestId("highlight-status")).toHaveCount(0);
    await expect(michigan).toHaveCount(0);
  });

  test("highlight survives week navigation and reports an unavailable observation", async ({ page }) => {
    await page.goto("/charts?chart=adjusted&week=2");
    await page.getByTestId("team-highlight").selectOption("Notre Dame");
    await expect(page.locator("g[data-team='Notre Dame']")).toHaveAttribute("aria-pressed", "true");
    await page.locator("#week-select").selectOption("3");
    await expect(page.getByTestId("highlight-status")).toContainText("Notre Dame");
    await expect(page.locator("g[data-team='Notre Dame']")).toHaveCount(0);
    await expect(page.getByTestId("highlight-status")).toContainText("no available observation Through Week 3");
    await page.getByRole("link", { name: "Previous through week" }).click();
    await expect(page.locator("g[data-team='Notre Dame']")).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("link", { name: "Next through week" }).click();
    await expect(page.getByTestId("highlight-status")).toContainText("no available observation Through Week 3");
  });

  test("markers are keyboard reachable; arrows move focus and a tooltip appears", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    const first = page.locator("g[data-team]").first();
    const tooltip = page.getByTestId("chart-tooltip");
    // Focus handlers attach on hydration; retry until the tooltip responds.
    await expect(async () => {
      await first.blur();
      await first.focus();
      await expect(tooltip).toBeVisible({ timeout: 500 });
    }).toPass();
    const firstTeam = await first.getAttribute("data-team");
    await expect(tooltip).toContainText(firstTeam ?? "");
    await page.keyboard.press("ArrowRight");
    const focused = await page.evaluate(() => document.activeElement?.getAttribute("data-team"));
    expect(focused).toBeTruthy();
    expect(focused).not.toBe(firstTeam);
    await expect(tooltip).toContainText(focused ?? "");
    await expect(page.locator("g[data-team]:focus .focus-ring")).toHaveCSS("opacity", "1");
    await expect(first).toHaveAttribute("role", "button");
    await expect(first).toHaveAttribute("aria-label", /success rate .*20\+ yard rate .* plays/);
    await page.keyboard.press("Escape");
    await expect(tooltip).toHaveCount(0);
  });

  test("net-success bars retain a visible keyboard focus ring", async ({ page }) => {
    await page.goto("/charts?chart=net-success&week=3");
    const first = page.locator("g[data-game]").first();
    await expect(async () => {
      await first.blur();
      await first.focus();
      await expect(page.getByTestId("chart-tooltip")).toBeVisible({ timeout: 500 });
    }).toPass();
    await page.keyboard.press("ArrowRight");
    await expect(first).not.toBeFocused();
    await expect(page.locator("g[data-game]:focus .focus-ring")).toHaveCSS("opacity", "1");
    await expect(page.getByTestId("chart-tooltip")).toBeVisible();
  });

  test("teams without data are listed instead of plotted", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    await expect(page.getByTestId("unavailable-teams")).toContainText("Wyoming");
    await expect(page.locator("g[data-team='Wyoming']")).toHaveCount(0);
    await page.goto("/charts?chart=adjusted&week=3");
    // Window as_of_week 4 has no Notre Dame defense row: one role is not a point.
    await expect(page.getByTestId("unavailable-teams")).toContainText("Notre Dame");
    await expect(page.locator("g[data-team='Notre Dame']")).toHaveCount(0);
  });

  test("a release without chart tables shows the arrival notice, errors show unavailable", async ({ page }) => {
    await page.goto("/charts?fixture=unsupported");
    await expect(page.getByTestId("charts-notice")).toHaveText("Charts arrive with the next weekly release.");
    await expect(page.getByTestId("net-success-chart")).toHaveCount(0);
    await page.goto("/charts?fixture=error");
    await expect(page.getByTestId("charts-notice")).toHaveText("Charts are temporarily unavailable.");
    // A failing adjusted window shows the same card instead of the route error page.
    await page.goto("/charts?chart=adjusted&week=3&fixture=adjusted-error");
    await expect(page.getByTestId("charts-notice")).toHaveText("Charts are temporarily unavailable.");
  });

  test("explosiveness toggle appears only for a release that serves yardage", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    await expect(page.getByTestId("efficiency-metric-switcher")).toBeVisible();
    await expect(page.getByText("20+ Yard Play Rate", { exact: true })).toBeVisible();
    await page.goto("/charts?chart=efficiency&week=3&fixture=v1");
    await expect(page.getByTestId("scatter-chart")).toBeVisible();
    await expect(page.getByTestId("efficiency-metric-switcher")).toHaveCount(0);
    await expect(page.getByText("PPA/play", { exact: true }).first()).toBeVisible();
    await expect(page.locator("g[data-team]")).toHaveCount(PLOTTED);
  });

  test("charts on every tab load logos without a broken image", async ({ page }) => {
    const failed: string[] = [];
    page.on("response", (response) => {
      if (response.url().includes("/logos/") && !response.ok()) failed.push(`${response.status()} ${response.url()}`);
    });
    for (const url of ["/charts?chart=net-success&week=2", "/charts?chart=efficiency&week=3", "/charts?chart=adjusted&week=3"]) {
      await page.goto(url);
      await page.waitForLoadState("networkidle");
      const broken = await page.evaluate(() => [...document.images].filter((i) => i.complete && i.naturalWidth === 0).length);
      expect(broken, url).toBe(0);
      const svgLogos = await page.locator("svg image").count();
      expect(svgLogos, url).toBeGreaterThan(0);
    }
    expect(failed).toEqual([]);
  });

  test("mobile layout: bars become horizontal rows and nothing scrolls the page sideways", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto("/charts?chart=net-success&week=3");
    await expect(page.getByTestId("net-success-chart")).toHaveAttribute("data-orientation", "horizontal");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Charts" })).toBeVisible();
  });

  test("nav shows Charts and the nav width matches the chart page", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/charts");
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await expect(nav.getByRole("link", { name: "Charts" })).toHaveAttribute("aria-current", "page");
    // Styles may still be compiling on the first request; poll until the layout settles.
    await expect
      .poll(async () => {
        const navBox = await nav.locator("> div").boundingBox();
        const mainBox = await page.locator("main", { has: page.getByRole("heading", { name: "Team charts" }) }).boundingBox();
        return Math.abs((navBox?.width ?? 0) - (mainBox?.width ?? 0));
      })
      .toBeLessThanOrEqual(2);
  });

  test("filtered export contains the chart population, group, metric and persistent highlight", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    await page.getByTestId("conference-filter").selectOption("SEC");
    await page.getByTestId("team-highlight").selectOption("Alabama");
    const teams = await page.locator("g[data-team]").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-team")!).sort());
    const { file, capture } = await exportPng(page);
    expect(capture.teams.sort()).toEqual(teams);
    expect(capture.text).toContain("Through Week 3");
    expect(capture.text).toContain("SEC");
    expect(capture.text).toContain("20+ Yard Rate");
    expect(capture.text).toContain("Highlight: Alabama");
    const labelBox = await page.getByTestId("highlight-label").boundingBox();
    const axisBox = await page.getByTestId("scatter-chart").locator("svg > text").first().boundingBox();
    expect(labelBox!.y + labelBox!.height).toBeLessThan(axisBox!.y);
    fs.mkdirSync("test-results/chart-visuals", { recursive: true });
    fs.copyFileSync(file, "test-results/chart-visuals/filtered-scatter-export.png");
    await page.screenshot({ path: "test-results/chart-visuals/filtered-scatter-desktop.png", fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: "test-results/chart-visuals/filtered-scatter-mobile.png", fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
  });

  test("net-success export includes exactly the selected group's games", async ({ page }) => {
    await page.goto("/charts?chart=net-success&week=3");
    await page.getByTestId("conference-filter").selectOption("SEC");
    const games = await page.locator("g[data-game]").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-game")!).sort());
    const { capture } = await exportPng(page);
    expect(capture.games.sort()).toEqual(games);
    expect(capture.text).toContain("Week 3");
    expect(capture.text).toContain("SEC");
  });

  test("dense national scatter stays responsive and exports readable labels", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto("/charts?chart=efficiency&week=2&fixture=slate");
    await expect(page.locator("g[data-team]")).toHaveCount(138);
    fs.mkdirSync("test-results/chart-visuals", { recursive: true });
    await page.screenshot({ path: "test-results/chart-visuals/dense-national-desktop.png", fullPage: true });
    const { file } = await exportPng(page);
    fs.copyFileSync(file, "test-results/chart-visuals/dense-national-export.png");
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: "test-results/chart-visuals/dense-national-mobile.png", fullPage: true });
    const scroll = page.getByTestId("scatter-scroll");
    await expect(scroll).toHaveAttribute("tabindex", "0");
    expect(await scroll.evaluate((node) => node.scrollWidth > node.clientWidth)).toBe(true);
    await scroll.focus();
    await page.keyboard.press("ArrowRight");
    await expect.poll(() => scroll.evaluate((node) => node.scrollLeft)).toBeGreaterThan(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
  });

  test("touch activation selects a team while controls remain within the mobile viewport", async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true });
    const page = await context.newPage();
    await page.goto("/charts?chart=efficiency&week=3");
    const mark = page.locator("g[data-team='Boise State']");
    await mark.tap();
    await expect(mark).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("chart-tooltip")).toContainText("Boise State");
    await mark.tap();
    await expect(mark).toHaveAttribute("aria-pressed", "false");
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
    await context.close();
  });

  test("PNG export of a scatter is 2000x1125 with every logo decoded", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    await page.waitForLoadState("networkidle");
    const { file, report } = await exportPng(page);
    expect(pngSize(file)).toEqual({ width: 2000, height: 1125 });
    expect(report.logos).toBeGreaterThan(0);
    expect(report.decoded).toBe(report.logos);
  });

  test("export icon buttons are named, show a tooltip on keyboard focus and announce the result", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("button", { name: /table/i })).toHaveCount(0);
    const download = page.getByRole("button", { name: "Download PNG", exact: true });
    await expect(download).toHaveText("");
    const tooltip = page.getByTestId("chart-download-tooltip");
    await expect(tooltip).toHaveCSS("opacity", "0");
    await download.focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab");
    await expect(tooltip).toHaveText("Download PNG");
    await expect(tooltip).toHaveCSS("opacity", "1");
    const saved = page.waitForEvent("download");
    await page.keyboard.press("Enter");
    await saved;
    await expect(page.getByTestId("chart-export").getByRole("status")).toHaveText("Image saved");
    await expect(tooltip).toHaveText("Image saved");
    await expect(tooltip).toHaveText("Download PNG", { timeout: 5_000 });
  });

  test("PNG export of a full Week 0 slate is as wide as 140 + 30 per game and keeps its logos", async ({ page }) => {
    await page.goto("/charts?chart=net-success&week=0&fixture=slate");
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("net-success-chart").locator("g[data-game]")).toHaveCount(69);
    const { file, report } = await exportPng(page);
    expect(pngSize(file)).toEqual({ width: 140 + 30 * 69, height: 1125 });
    expect(report.decoded).toBe(report.logos);
    expect(report.logos).toBeGreaterThanOrEqual(140);
    // Logos are in the captured pixels: the image has far more colors than flat bars alone.
    const colors = await page.evaluate(async (base64) => {
      const blob = await (await fetch(`data:image/png;base64,${base64}`)).blob();
      const bitmap = await createImageBitmap(blob);
      const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
      const context = canvas.getContext("2d")!;
      context.drawImage(bitmap, 0, 0);
      const data = context.getImageData(0, 0, bitmap.width, bitmap.height).data;
      const seen = new Set<number>();
      for (let i = 0; i < data.length; i += 4 * 7) seen.add(((data[i] >> 3) << 10) | ((data[i + 1] >> 3) << 5) | (data[i + 2] >> 3));
      return seen.size;
    }, fs.readFileSync(file).toString("base64"));
    expect(colors).toBeGreaterThan(300);
  });

  test("the team param seeds the highlight and persists across charts, weeks and sides", async ({ page }) => {
    await page.goto("/charts?chart=efficiency&week=3&team=michigan");
    const michigan = page.locator("g[data-team='Michigan']");
    await expect(michigan).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("link", { name: "Adjusted PPA/play" }).click();
    await expect(page).toHaveURL(/chart=adjusted.*team=michigan/);
    await expect(michigan).toHaveAttribute("aria-pressed", "true");
    // Net success has no finder, but keeps the team for the next chart.
    await page.getByRole("link", { name: "Net success rate" }).click();
    await expect(page).toHaveURL(/chart=net-success.*team=michigan/);
    await expect(page.getByTestId("team-search")).toHaveCount(0);
    await page.getByRole("link", { name: "Efficiency vs explosiveness", exact: true }).click();
    await expect(page).toHaveURL(/chart=efficiency.*team=michigan/);
    await expect(michigan).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("link", { name: "defense", exact: true }).click();
    await expect(page).toHaveURL(/side=defense.*team=michigan/);
    await expect(michigan).toHaveAttribute("aria-pressed", "true");

    // Choosing a team rewrites the URL in place, without a navigation.
    await page.evaluate(() => { (window as typeof window & { chartMarker?: boolean }).chartMarker = true; });
    await page.getByTestId("team-highlight").selectOption("Alabama");
    await expect(page).toHaveURL(/team=Alabama/);
    await expect(page.locator("g[data-team='Alabama']")).toHaveAttribute("aria-pressed", "true");
    await page.locator("#week-select").selectOption("2");
    await expect(page).toHaveURL(/week=2.*team=Alabama|team=Alabama.*week=2/);
    await expect(page.locator("g[data-team='Alabama']")).toHaveAttribute("aria-pressed", "true");
    await page.getByTestId("team-highlight").selectOption("Alabama");
    await expect(page).not.toHaveURL(/team=/);
    expect(await page.evaluate(() => (window as typeof window & { chartMarker?: boolean }).chartMarker)).toBe(true);

    // An unknown team is ignored.
    await page.goto("/charts?chart=efficiency&week=3&team=Nowhere%20State");
    await expect(page.locator("g[data-team]")).toHaveCount(PLOTTED);
    await expect(page.getByTestId("highlight-status")).toHaveCount(0);
    await expect(page.locator("g[data-team][aria-pressed='true']")).toHaveCount(0);
  });

  test("net-success summary, outplayed band and a fixed success-gap order shared by the export", async ({ page }) => {
    await page.goto("/charts?chart=net-success&week=3");
    await expect(page.getByTestId("net-success-summary")).toHaveText(/^\d+ of 8 winners had the lower success rate\.$/);
    await expect(page.getByTestId("outplayed-band")).toHaveCount(1);
    await expect(page.getByTestId("net-success-sort")).toHaveCount(0);
    const order = await page.locator("g[data-game]").evaluateAll((nodes) => nodes.map((node) => {
      const label = node.getAttribute("aria-label")!;
      const gap = Number(label.match(/(-?[\d.]+) percentage points/)![1]) * (label.includes("disadvantage") ? -1 : 1);
      return { game: Number(node.getAttribute("data-game")), gap };
    }));
    for (let i = 1; i < order.length; i++) {
      const [prev, next] = [order[i - 1], order[i]];
      expect(next.gap > prev.gap || (next.gap === prev.gap && next.game > prev.game)).toBe(true);
    }
    const { capture } = await exportPng(page);
    expect(capture.games.map(Number)).toEqual(order.map((b) => b.game));
  });

  test("adjusted ticks use two decimals and the tooltip shows the stored decomposition", async ({ page }) => {
    await page.goto("/charts?chart=adjusted&week=3");
    const ticks = await page.getByTestId("scatter-chart").locator("svg g text").allTextContents();
    expect(ticks.some((tick) => /^[+-]?\d\.\d{2}$/.test(tick))).toBe(true);
    expect(ticks.some((tick) => /^[+-]?\d\.\d{3}$/.test(tick))).toBe(false);
    const alabama = page.locator("g[data-team='Alabama']");
    // Focus handlers attach on hydration; retry until the tooltip responds.
    await expect(async () => {
      await alabama.blur();
      await alabama.focus();
      await expect(page.getByTestId("chart-tooltip")).toBeVisible({ timeout: 500 });
    }).toPass();
    await expect(page.getByTestId("chart-tooltip")).toContainText(/Alabama .*raw .*venue correction .*opponent adjustment .*rank \d+ of \d+/);
  });
});
