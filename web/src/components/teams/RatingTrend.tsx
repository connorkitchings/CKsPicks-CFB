"use client";

import { useState } from "react";
import { ratingText } from "@/components/ratings/StatGrid";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { TeamSection } from "@/components/teams/TeamSection";
import { trendAxis, trendWeekLabels, type TeamRankPoint } from "@/lib/team-rank-history";

type Measure = "rating" | "rank";

const MEASURES = [{ value: "rating", label: "Rating" }, { value: "rank", label: "Rank" }] as const;

/** Each point is the rating after that week's games, so the last one is the pregame rating of the following week. */
const W = 320;
const H = 170;
const PAD = { left: 40, right: 12, top: 18, bottom: 26 };
function Chart({ points, measure }: { points: readonly TeamRankPoint[]; measure: Measure }) {
  const { lo, hi, ticks } = trendAxis(points.map((point) => point[measure]), measure);
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const firstWeek = points[0].week;
  const span = points[points.length - 1].week - firstWeek;
  const x = (week: number) => PAD.left + (span === 0 ? plotW / 2 : ((week - firstWeek) / span) * plotW);
  const y = (value: number) => PAD.top + (measure === "rank" ? (value - lo) / (hi - lo) : (hi - value) / (hi - lo)) * plotH;
  const coords = points.map((point) => [x(point.week), y(point[measure])] as const);
  const line = coords.map(([cx, cy]) => `${cx.toFixed(1)},${cy.toFixed(1)}`).join(" ");
  const [endX, endY] = coords[coords.length - 1];
  const last = points[points.length - 1];
  const label = (point: TeamRankPoint) => (measure === "rating" ? ratingText(point.rating) : `#${point.rank}`);
  const first = points[0];
  const weekLabels = trendWeekLabels(points.map((point) => point.week), plotW, 52);
  const summary = `${measure === "rating" ? "Overall rating" : "Overall rank"} by week: ${label(first)} after Week ${first.week}, ${label(last)} after Week ${last.week}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary} className="block h-auto w-full text-[11px]">
      {ticks.map((tick) => (
        <g key={tick}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} className={tick === 0 && measure === "rating" ? "stroke-ink-faint" : "stroke-line"} />
          <text x={PAD.left - 6} y={y(tick) + 4} textAnchor="end" className="fill-ink-muted font-mono">{measure === "rating" ? tick.toFixed(1) : `#${tick}`}</text>
        </g>
      ))}
      {coords.length > 1 && <>
        <path d={`M${line.replaceAll(" ", "L")}L${endX},${PAD.top + plotH}L${coords[0][0]},${PAD.top + plotH}Z`} className="fill-accent opacity-10" />
        <polyline points={line} fill="none" strokeWidth={2} strokeLinejoin="round" className="stroke-accent" />
      </>}
      <circle cx={endX} cy={endY} r={4} className="fill-accent" />
      <text x={endX} y={endY - 9} textAnchor="end" className="fill-ink font-mono font-semibold">{label(last)}</text>
      {weekLabels.map((week, i) => (
        <text key={week} x={x(week)} y={H - 6} textAnchor={i === 0 && weekLabels.length > 1 ? "start" : i === weekLabels.length - 1 ? "end" : "middle"} className="fill-ink-muted font-mono">Wk {week}</text>
      ))}
    </svg>
  );
}

/** Overall rating or national rank after each stored week, switchable, with the latest value labelled. */
export function RatingTrend({ points }: { points: readonly TeamRankPoint[] }) {
  const [measure, setMeasure] = useState<Measure>("rating");
  return (
    <TeamSection
      id="team-rating-trend"
      title="Rating trend"
      actions={points.length > 0 && <SegmentedControl<Measure> label="Trend measure" value={measure} onChange={setMeasure} options={MEASURES} size="sm" testId="trend-measure" />}
    >
      {points.length === 0 ? <p className="text-sm text-ink-muted">No weekly rating history is available for this team.</p> : <Chart points={points} measure={measure} />}
    </TeamSection>
  );
}
