"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import clsx from "clsx";
import type { PerformanceDetail, GradedGamePick } from "@/lib/v5";

type TargetFilter = "all" | "spread" | "total";

interface PickItem {
  week: number;
  target: "spread" | "total";
  result: "win" | "loss" | "push";
  profitUnits: number;
  highConfidence: boolean;
}

interface WeekAggregate {
  week: number;
  spread: { win: number; loss: number; push: number; units: number; winRate: number; roi: number };
  total: { win: number; loss: number; push: number; units: number; winRate: number; roi: number };
  combined: { win: number; loss: number; push: number; units: number; roi: number; winRate: number };
}

function extractPicks(games: GradedGamePick[]): PickItem[] {
  const list: PickItem[] = [];
  for (const g of games) {
    if (g.spreadResult !== null) {
      list.push({
        week: g.week,
        target: "spread",
        result: g.spreadResult,
        profitUnits: g.spreadUnits ?? (g.spreadResult === "win" ? 0.9091 : g.spreadResult === "loss" ? -1.0 : 0.0),
        highConfidence: g.highConfidence,
      });
    }
    if (g.totalResult !== null) {
      list.push({
        week: g.week,
        target: "total",
        result: g.totalResult,
        profitUnits: g.totalUnits ?? (g.totalResult === "win" ? 0.9091 : g.totalResult === "loss" ? -1.0 : 0.0),
        highConfidence: g.highConfidence,
      });
    }
  }
  return list;
}

