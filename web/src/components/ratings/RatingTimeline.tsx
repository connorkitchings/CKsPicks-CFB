"use client";

import { nationalRanks, ratingField, type RatingHistoryPeriod, type RatingMetric } from "@/lib/team-analysis";
import { trendAxis } from "@/lib/team-rank-history";
import { Notice } from "@/components/ui/Notice";

/** Two bounded series at most. Missing certified weeks remain visible breaks, not interpolation. */
export function RatingTimeline({ history, teams, metric, measure }: { history: readonly RatingHistoryPeriod[]; teams: readonly string[]; metric: RatingMetric; measure: "rating" | "rank" }) {
  const series = teams.slice(0, 2).map((team) => history.map((entry, index) => {
    const row = entry.ratings.find((r) => r.team === team);
    const value = row ? measure === "rating" ? row[ratingField[metric]] : nationalRanks(entry.ratings, metric).get(team) : undefined;
    return { index, team, period: entry.period, value };
  }));
  const values = series.flatMap((points) => points.flatMap((p) => p.value === undefined ? [] : [p.value]));
  if (!teams.length) return <Notice tone="empty">Choose a team to explore its rating history.</Notice>;
  if (!values.length) return <Notice tone="empty">No exact-period history is available for these teams.</Notice>;
  const { lo, hi, ticks } = trendAxis(values, measure);
  const x = (i: number) => 55 + (history.length < 2 ? 320 : i / (history.length - 1) * 640);
  const y = (value: number) => 25 + (measure === "rank" ? (value - lo) : (hi - value)) / (hi - lo) * 220;
  const colors = ["var(--accent)", "var(--ink)"];
  return <section aria-label="Rating trajectory" className="space-y-3"><ul className="flex flex-wrap gap-4 text-sm">{teams.map((team, index) => <li key={team}><span aria-hidden style={{ color: colors[index] }}>● </span>{team}{index === 1 && " (dashed)"}</li>)}</ul><svg viewBox="0 0 740 300" role="img" aria-label={`${metric} ${measure} through the selected period; missing weeks are gaps`} className="w-full rounded-xl border border-line bg-surface-card"><rect x="55" y="25" width="640" height="220" fill="none" stroke="var(--line)" />{ticks.map((tick) => <g key={tick}><line x1="55" x2="695" y1={y(tick)} y2={y(tick)} stroke="var(--line)" /><text x="47" y={y(tick) + 4} textAnchor="end" fontSize="12" fill="var(--ink-muted)">{measure === "rank" ? `#${tick}` : tick.toFixed(1)}</text></g>)}{series.map((points, seriesIndex) => <g key={teams[seriesIndex]}>{points.map((p, index) => {
    if (p.value === undefined) return null;
    const prior = points[index - 1];
    const consecutive = prior && prior.value !== undefined && ((prior.period.id === "preseason" && p.period.postWeek === 0) || (prior.period.postWeek !== undefined && p.period.postWeek === prior.period.postWeek + 1));
    return <g key={p.period.id}>{consecutive && <line x1={x(prior.index)} x2={x(p.index)} y1={y(prior.value!)} y2={y(p.value)} stroke={colors[seriesIndex]} strokeWidth="2.5" strokeDasharray={seriesIndex === 1 ? "6 4" : undefined} />}<circle cx={x(p.index)} cy={y(p.value)} r="4" fill={colors[seriesIndex]}><title>{`${p.team}, ${p.period.label}: ${measure === "rank" ? `#${p.value}` : p.value.toFixed(2)}`}</title></circle></g>;
  })}</g>)}{history.map((entry, index) => (index === 0 || index === history.length - 1 || index % Math.max(1, Math.ceil(history.length / 5)) === 0) && <text key={entry.period.id} x={x(index)} y="270" textAnchor="middle" fill="var(--ink-muted)" fontSize="12">{entry.period.id === "preseason" ? "Pre" : entry.period.postWeek === undefined ? entry.period.cutoffUtc?.slice(5, 10) : `W${entry.period.postWeek}`}</text>)}</svg><p className="text-xs text-ink-muted">Week labels mean through that week. National ranks use the full period population. Gaps indicate missing certified weeks.</p><details className="rounded-lg border border-line p-3"><summary className="min-h-11 cursor-pointer text-sm font-semibold">Show trend as table</summary><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th className="p-2 text-left">Period</th>{teams.map((team) => <th key={team} className="p-2 text-right">{team}</th>)}</tr></thead><tbody>{history.map((entry, index) => <tr key={entry.period.id} className="border-t border-line"><th className="p-2 text-left font-normal">{entry.period.label}</th>{series.map((points, seriesIndex) => <td key={teams[seriesIndex]} className="p-2 text-right tabular-nums">{points[index].value === undefined ? "—" : measure === "rank" ? `#${points[index].value}` : points[index].value.toFixed(2)}</td>)}</tr>)}</tbody></table></div></details></section>;
}
