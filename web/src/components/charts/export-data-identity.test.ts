import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import nodeModule from "node:module";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

type ResolveResult = { url: string; shortCircuit?: boolean };
type LoadResult = { format?: string; source?: string; shortCircuit?: boolean };
const { registerHooks } = nodeModule as unknown as { registerHooks(hooks: {
  resolve: (specifier: string, context: { parentURL?: string }, next: (specifier: string, context: object) => ResolveResult) => ResolveResult;
  load: (url: string, context: object, next: (url: string, context: object) => LoadResult) => LoadResult;
}): void };
const root = path.resolve("src");
registerHooks({
  resolve(specifier, context, next) {
    if (specifier === "next/navigation") return { url: "test:navigation", shortCircuit: true };
    if (specifier.endsWith("/ChartFrame") || specifier === "./ChartFrame") return { url: "test:frame", shortCircuit: true };
    if (specifier === "next/link") return next("next/link.js", context);
    if (specifier.startsWith("@/") || specifier.startsWith(".")) {
      const base = specifier.startsWith("@/") ? path.join(root, specifier.slice(2)) : path.resolve(path.dirname(fileURLToPath(context.parentURL!)), specifier);
      for (const candidate of [base, `${base}.ts`, `${base}.tsx`, path.join(base, "index.ts")]) {
        if (existsSync(candidate) && /\.tsx?$/.test(candidate)) return { url: pathToFileURL(candidate).href, shortCircuit: true };
      }
    }
    return next(specifier, context);
  },
  load(url, context, next) {
    if (url === "test:navigation") return { format: "module", shortCircuit: true, source: 'export const usePathname = () => "/stats"; export const useSearchParams = () => new URLSearchParams();' };
    if (url === "test:frame") return { format: "module", shortCircuit: true, source: 'export const EXPORT_SIZE = { width: 1000, height: 562.5 }; export const EXPORT_CHART_HEIGHT = 406.5; export const ExportCard = () => null; export const HighlightStatus = () => null; export function ChartFrame(props) { globalThis.__chartExportKey = props.exportSpec.contentKey; return null; }' };
    if (!url.endsWith(".tsx")) return next(url, context);
    return { format: "module", shortCircuit: true, source: ts.transpileModule(readFileSync(fileURLToPath(url), "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText };
  },
});

const fixtures = await import("@/test/fixtures/charts");
const charts = await import("@/lib/charts");
const config = await import("@/lib/chart-config");
const { reusablePreparedImage } = await import("@/lib/share-image");
const { ScatterView } = await import("./ScatterView");
const { NetSuccessView } = await import("./NetSuccessView");
const { GameLogView } = await import("./GameLogView");
const { TrajectoryPanel } = await import("./TrajectoryPanel");
const { MarketBoardView } = await import("./MarketBoardView");
const shared = { season: 2026, week: 3, roster: fixtures.chartsRosterFixture, filter: "all", highlight: null, onFilterChange: () => {}, onHighlight: () => {} } as const;
const scatter = charts.efficiencyPoints(shared.roster, fixtures.chartsGameRowsFixture, 3, "offense", "ppa");
const bars = charts.netSuccessBars(fixtures.chartsGameRowsFixture, 3).bars;
const trajectory = charts.ratingTrajectorySeries(shared.roster, fixtures.chartsRatingSnapshotsFixture(), "overall");
const games = fixtures.chartsSlateMarketGamesFixture(3);
const cases = [
  { name: "scatter", data: scatter, change: (d: typeof scatter) => { d.points[0].x += 0.1; }, render: (data: typeof scatter) => React.createElement(ScatterView, { shared, kind: "efficiency", side: "offense", data, config: config.efficiencyConfig("offense", "ppa"), describe: () => "" }) },
  { name: "net success", data: bars, change: (d: typeof bars) => { d[0].value += 0.1; }, render: (data: typeof bars) => React.createElement(NetSuccessView, { shared, bars: data, notCharted: [] }) },
  { name: "game log", data: fixtures.chartsGameRowsFixture, change: (d: typeof fixtures.chartsGameRowsFixture) => { d[0].offSuccessSum += 10; }, render: (rows: typeof fixtures.chartsGameRowsFixture) => React.createElement(GameLogView, { shared: { ...shared, highlight: rows[0].team }, rows, adjusted: fixtures.chartsAdjustedFixture(3), initialMetric: "success", explosiveness: false }) },
  { name: "trajectory", data: trajectory, change: (d: typeof trajectory) => { d.series[0].values[0]! += 1; }, render: (data: typeof trajectory) => React.createElement(TrajectoryPanel, { shared, kind: "rating-trajectory", data, metric: { label: "Overall", slug: "overall", yLabel: "Overall" }, metricControl: null, formatTick: String, formatCell: () => "" }) },
  { name: "market board", data: games, change: (d: typeof games) => { d[0].predictedSpread! += 1; }, render: (data: typeof games) => React.createElement(MarketBoardView, { shared, games: data, initialMetric: "spread" }) },
];
for (const entry of cases) test(`${entry.name} invalidates a prepared image when the data changes`, () => {
  const key = (data: never) => { renderToStaticMarkup(entry.render(data)); return (globalThis as typeof globalThis & { __chartExportKey: string }).__chartExportKey; };
  const original = structuredClone(entry.data);
  const first = key(original as never);
  assert.equal(key(structuredClone(original) as never), first);
  const changed = structuredClone(original);
  (entry.change as (value: typeof changed) => void)(changed);
  const identity = { contentKey: first, filename: "chart.png", title: "Chart", width: 1000, height: 562.5, background: "", theme: "light" as const };
  assert.equal(reusablePreparedImage({ identity, file: "old" }, { ...identity, contentKey: key(structuredClone(original) as never) }), "old");
  assert.equal(reusablePreparedImage({ identity, file: "old" }, { ...identity, contentKey: key(changed as never) }), null);
});