export function PerformanceDashboard({ data }: { data: PerformanceDetail }) {
  const [targetFilter, setTargetFilter] = useState<TargetFilter>("all");
  const [confidenceOnly, setConfidenceOnly] = useState<boolean>(false);

  const allPicks = useMemo(() => extractPicks(data.gradedGames), [data.gradedGames]);

  const activePicks = useMemo(() => {
    return allPicks.filter((p) => {
      if (confidenceOnly && !p.highConfidence) return false;
      return true;
    });
  }, [allPicks, confidenceOnly]);

  // Overall KPIs
  const overallKPIs = useMemo(() => {
    let spreadWins = 0, spreadLosses = 0, spreadPushes = 0, spreadUnits = 0;
    let totalWins = 0, totalLosses = 0, totalPushes = 0, totalUnits = 0;

    for (const p of activePicks) {
      if (p.target === "spread") {
        if (p.result === "win") spreadWins++;
        else if (p.result === "loss") spreadLosses++;
        else if (p.result === "push") spreadPushes++;
        spreadUnits += p.profitUnits;
      } else {
        if (p.result === "win") totalWins++;
        else if (p.result === "loss") totalLosses++;
        else if (p.result === "push") totalPushes++;
        totalUnits += p.profitUnits;
      }
    }

    const sDecisions = spreadWins + spreadLosses;
    const sRisked = spreadWins + spreadLosses + spreadPushes;
    const sWinRate = sDecisions > 0 ? (spreadWins / sDecisions) * 100 : 0;
    const sRoi = sRisked > 0 ? (spreadUnits / sRisked) * 100 : 0;

    const tDecisions = totalWins + totalLosses;
    const tRisked = totalWins + totalLosses + totalPushes;
    const tWinRate = tDecisions > 0 ? (totalWins / tDecisions) * 100 : 0;
    const tRoi = tRisked > 0 ? (totalUnits / tRisked) * 100 : 0;

    const cWins = spreadWins + totalWins;
    const cLosses = spreadLosses + totalLosses;
    const cPushes = spreadPushes + totalPushes;
    const cUnits = spreadUnits + totalUnits;
    const cRisked = cWins + cLosses + cPushes;
    const cRoi = cRisked > 0 ? (cUnits / cRisked) * 100 : 0;

    // Focused Return depends on targetFilter
    let focusedUnits = cUnits;
    let focusedRisked = cRisked;
    let focusedRoi = cRoi;
    let focusedLabel = "Net Betting Return";

    if (targetFilter === "spread") {
      focusedUnits = spreadUnits;
      focusedRisked = sRisked;
      focusedRoi = sRoi;
      focusedLabel = "Spread Net Return";
    } else if (targetFilter === "total") {
      focusedUnits = totalUnits;
      focusedRisked = tRisked;
      focusedRoi = tRoi;
      focusedLabel = "Totals Net Return";
    }

    return {
      spread: {
        record: `${spreadWins}–${spreadLosses}–${spreadPushes}`,
        winRate: sDecisions > 0 ? `${sWinRate.toFixed(1)}%` : "—",
        units: `${spreadUnits >= 0 ? "+" : ""}${spreadUnits.toFixed(2)}u`,
        roi: `${sRisked > 0 ? `${sRoi >= 0 ? "+" : ""}${sRoi.toFixed(1)}%` : "—"}`,
        isPositive: spreadUnits >= 0,
      },
      total: {
        record: `${totalWins}–${totalLosses}–${totalPushes}`,
        winRate: tDecisions > 0 ? `${tWinRate.toFixed(1)}%` : "—",
        units: `${totalUnits >= 0 ? "+" : ""}${totalUnits.toFixed(2)}u`,
        roi: `${tRisked > 0 ? `${tRoi >= 0 ? "+" : ""}${tRoi.toFixed(1)}%` : "—"}`,
        isPositive: totalUnits >= 0,
      },
      focused: {
        label: focusedLabel,
        totalBets: focusedRisked,
        units: `${focusedUnits >= 0 ? "+" : ""}${focusedUnits.toFixed(2)}u`,
        roi: `${focusedRisked > 0 ? `${focusedRoi >= 0 ? "+" : ""}${focusedRoi.toFixed(1)}%` : "—"}`,
        isPositive: focusedUnits >= 0,
      },
    };
  }, [activePicks, targetFilter]);

  // Aggregated Weekly Breakdown Table
  const weeklyData = useMemo(() => {
    const list: WeekAggregate[] = [];

    for (const w of data.weeks) {
      const wPicks = activePicks.filter((p) => p.week === w);
      if (wPicks.length === 0) continue;

      let sw = 0, sl = 0, sp = 0, su = 0;
      let tw = 0, tl = 0, tp = 0, tu = 0;

      for (const p of wPicks) {
        if (p.target === "spread") {
          if (p.result === "win") sw++;
          else if (p.result === "loss") sl++;
          else if (p.result === "push") sp++;
          su += p.profitUnits;
        } else {
          if (p.result === "win") tw++;
          else if (p.result === "loss") tl++;
          else if (p.result === "push") tp++;
          tu += p.profitUnits;
        }
      }

      const sDec = sw + sl;
      const sRisk = sw + sl + sp;
      const sWinRate = sDec > 0 ? (sw / sDec) * 100 : 0;
      const sRoi = sRisk > 0 ? (su / sRisk) * 100 : 0;

      const tDec = tw + tl;
      const tRisk = tw + tl + tp;
      const tWinRate = tDec > 0 ? (tw / tDec) * 100 : 0;
      const tRoi = tRisk > 0 ? (tu / tRisk) * 100 : 0;

      const cRisk = sRisk + tRisk;
      const cDec = sDec + tDec;
      const netUnits = su + tu;
      const cRoi = cRisk > 0 ? (netUnits / cRisk) * 100 : 0;
      const cWinRate = cDec > 0 ? ((sw + tw) / cDec) * 100 : 0;

      list.push({
        week: w,
        spread: { win: sw, loss: sl, push: sp, units: su, winRate: sWinRate, roi: sRoi },
        total: { win: tw, loss: tl, push: tp, units: tu, winRate: tWinRate, roi: tRoi },
        combined: { win: sw + tw, loss: sl + tl, push: sp + tp, units: netUnits, roi: cRoi, winRate: cWinRate },
      });
    }

    return list;
  }, [data.weeks, activePicks]);

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* 3 Betting KPI Cards: Mobile 2+1 grid, Desktop 3-col */}
      <section aria-labelledby="kpi-heading" className="grid grid-cols-2 gap-2.5 sm:gap-4 md:grid-cols-3">
        <h2 id="kpi-heading" className="sr-only">Betting performance summary</h2>

        {/* Spread Performance Card */}
        <button
          type="button"
          onClick={() => setTargetFilter(targetFilter === "spread" ? "all" : "spread")}
          className={clsx(
            "col-span-1 rounded-xl border p-3 sm:p-5 shadow-sm transition-all text-left cursor-pointer",
            targetFilter === "spread"
              ? "border-accent ring-1 ring-accent bg-surface-card"
              : "border-line bg-surface-card hover:border-ink-faint"
          )}
        >
          <div className="flex items-center justify-between mb-1.5 sm:mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              <span className="sm:hidden">Spread</span>
              <span className="hidden sm:inline">Spread Performance</span>
            </span>
            {targetFilter === "spread" && (
              <span className="rounded bg-accent-soft px-1.5 py-0.5 text-[10px] font-semibold text-accent-ink">
                active
              </span>
            )}
          </div>
          <div className="font-mono text-2xl sm:text-4xl font-bold tracking-tight text-ink">
            {overallKPIs.spread.record}
          </div>
          <div className="mt-2 sm:mt-3 space-y-1 text-xs">
            <div className="flex items-center justify-between text-ink-muted">
              <span>Win Rate</span>
              <span className="font-mono font-medium text-ink">{overallKPIs.spread.winRate}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-ink-muted">Net Return</span>
              <span
                className={clsx(
                  "font-mono font-semibold",
                  overallKPIs.spread.isPositive ? "text-win" : "text-loss"
                )}
              >
                {overallKPIs.spread.units} <span className="hidden sm:inline">({overallKPIs.spread.roi})</span>
              </span>
            </div>
            <div className="flex items-center justify-between text-ink-muted sm:hidden">
              <span>ROI</span>
              <span
                className={clsx(
                  "font-mono font-semibold",
                  overallKPIs.spread.isPositive ? "text-win" : "text-loss"
                )}
              >
                {overallKPIs.spread.roi}
              </span>
            </div>
          </div>
        </button>

        {/* Totals Performance Card */}
        <button
          type="button"
          onClick={() => setTargetFilter(targetFilter === "total" ? "all" : "total")}
          className={clsx(
            "col-span-1 rounded-xl border p-3 sm:p-5 shadow-sm transition-all text-left cursor-pointer",
            targetFilter === "total"
              ? "border-accent ring-1 ring-accent bg-surface-card"
              : "border-line bg-surface-card hover:border-ink-faint"
          )}
        >
          <div className="flex items-center justify-between mb-1.5 sm:mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              <span className="sm:hidden">Totals</span>
              <span className="hidden sm:inline">Totals Performance</span>
            </span>
            {targetFilter === "total" && (
              <span className="rounded bg-accent-soft px-1.5 py-0.5 text-[10px] font-semibold text-accent-ink">
                active
              </span>
            )}
          </div>
          <div className="font-mono text-2xl sm:text-4xl font-bold tracking-tight text-ink">
            {overallKPIs.total.record}
          </div>
          <div className="mt-2 sm:mt-3 space-y-1 text-xs">
            <div className="flex items-center justify-between text-ink-muted">
              <span>Win Rate</span>
              <span className="font-mono font-medium text-ink">{overallKPIs.total.winRate}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-ink-muted">Net Return</span>
              <span
                className={clsx(
                  "font-mono font-semibold",
                  overallKPIs.total.isPositive ? "text-win" : "text-loss"
                )}
              >
                {overallKPIs.total.units} <span className="hidden sm:inline">({overallKPIs.total.roi})</span>
              </span>
            </div>
            <div className="flex items-center justify-between text-ink-muted sm:hidden">
              <span>ROI</span>
              <span
                className={clsx(
                  "font-mono font-semibold",
                  overallKPIs.total.isPositive ? "text-win" : "text-loss"
                )}
              >
                {overallKPIs.total.roi}
              </span>
            </div>
          </div>
        </button>

        {/* Net Betting Return Card */}
        <div className="col-span-2 md:col-span-1 rounded-xl border border-line bg-surface-card p-3 sm:p-5 shadow-sm">
          <div className="flex items-center justify-between mb-1.5 sm:mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              {overallKPIs.focused.label}
            </span>
            <span className="text-[10px] text-ink-faint font-medium">
              {overallKPIs.focused.totalBets} graded
            </span>
          </div>
          <div
            className={clsx(
              "font-mono text-2xl sm:text-4xl font-bold tracking-tight",
              overallKPIs.focused.isPositive ? "text-win" : "text-loss"
            )}
          >
            {overallKPIs.focused.units}
          </div>
          <div className="mt-2 sm:mt-3 space-y-1 text-xs">
            <div className="flex items-center justify-between text-ink-muted">
              <span>Overall ROI</span>
              <span
                className={clsx(
                  "font-mono font-semibold",
                  overallKPIs.focused.isPositive ? "text-win" : "text-loss"
                )}
              >
                {overallKPIs.focused.roi}
              </span>
            </div>
            <div className="flex items-center justify-between text-ink-muted">
              <span>Graded Volume</span>
              <span className="font-mono font-medium text-ink">{overallKPIs.focused.totalBets} picks</span>
            </div>
          </div>
        </div>
      </section>

      {/* Model Calibration Strip */}
      <section
        aria-labelledby="calibration-heading"
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 sm:gap-2.5 rounded-xl border border-line bg-surface-card px-3 sm:px-4 py-2 sm:py-2.5 shadow-sm text-xs text-ink-muted"
      >
        <h2 id="calibration-heading" className="sr-only">Model calibration</h2>
        <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
            Model Calibration
          </span>
          <span className="text-ink-faint">·</span>
          <span>
            Spread MAE <strong className="font-mono text-ink">{data.summary.marginMae !== null ? `${data.summary.marginMae.toFixed(1)} pts` : "—"}</strong>
          </span>
          <span className="text-ink-faint">·</span>
          <span>
            Total MAE <strong className="font-mono text-ink">{data.summary.totalMae !== null ? `${data.summary.totalMae.toFixed(1)} pts` : "—"}</strong>
          </span>
          {data.summary.marginCoverage95 !== null && (
            <>
              <span className="text-ink-faint">·</span>
              <span>
                95% CI <strong className="font-mono text-ink">{data.summary.marginCoverage95.toFixed(1)}%</strong>
              </span>
            </>
          )}
        </div>
        <div className="text-[11px] text-ink-faint">
          Linear calibration against closing lines
        </div>
      </section>

      {/* Filter Toolbar: Target Selector & High Confidence Toggle */}
      <section aria-labelledby="filter-heading" className="flex flex-wrap items-center justify-between gap-2.5 sm:gap-3 rounded-xl border border-line bg-surface-card p-3 sm:p-4 shadow-sm">
        <h2 id="filter-heading" className="sr-only">Dashboard filters</h2>

        {/* Target Tabs (All Picks, Spreads, Totals) */}
        <div className="inline-flex rounded-lg bg-surface-inset p-1" role="tablist" aria-label="Bet target">
          {(["all", "spread", "total"] as const).map((t) => {
            const label = t === "all" ? "All Picks" : t === "spread" ? "Spreads" : "Totals";
            return (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={targetFilter === t}
                onClick={() => setTargetFilter(t)}
                className={clsx(
                  "rounded-md px-3 sm:px-3.5 py-1 text-xs font-medium transition-colors",
                  targetFilter === t
                    ? "bg-surface-card text-ink shadow-sm"
                    : "text-ink-muted hover:text-ink"
                )}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* High Confidence Toggle */}
        <button
          type="button"
          onClick={() => setConfidenceOnly(!confidenceOnly)}
          className={clsx(
            "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
            confidenceOnly
              ? "border-accent bg-accent-soft text-accent-ink"
              : "border-line bg-surface-inset text-ink-muted hover:text-ink"
          )}
        >
          <span className={confidenceOnly ? "text-accent" : "text-ink-faint"}>★</span>
          High Confidence Only
        </button>
      </section>

      {/* Weekly Breakdown Section: Mobile Cards (sm:hidden) & Desktop Table (hidden sm:block) */}
      <section aria-labelledby="weekly-heading" className="rounded-xl border border-line bg-surface-card overflow-hidden shadow-sm">
        <h2 id="weekly-heading" className="sr-only">Weekly performance breakdown</h2>

        {/* Mobile Cards (sm:hidden) */}
        <div className="sm:hidden divide-y divide-line">
          {weeklyData.map((row) => {
            const isSpread = targetFilter === "spread";
            const isTotal = targetFilter === "total";

            return (
              <div key={row.week} className="p-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <Link
                    href={`/results?week=${row.week}`}
                    className="inline-flex items-center gap-1 text-sm font-bold text-ink hover:text-accent-ink"
                    title={`View Week ${row.week} results slate`}
                  >
                    <span>Week {row.week}</span>
                    <span className="text-ink-faint text-xs">→</span>
                  </Link>
                  {isSpread ? (
                    <div className="flex items-center gap-2 text-xs font-mono">
                      <span className={clsx("font-bold", row.spread.units >= 0 ? "text-win" : "text-loss")}>
                        {row.spread.units >= 0 ? "+" : ""}{row.spread.units.toFixed(2)}u
                      </span>
                      <span className="text-ink-muted">
                        ({row.spread.win + row.spread.loss + row.spread.push > 0 ? `${row.spread.roi >= 0 ? "+" : ""}${row.spread.roi.toFixed(1)}%` : "—"})
                      </span>
                    </div>
                  ) : isTotal ? (
                    <div className="flex items-center gap-2 text-xs font-mono">
                      <span className={clsx("font-bold", row.total.units >= 0 ? "text-win" : "text-loss")}>
                        {row.total.units >= 0 ? "+" : ""}{row.total.units.toFixed(2)}u
                      </span>
                      <span className="text-ink-muted">
                        ({row.total.win + row.total.loss + row.total.push > 0 ? `${row.total.roi >= 0 ? "+" : ""}${row.total.roi.toFixed(1)}%` : "—"})
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-xs font-mono">
                      <span className={clsx("font-bold", row.combined.units >= 0 ? "text-win" : "text-loss")}>
                        {row.combined.units >= 0 ? "+" : ""}{row.combined.units.toFixed(2)}u
                      </span>
                      <span className="text-ink-muted">
                        ({row.combined.roi >= 0 ? "+" : ""}{row.combined.roi.toFixed(1)}%)
                      </span>
                    </div>
                  )}
                </div>

                {isSpread ? (
                  <div className="flex items-center justify-between text-xs text-ink-muted bg-surface-inset rounded-lg px-2.5 py-1.5">
                    <span>Record: <strong className="text-ink font-mono">{row.spread.win}–{row.spread.loss}–{row.spread.push}</strong></span>
                    <span>Win Rate: <strong className="text-ink font-mono">{row.spread.win + row.spread.loss > 0 ? `${row.spread.winRate.toFixed(1)}%` : "—"}</strong></span>
                  </div>
                ) : isTotal ? (
                  <div className="flex items-center justify-between text-xs text-ink-muted bg-surface-inset rounded-lg px-2.5 py-1.5">
                    <span>Record: <strong className="text-ink font-mono">{row.total.win}–{row.total.loss}–{row.total.push}</strong></span>
                    <span>Win Rate: <strong className="text-ink font-mono">{row.total.win + row.total.loss > 0 ? `${row.total.winRate.toFixed(1)}%` : "—"}</strong></span>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-surface-inset rounded-lg p-2 space-y-0.5">
                      <div className="text-[10px] uppercase font-semibold text-ink-faint">Spread</div>
                      <div className="flex items-center justify-between font-mono">
                        <span className="text-ink font-medium">{row.spread.win}–{row.spread.loss}–{row.spread.push}</span>
                        <span className={clsx("font-semibold", row.spread.units >= 0 ? "text-win" : "text-loss")}>
                          {row.spread.units >= 0 ? "+" : ""}{row.spread.units.toFixed(2)}u
                        </span>
                      </div>
                    </div>
                    <div className="bg-surface-inset rounded-lg p-2 space-y-0.5">
                      <div className="text-[10px] uppercase font-semibold text-ink-faint">Totals</div>
                      <div className="flex items-center justify-between font-mono">
                        <span className="text-ink font-medium">{row.total.win}–{row.total.loss}–{row.total.push}</span>
                        <span className={clsx("font-semibold", row.total.units >= 0 ? "text-win" : "text-loss")}>
                          {row.total.units >= 0 ? "+" : ""}{row.total.units.toFixed(2)}u
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Season Total Mobile Summary */}
          <div className="p-3.5 bg-surface-inset/80 space-y-2 border-t-2 border-line">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-ink">Season Total</span>
              <div className="flex items-center gap-2 text-xs font-mono">
                <span
                  className={clsx(
                    "font-bold text-sm",
                    overallKPIs.focused.isPositive ? "text-win" : "text-loss"
                  )}
                >
                  {overallKPIs.focused.units}
                </span>
                <span className="text-ink-muted">({overallKPIs.focused.roi})</span>
              </div>
            </div>
            <div className="flex items-center justify-between text-xs text-ink-muted">
              {targetFilter === "spread" ? (
                <>
                  <span>Record: <strong className="text-ink font-mono">{overallKPIs.spread.record}</strong></span>
                  <span>Win Rate: <strong className="text-ink font-mono">{overallKPIs.spread.winRate}</strong></span>
                </>
              ) : targetFilter === "total" ? (
                <>
                  <span>Record: <strong className="text-ink font-mono">{overallKPIs.total.record}</strong></span>
                  <span>Win Rate: <strong className="text-ink font-mono">{overallKPIs.total.winRate}</strong></span>
                </>
              ) : (
                <>
                  <span>Spread: <strong className="text-ink font-mono">{overallKPIs.spread.record}</strong></span>
                  <span>Total: <strong className="text-ink font-mono">{overallKPIs.total.record}</strong></span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Desktop Table (hidden sm:block) */}
        <div className="hidden sm:block overflow-x-auto">
          {targetFilter === "spread" ? (
            /* Spreads-Only Table */
            <table className="w-full min-w-[560px] text-xs tabular-nums text-left">
              <thead className="border-b border-line bg-surface-inset text-[11px] uppercase tracking-wider text-ink-faint font-semibold">
                <tr>
                  <th scope="col" className="px-4 py-3">Week</th>
                  <th scope="col" className="px-3 py-3 text-right">Spread Record (W-L-P)</th>
                  <th scope="col" className="px-3 py-3 text-right">Win Rate</th>
                  <th scope="col" className="px-3 py-3 text-right">Profit Units</th>
                  <th scope="col" className="px-4 py-3 text-right">ROI %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {weeklyData.map((row) => (
                  <tr key={row.week} className="hover:bg-surface-inset/50 transition-colors">
                    <td className="px-4 py-3 font-semibold text-ink">
                      <Link
                        href={`/results?week=${row.week}`}
                        className="hover:text-accent-ink hover:underline"
                        title={`View Week ${row.week} results slate`}
                      >
                        Week {row.week}
                      </Link>
                    </td>
                    <td className="px-3 py-3 text-right text-ink">
                      {row.spread.win}–{row.spread.loss}–{row.spread.push}
                    </td>
                    <td className="px-3 py-3 text-right text-ink-muted">
                      {row.spread.win + row.spread.loss > 0 ? `${row.spread.winRate.toFixed(1)}%` : "—"}
                    </td>
                    <td
                      className={clsx(
                        "px-3 py-3 text-right font-medium",
                        row.spread.units >= 0 ? "text-win" : "text-loss"
                      )}
                    >
                      {row.spread.units >= 0 ? "+" : ""}{row.spread.units.toFixed(2)}u
                    </td>
                    <td className="px-4 py-3 text-right text-ink">
                      {row.spread.win + row.spread.loss + row.spread.push > 0
                        ? `${row.spread.roi >= 0 ? "+" : ""}${row.spread.roi.toFixed(1)}%`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-line bg-surface-inset font-semibold text-ink">
                <tr>
                  <td className="px-4 py-3">Season Total</td>
                  <td className="px-3 py-3 text-right">{overallKPIs.spread.record}</td>
                  <td className="px-3 py-3 text-right">{overallKPIs.spread.winRate}</td>
                  <td
                    className={clsx(
                      "px-3 py-3 text-right font-mono font-bold",
                      overallKPIs.spread.isPositive ? "text-win" : "text-loss"
                    )}
                  >
                    {overallKPIs.spread.units}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{overallKPIs.spread.roi}</td>
                </tr>
              </tfoot>
            </table>
          ) : targetFilter === "total" ? (
            /* Totals-Only Table */
            <table className="w-full min-w-[560px] text-xs tabular-nums text-left">
              <thead className="border-b border-line bg-surface-inset text-[11px] uppercase tracking-wider text-ink-faint font-semibold">
                <tr>
                  <th scope="col" className="px-4 py-3">Week</th>
                  <th scope="col" className="px-3 py-3 text-right">Totals Record (W-L-P)</th>
                  <th scope="col" className="px-3 py-3 text-right">Win Rate</th>
                  <th scope="col" className="px-3 py-3 text-right">Profit Units</th>
                  <th scope="col" className="px-4 py-3 text-right">ROI %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {weeklyData.map((row) => (
                  <tr key={row.week} className="hover:bg-surface-inset/50 transition-colors">
                    <td className="px-4 py-3 font-semibold text-ink">
                      <Link
                        href={`/results?week=${row.week}`}
                        className="hover:text-accent-ink hover:underline"
                        title={`View Week ${row.week} results slate`}
                      >
                        Week {row.week}
                      </Link>
                    </td>
                    <td className="px-3 py-3 text-right text-ink">
                      {row.total.win}–{row.total.loss}–{row.total.push}
                    </td>
                    <td className="px-3 py-3 text-right text-ink-muted">
                      {row.total.win + row.total.loss > 0 ? `${row.total.winRate.toFixed(1)}%` : "—"}
                    </td>
                    <td
                      className={clsx(
                        "px-3 py-3 text-right font-medium",
                        row.total.units >= 0 ? "text-win" : "text-loss"
                      )}
                    >
                      {row.total.units >= 0 ? "+" : ""}{row.total.units.toFixed(2)}u
                    </td>
                    <td className="px-4 py-3 text-right text-ink">
                      {row.total.win + row.total.loss + row.total.push > 0
                        ? `${row.total.roi >= 0 ? "+" : ""}${row.total.roi.toFixed(1)}%`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-line bg-surface-inset font-semibold text-ink">
                <tr>
                  <td className="px-4 py-3">Season Total</td>
                  <td className="px-3 py-3 text-right">{overallKPIs.total.record}</td>
                  <td className="px-3 py-3 text-right">{overallKPIs.total.winRate}</td>
                  <td
                    className={clsx(
                      "px-3 py-3 text-right font-mono font-bold",
                      overallKPIs.total.isPositive ? "text-win" : "text-loss"
                    )}
                  >
                    {overallKPIs.total.units}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{overallKPIs.total.roi}</td>
                </tr>
              </tfoot>
            </table>
          ) : (
            /* All Targets (Full Comparison Table) */
            <table className="w-full min-w-[620px] text-xs tabular-nums text-left">
              <thead className="border-b border-line bg-surface-inset text-[11px] uppercase tracking-wider text-ink-faint font-semibold">
                <tr>
                  <th scope="col" className="px-4 py-3">Week</th>
                  <th scope="col" className="px-3 py-3 text-right">Spread (W-L-P)</th>
                  <th scope="col" className="px-3 py-3 text-right">Spread Units</th>
                  <th scope="col" className="px-3 py-3 text-right">Total (W-L-P)</th>
                  <th scope="col" className="px-3 py-3 text-right">Total Units</th>
                  <th scope="col" className="px-3 py-3 text-right">Net Units</th>
                  <th scope="col" className="px-4 py-3 text-right">ROI %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {weeklyData.map((row) => {
                  const isNetPositive = row.combined.units >= 0;
                  return (
                    <tr key={row.week} className="hover:bg-surface-inset/50 transition-colors">
                      <td className="px-4 py-3 font-semibold text-ink">
                        <Link
                          href={`/results?week=${row.week}`}
                          className="hover:text-accent-ink hover:underline"
                          title={`View Week ${row.week} results slate`}
                        >
                          Week {row.week}
                        </Link>
                      </td>
                      <td className="px-3 py-3 text-right text-ink">
                        {row.spread.win}–{row.spread.loss}–{row.spread.push}
                      </td>
                      <td
                        className={clsx(
                          "px-3 py-3 text-right font-medium",
                          row.spread.units >= 0 ? "text-win" : "text-loss"
                        )}
                      >
                        {row.spread.units >= 0 ? "+" : ""}{row.spread.units.toFixed(2)}u
                      </td>
                      <td className="px-3 py-3 text-right text-ink">
                        {row.total.win}–{row.total.loss}–{row.total.push}
                      </td>
                      <td
                        className={clsx(
                          "px-3 py-3 text-right font-medium",
                          row.total.units >= 0 ? "text-win" : "text-loss"
                        )}
                      >
                        {row.total.units >= 0 ? "+" : ""}{row.total.units.toFixed(2)}u
                      </td>
                      <td
                        className={clsx(
                          "px-3 py-3 text-right font-semibold",
                          isNetPositive ? "text-win" : "text-loss"
                        )}
                      >
                        {isNetPositive ? "+" : ""}{row.combined.units.toFixed(2)}u
                      </td>
                      <td className="px-4 py-3 text-right text-ink">
                        {row.combined.roi >= 0 ? "+" : ""}{row.combined.roi.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot className="border-t-2 border-line bg-surface-inset font-semibold text-ink">
                <tr>
                  <td className="px-4 py-3">Season Total</td>
                  <td className="px-3 py-3 text-right">
                    {overallKPIs.spread.record}
                  </td>
                  <td
                    className={clsx(
                      "px-3 py-3 text-right font-mono font-bold",
                      overallKPIs.spread.isPositive ? "text-win" : "text-loss"
                    )}
                  >
                    {overallKPIs.spread.units}
                  </td>
                  <td className="px-3 py-3 text-right">
                    {overallKPIs.total.record}
                  </td>
                  <td
                    className={clsx(
                      "px-3 py-3 text-right font-mono font-bold",
                      overallKPIs.total.isPositive ? "text-win" : "text-loss"
                    )}
                  >
                    {overallKPIs.total.units}
                  </td>
                  <td
                    className={clsx(
                      "px-3 py-3 text-right font-mono font-bold",
                      overallKPIs.focused.isPositive ? "text-win" : "text-loss"
                    )}
                  >
                    {overallKPIs.focused.units}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {overallKPIs.focused.roi}
                  </td>
                </tr>
              </tfoot>
            </table>
          )}
        </div>
      </section>

      {/* Helpful Slate Deep Dive Note */}
      <p className="text-xs text-ink-muted">
        💡 Click any week above to view the full game-by-game results and graded picks on the Results tab.
      </p>
    </div>
  );
}
