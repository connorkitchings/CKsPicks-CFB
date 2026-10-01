"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";
import clsx from "clsx";
import type { PerformanceDetail, GradedGamePick } from "@/lib/v5";
import { logoUrl } from "@/lib/teams";
import {
  marketSpreadView,
  modelSpreadView,
  spreadLabel,
  signedSpread,
  spreadBetLabel,
  totalBetLabel,
} from "@/lib/betting-format";

type TargetFilter = "all" | "spread" | "total";
type ActiveTab = "log" | "weekly";

interface FlatPick {
  id: string;
  gameId: number;
  week: number;
  startDate: Date;
  homeTeam: string;
  awayTeam: string;
  homePoints: number | null;
  awayPoints: number | null;
  target: "spread" | "total";
  marketLine: string;
  modelPrediction: string;
  edge: number | null;
  pickLabel: string;
  result: "win" | "loss" | "push";
  profitUnits: number;
  highConfidence: boolean;
  evidenceClass: "replay" | "live";
}

function formatShortDate(date: Date): string {
  const d = new Date(date);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function flattenPicks(games: GradedGamePick[]): FlatPick[] {
  const picks: FlatPick[] = [];

  for (const g of games) {
    if (g.spreadResult !== null) {
      const mSpread = marketSpreadView(g.homeTeam, g.awayTeam, g.marketSpread);
      const modSpread = modelSpreadView(g.homeTeam, g.awayTeam, g.predictedSpread);
      const bet = spreadBetLabel(g.homeTeam, g.awayTeam, g.spreadLean, g.marketSpread);

      picks.push({
        id: `${g.gameId}-spread`,
        gameId: g.gameId,
        week: g.week,
        startDate: g.startDate,
        homeTeam: g.homeTeam,
        awayTeam: g.awayTeam,
        homePoints: g.homePoints,
        awayPoints: g.awayPoints,
        target: "spread",
        marketLine: spreadLabel(mSpread),
        modelPrediction: spreadLabel(modSpread),
        edge: g.spreadEdge,
        pickLabel: bet ?? "Spread Lean",
        result: g.spreadResult,
        profitUnits: g.spreadUnits ?? (g.spreadResult === "win" ? 0.9091 : g.spreadResult === "loss" ? -1.0 : 0.0),
        highConfidence: g.highConfidence,
        evidenceClass: g.evidenceClass,
      });
    }

    if (g.totalResult !== null) {
      const bet = totalBetLabel(g.totalLean, g.marketTotal);

      picks.push({
        id: `${g.gameId}-total`,
        gameId: g.gameId,
        week: g.week,
        startDate: g.startDate,
        homeTeam: g.homeTeam,
        awayTeam: g.awayTeam,
        homePoints: g.homePoints,
        awayPoints: g.awayPoints,
        target: "total",
        marketLine: g.marketTotal !== null ? g.marketTotal.toFixed(1) : "—",
        modelPrediction: g.predictedTotal !== null ? g.predictedTotal.toFixed(1) : "—",
        edge: g.totalEdge,
        pickLabel: bet ?? "Total Lean",
        result: g.totalResult,
        profitUnits: g.totalUnits ?? (g.totalResult === "win" ? 0.9091 : g.totalResult === "loss" ? -1.0 : 0.0),
        highConfidence: g.highConfidence,
        evidenceClass: g.evidenceClass,
      });
    }
  }

  return picks;
}

export function PerformanceDashboard({ data }: { data: PerformanceDetail }) {
  const [targetFilter, setTargetFilter] = useState<TargetFilter>("all");
  const [selectedWeek, setSelectedWeek] = useState<string>("all");
  const [confidenceOnly, setConfidenceOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [activeTab, setActiveTab] = useState<ActiveTab>("log");

  const allPicks = useMemo(() => flattenPicks(data.gradedGames), [data.gradedGames]);

  const filteredPicks = useMemo(() => {
    return allPicks.filter((pick) => {
      if (targetFilter !== "all" && pick.target !== targetFilter) return false;
      if (selectedWeek !== "all" && pick.week !== Number(selectedWeek)) return false;
      if (confidenceOnly && !pick.highConfidence) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesTeam =
          pick.homeTeam.toLowerCase().includes(q) || pick.awayTeam.toLowerCase().includes(q);
        if (!matchesTeam) return false;
      }
      return true;
    });
  }, [allPicks, targetFilter, selectedWeek, confidenceOnly, searchQuery]);

  // Dynamic Metrics for active filtered slice
  const stats = useMemo(() => {
    let spreadWins = 0, spreadLosses = 0, spreadPushes = 0, spreadUnits = 0;
    let totalWins = 0, totalLosses = 0, totalPushes = 0, totalUnits = 0;

    for (const p of filteredPicks) {
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

    const spreadDecisions = spreadWins + spreadLosses;
    const spreadRisked = spreadWins + spreadLosses + spreadPushes;
    const spreadWinRate = spreadDecisions > 0 ? (spreadWins / spreadDecisions) * 100 : 0;
    const spreadRoi = spreadRisked > 0 ? (spreadUnits / spreadRisked) * 100 : 0;

    const totalDecisions = totalWins + totalLosses;
    const totalRisked = totalWins + totalLosses + totalPushes;
    const totalWinRate = totalDecisions > 0 ? (totalWins / totalDecisions) * 100 : 0;
    const totalRoi = totalRisked > 0 ? (totalUnits / totalRisked) * 100 : 0;

    const combinedWins = spreadWins + totalWins;
    const combinedLosses = spreadLosses + totalLosses;
    const combinedPushes = spreadPushes + totalPushes;
    const combinedUnits = spreadUnits + totalUnits;
    const combinedDecisions = combinedWins + combinedLosses;
    const combinedRisked = combinedWins + combinedLosses + combinedPushes;
    const combinedWinRate = combinedDecisions > 0 ? (combinedWins / combinedDecisions) * 100 : 0;
    const combinedRoi = combinedRisked > 0 ? (combinedUnits / combinedRisked) * 100 : 0;

    return {
      spread: {
        record: `${spreadWins}–${spreadLosses}–${spreadPushes}`,
        winRate: spreadDecisions > 0 ? `${spreadWinRate.toFixed(1)}%` : "—",
        units: `${spreadUnits >= 0 ? "+" : ""}${spreadUnits.toFixed(2)}u`,
        roi: `${spreadRisked > 0 ? `${spreadRoi >= 0 ? "+" : ""}${spreadRoi.toFixed(1)}%` : "—"}`,
        isUnitsPositive: spreadUnits >= 0,
      },
      total: {
        record: `${totalWins}–${totalLosses}–${totalPushes}`,
        winRate: totalDecisions > 0 ? `${totalWinRate.toFixed(1)}%` : "—",
        units: `${totalUnits >= 0 ? "+" : ""}${totalUnits.toFixed(2)}u`,
        roi: `${totalRisked > 0 ? `${totalRoi >= 0 ? "+" : ""}${totalRoi.toFixed(1)}%` : "—"}`,
        isUnitsPositive: totalUnits >= 0,
      },
      combined: {
        record: `${combinedWins}–${combinedLosses}–${combinedPushes}`,
        totalBets: combinedRisked,
        winRate: combinedDecisions > 0 ? `${combinedWinRate.toFixed(1)}%` : "—",
        units: `${combinedUnits >= 0 ? "+" : ""}${combinedUnits.toFixed(2)}u`,
        roi: `${combinedRisked > 0 ? `${combinedRoi >= 0 ? "+" : ""}${combinedRoi.toFixed(1)}%` : "—"}`,
        isUnitsPositive: combinedUnits >= 0,
      },
    };
  }, [filteredPicks]);

  // Calibration metrics from active week slice or overall
  const activeCalibration = useMemo(() => {
    if (selectedWeek !== "all") {
      const weekNum = Number(selectedWeek);
      const wSummary = data.byWeek[weekNum];
      if (wSummary) {
        return {
          marginMae: wSummary.marginMae !== null ? `${wSummary.marginMae.toFixed(1)} pts` : "—",
          totalMae: wSummary.totalMae !== null ? `${wSummary.totalMae.toFixed(1)} pts` : "—",
          coverage: wSummary.marginCoverage95 !== null ? `${wSummary.marginCoverage95.toFixed(1)}%` : "—",
        };
      }
    }
    return {
      marginMae: data.summary.marginMae !== null ? `${data.summary.marginMae.toFixed(1)} pts` : "—",
      totalMae: data.summary.totalMae !== null ? `${data.summary.totalMae.toFixed(1)} pts` : "—",
      coverage: data.summary.marginCoverage95 !== null ? `${data.summary.marginCoverage95.toFixed(1)}%` : "—",
    };
  }, [selectedWeek, data]);

  return (
    <div className="space-y-6">
      {/* 4-Card Hero KPI Grid */}
      <section aria-labelledby="kpi-heading" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <h2 id="kpi-heading" className="sr-only">Performance metrics</h2>

        {/* Spread KPI Card */}
        <div className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
            Spread Performance
          </p>
          <div className="mt-2 font-mono text-2xl font-bold tracking-tight text-ink">
            {stats.spread.record}
          </div>
          <div className="mt-1 flex items-center justify-between text-xs">
            <span className="text-ink-muted">{stats.spread.winRate} win rate</span>
            <span
              className={clsx(
                "font-mono font-semibold",
                stats.spread.isUnitsPositive ? "text-win" : "text-loss"
              )}
            >
              {stats.spread.units} ({stats.spread.roi} ROI)
            </span>
          </div>
        </div>

        {/* Total KPI Card */}
        <div className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
            Totals Performance
          </p>
          <div className="mt-2 font-mono text-2xl font-bold tracking-tight text-ink">
            {stats.total.record}
          </div>
          <div className="mt-1 flex items-center justify-between text-xs">
            <span className="text-ink-muted">{stats.total.winRate} win rate</span>
            <span
              className={clsx(
                "font-mono font-semibold",
                stats.total.isUnitsPositive ? "text-win" : "text-loss"
              )}
            >
              {stats.total.units} ({stats.total.roi} ROI)
            </span>
          </div>
        </div>

        {/* Combined Profit KPI Card */}
        <div className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
            Net Betting Return
          </p>
          <div
            className={clsx(
              "mt-2 font-mono text-2xl font-bold tracking-tight",
              stats.combined.isUnitsPositive ? "text-win" : "text-loss"
            )}
          >
            {stats.combined.units}
          </div>
          <div className="mt-1 flex items-center justify-between text-xs">
            <span className="text-ink-muted">{stats.combined.totalBets} graded bets</span>
            <span className="font-mono font-semibold text-ink">
              {stats.combined.roi} ROI
            </span>
          </div>
        </div>

        {/* Model Accuracy Card */}
        <div className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
            Model Calibration
          </p>
          <div className="mt-2 font-mono text-xl font-bold tracking-tight text-ink">
            {activeCalibration.marginMae} <span className="text-xs font-normal text-ink-faint">margin MAE</span>
          </div>
          <div className="mt-1 flex items-center justify-between text-xs text-ink-muted">
            <span>Total: {activeCalibration.totalMae}</span>
            <span>95% CI: {activeCalibration.coverage}</span>
          </div>
        </div>
      </section>

      {/* Filter Toolbar & Tab Switcher */}
      <section aria-labelledby="filter-heading" className="rounded-xl border border-line bg-surface-card p-4 shadow-sm space-y-4">
        <h2 id="filter-heading" className="sr-only">Dashboard filters</h2>

        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Target Tabs */}
          <div className="inline-flex rounded-lg bg-surface-inset p-1" role="tablist" aria-label="Bet target">
            {(["all", "spread", "total"] as const).map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={targetFilter === t}
                onClick={() => setTargetFilter(t)}
                className={clsx(
                  "rounded-md px-3 py-1 text-xs font-medium capitalize transition-colors",
                  targetFilter === t
                    ? "bg-surface-card text-ink shadow-sm"
                    : "text-ink-muted hover:text-ink"
                )}
              >
                {t === "all" ? "All Targets" : `${t}s`}
              </button>
            ))}
          </div>

          {/* View Mode Tabs: Audit Log vs Weekly Table */}
          <div className="inline-flex rounded-lg bg-surface-inset p-1">
            <button
              type="button"
              onClick={() => setActiveTab("log")}
              className={clsx(
                "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                activeTab === "log"
                  ? "bg-surface-card text-ink shadow-sm"
                  : "text-ink-muted hover:text-ink"
              )}
            >
              Graded Picks ({filteredPicks.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("weekly")}
              className={clsx(
                "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                activeTab === "weekly"
                  ? "bg-surface-card text-ink shadow-sm"
                  : "text-ink-muted hover:text-ink"
              )}
            >
              Weekly Breakdown
            </button>
          </div>
        </div>

        {/* Secondary Filters: Week, Confidence, Search */}
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-line">
          {/* Week Dropdown */}
          <div className="flex items-center gap-2">
            <label htmlFor="week-select" className="text-xs font-medium text-ink-muted">
              Week:
            </label>
            <select
              id="week-select"
              value={selectedWeek}
              onChange={(e) => setSelectedWeek(e.target.value)}
              className="rounded-lg border border-line bg-surface-inset px-2.5 py-1 text-xs font-medium text-ink focus:outline-none focus:ring-1 focus:ring-accent"
            >
              <option value="all">All Weeks</option>
              {data.weeks.map((w) => (
                <option key={w} value={String(w)}>
                  Week {w}
                </option>
              ))}
            </select>
          </div>

          {/* High Confidence Toggle */}
          <button
            type="button"
            onClick={() => setConfidenceOnly(!confidenceOnly)}
            className={clsx(
              "flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors",
              confidenceOnly
                ? "border-accent bg-accent-soft text-accent-ink"
                : "border-line bg-surface-inset text-ink-muted hover:text-ink"
            )}
          >
            <span className={confidenceOnly ? "text-accent" : "text-ink-faint"}>★</span>
            High Confidence Only
          </button>

          {/* Search Input */}
          <div className="ml-auto w-full sm:w-auto">
            <input
              type="search"
              placeholder="Filter by team..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full sm:w-56 rounded-lg border border-line bg-surface-inset px-3 py-1 text-xs text-ink placeholder:text-ink-faint focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
        </div>
      </section>

      {/* Main Content: Audit Log Table vs Weekly Breakdown Table */}
      {activeTab === "weekly" ? (
        <section aria-labelledby="weekly-heading" className="rounded-xl border border-line bg-surface-card overflow-hidden shadow-sm">
          <h2 id="weekly-heading" className="sr-only">Weekly breakdown</h2>
          <div className="overflow-x-auto">
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
                {data.weeks.map((w) => {
                  const ws = data.byWeek[w];
                  if (!ws) return null;
                  const isNetPositive = ws.combined.units >= 0;
                  return (
                    <tr key={w} className="hover:bg-surface-inset/50 transition-colors">
                      <td className="px-4 py-3 font-semibold text-ink">
                        Week {w}
                        {w <= 4 && (
                          <span className="ml-1.5 rounded bg-surface-inset px-1 py-0.5 text-[10px] font-normal text-ink-faint">
                            replay
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-right text-ink">
                        {ws.spread.win}–{ws.spread.loss}–{ws.spread.push}
                      </td>
                      <td
                        className={clsx(
                          "px-3 py-3 text-right font-medium",
                          ws.spread.units >= 0 ? "text-win" : "text-loss"
                        )}
                      >
                        {ws.spread.units >= 0 ? "+" : ""}{ws.spread.units.toFixed(2)}u
                      </td>
                      <td className="px-3 py-3 text-right text-ink">
                        {ws.total.win}–{ws.total.loss}–{ws.total.push}
                      </td>
                      <td
                        className={clsx(
                          "px-3 py-3 text-right font-medium",
                          ws.total.units >= 0 ? "text-win" : "text-loss"
                        )}
                      >
                        {ws.total.units >= 0 ? "+" : ""}{ws.total.units.toFixed(2)}u
                      </td>
                      <td
                        className={clsx(
                          "px-3 py-3 text-right font-semibold",
                          isNetPositive ? "text-win" : "text-loss"
                        )}
                      >
                        {isNetPositive ? "+" : ""}{ws.combined.units.toFixed(2)}u
                      </td>
                      <td className="px-4 py-3 text-right text-ink">
                        {ws.combined.roi >= 0 ? "+" : ""}{ws.combined.roi.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <section aria-labelledby="picks-heading" className="space-y-3">
          <h2 id="picks-heading" className="sr-only">Graded picks log</h2>

          {filteredPicks.length === 0 ? (
            <div className="rounded-xl border border-line bg-surface-card p-8 text-center text-sm text-ink-muted">
              No graded picks match the selected filters.
            </div>
          ) : (
            <div className="rounded-xl border border-line bg-surface-card overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[700px] text-xs tabular-nums text-left">
                  <thead className="border-b border-line bg-surface-inset text-[11px] uppercase tracking-wider text-ink-faint font-semibold">
                    <tr>
                      <th scope="col" className="px-4 py-3">Date / Week</th>
                      <th scope="col" className="px-3 py-3">Matchup</th>
                      <th scope="col" className="px-3 py-3">Final</th>
                      <th scope="col" className="px-3 py-3">Target</th>
                      <th scope="col" className="px-3 py-3">Market</th>
                      <th scope="col" className="px-3 py-3">Model</th>
                      <th scope="col" className="px-3 py-3">Pick</th>
                      <th scope="col" className="px-3 py-3 text-center">Result</th>
                      <th scope="col" className="px-4 py-3 text-right">Profit</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {filteredPicks.map((pick) => {
                      const isWin = pick.result === "win";
                      const isLoss = pick.result === "loss";
                      return (
                        <tr key={pick.id} className="hover:bg-surface-inset/50 transition-colors">
                          {/* Date & Week */}
                          <td className="px-4 py-3 whitespace-nowrap text-ink-muted">
                            <div>{formatShortDate(pick.startDate)}</div>
                            <div className="text-[10px] text-ink-faint">Wk {pick.week}</div>
                          </td>

                          {/* Matchup */}
                          <td className="px-3 py-3">
                            <div className="flex items-center gap-1.5 font-medium text-ink">
                              <span className="flex items-center gap-1">
                                <Image
                                  src={logoUrl(pick.awayTeam)}
                                  alt=""
                                  width={14}
                                  height={14}
                                  className="h-3.5 w-3.5 shrink-0 object-contain"
                                />
                                <Link
                                  href={`/teams/${encodeURIComponent(pick.awayTeam)}`}
                                  className="hover:underline"
                                >
                                  {pick.awayTeam}
                                </Link>
                              </span>
                              <span className="text-ink-faint">@</span>
                              <span className="flex items-center gap-1">
                                <Image
                                  src={logoUrl(pick.homeTeam)}
                                  alt=""
                                  width={14}
                                  height={14}
                                  className="h-3.5 w-3.5 shrink-0 object-contain"
                                />
                                <Link
                                  href={`/teams/${encodeURIComponent(pick.homeTeam)}`}
                                  className="hover:underline"
                                >
                                  {pick.homeTeam}
                                </Link>
                              </span>
                            </div>
                          </td>

                          {/* Final Score */}
                          <td className="px-3 py-3 whitespace-nowrap font-mono text-ink">
                            {pick.homePoints !== null && pick.awayPoints !== null
                              ? `${pick.awayPoints}–${pick.homePoints}`
                              : "—"}
                          </td>

                          {/* Target Badge */}
                          <td className="px-3 py-3 whitespace-nowrap">
                            <span
                              className={clsx(
                                "inline-block rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                                pick.target === "spread"
                                  ? "bg-surface-inset text-ink-muted"
                                  : "bg-surface-inset text-accent-ink"
                              )}
                            >
                              {pick.target}
                            </span>
                          </td>

                          {/* Market Line */}
                          <td className="px-3 py-3 whitespace-nowrap font-mono text-ink-muted">
                            {pick.marketLine}
                          </td>

                          {/* Model Forecast & Edge */}
                          <td className="px-3 py-3 whitespace-nowrap font-mono text-ink">
                            <span>{pick.modelPrediction}</span>
                            {pick.edge !== null && (
                              <span className="ml-1 text-[11px] text-accent-ink">
                                ({signedSpread(pick.edge)})
                              </span>
                            )}
                          </td>

                          {/* Pick Label */}
                          <td className="px-3 py-3 whitespace-nowrap font-medium text-ink">
                            <div className="flex items-center gap-1">
                              {pick.highConfidence && (
                                <span className="text-accent text-xs" title="High confidence pick">
                                  ★
                                </span>
                              )}
                              <span>{pick.pickLabel}</span>
                            </div>
                          </td>

                          {/* Result Pill */}
                          <td className="px-3 py-3 text-center whitespace-nowrap">
                            <span
                              className={clsx(
                                "inline-block rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider",
                                isWin && "bg-win-soft text-win",
                                isLoss && "bg-loss-soft text-loss",
                                pick.result === "push" && "bg-surface-inset text-ink-muted"
                              )}
                            >
                              {pick.result}
                            </span>
                          </td>

                          {/* Profit Units */}
                          <td
                            className={clsx(
                              "px-4 py-3 text-right font-mono font-semibold whitespace-nowrap",
                              pick.profitUnits > 0 && "text-win",
                              pick.profitUnits < 0 && "text-loss",
                              pick.profitUnits === 0 && "text-ink-faint"
                            )}
                          >
                            {pick.profitUnits > 0 ? "+" : ""}
                            {pick.profitUnits.toFixed(2)}u
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
