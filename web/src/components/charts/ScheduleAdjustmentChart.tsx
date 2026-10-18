"use client";

import { formatEpaTick } from "@/lib/chart-config";
import { formatEpa, niceTicks, type Domain, type ScheduleRow, type ScheduleSubset } from "@/lib/charts";
import { teamAbbr } from "@/lib/team-logos";
import { TeamMark } from "./TeamMark";
import { useChartSelection } from "./useChartSelection";

export type ScheduleAdjustmentChartProps = {
  subset: ScheduleSubset;
  /** National domain, so filtering never moves a team. */
  domain: Domain;
  invert: boolean;
  axisLabel: string;
  highlight: string | null;
  onToggleHighlight: (team: string) => void;
  describe: (row: ScheduleRow) => string;
  /** ViewBox width; the SVG scales to its container. */
  width: number;
  interactive?: boolean;
  label: string;
};

const ROW = 24;
const FOOT = 34;
/** Narrower views abbreviate team names and wrap the legend caption. */
const isWide = (width: number) => width >= 800;
const headHeight = (width: number) => (isWide(width) ? 70 : 84);

type Line =
  | { type: "row"; row: ScheduleRow }
  | { type: "note"; text: string; testId: string };

function linesOf({ top, bottom, omitted, extra }: ScheduleSubset): Line[] {
  const lines: Line[] = top.map((row) => ({ type: "row", row }));
  if (bottom.length) {
    lines.push({ type: "note", text: `${omitted} teams not shown`, testId: "schedule-omitted" });
    lines.push(...bottom.map((row): Line => ({ type: "row", row })));
  }
  if (extra) {
    lines.push({ type: "note", text: `Highlighted: ${extra.position} of ${extra.total}`, testId: "schedule-extra-divider" });
    lines.push({ type: "row", row: extra.row });
  }
  return lines;
}

/** ViewBox height of the chart drawing `subset` at viewBox `width`. */
export function scheduleChartHeight(subset: ScheduleSubset, width: number): number {
  return headHeight(width) + linesOf(subset).length * ROW + FOOT;
}

/**
 * Dumbbell rows from venue-neutral (hollow dot) to opponent-adjusted (filled dot) PPA/play,
 * one per team, with the schedule effect printed at the right.
 */
export function ScheduleAdjustmentChart({
  subset,
  domain,
  invert,
  axisLabel,
  highlight,
  onToggleHighlight,
  describe,
  width,
  interactive = true,
  label,
}: ScheduleAdjustmentChartProps) {
  const lines = linesOf(subset);
  const height = scheduleChartHeight(subset, width);
  const wide = isWide(width);
  const nameWidth = wide ? 190 : 84;
  const valueWidth = wide ? 72 : 52;
  const plot = { left: nameWidth, right: width - valueWidth, top: headHeight(width), bottom: height - FOOT };
  const fraction = (value: number) => (value - domain[0]) / (domain[1] - domain[0]);
  const sx = (value: number) => plot.left + (invert ? 1 - fraction(value) : fraction(value)) * (plot.right - plot.left);
  const rowY = (index: number) => plot.top + ROW * (index + 0.5);
  const ticks = niceTicks(domain[0], domain[1], wide ? 6 : 4);

  const keys = lines.flatMap((line) => (line.type === "row" ? [line.row.team] : []));
  const { selected, register, handlers } = useChartSelection(keys);
  const tipIndex = interactive && selected ? lines.findIndex((line) => line.type === "row" && line.row.team === selected) : -1;
  const tipLine = tipIndex >= 0 ? lines[tipIndex] : undefined;
  const tipRow = tipLine?.type === "row" ? tipLine.row : undefined;

  return (
    <div className="relative" data-testid="schedule-chart" data-domain={domain.join(",")} data-inverted={invert ? "true" : "false"}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="group" aria-label={label} className="block h-auto w-full select-none">
        <g fontSize={12} fill="var(--ink-muted)" data-testid="schedule-legend" pointerEvents="none">
          <circle cx={(wide ? plot.left : 8) + 6} cy={14} r={4.5} fill="var(--surface-card)" stroke="var(--ink-muted)" strokeWidth={1.5} />
          <text x={(wide ? plot.left : 8) + 16} y={14} dominantBaseline="central">Venue-neutral</text>
          <circle cx={(wide ? plot.left : 8) + 118} cy={14} r={5} fill="var(--accent)" />
          <text x={(wide ? plot.left : 8) + 128} y={14} dominantBaseline="central">Opponent-adjusted</text>
          {wide ? (
            <text x={plot.left} y={34} fontSize={11} fill="var(--ink-faint)">
              Filled dot right of hollow: raw understated: tougher opponents than average. Left: raw inflated: weaker opponents.
            </text>
          ) : (
            <text x={8} y={34} fontSize={10} fill="var(--ink-faint)">
              <tspan x={8}>Filled dot right of hollow: raw understated: tougher opponents than average.</tspan>
              <tspan x={8} dy={13}>Left: raw inflated: weaker opponents.</tspan>
            </text>
          )}
        </g>
        <text x={width - 8} y={plot.top - 10} textAnchor="end" fontSize={11} fontWeight={600} fill="var(--ink-muted)">
          Effect
        </text>
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={sx(tick)} x2={sx(tick)} y1={plot.top} y2={plot.bottom} stroke="var(--line)" strokeWidth={0.6} />
            <text x={sx(tick)} y={plot.top - 10} textAnchor="middle" fontSize={11} fill="var(--ink-muted)">
              {formatEpaTick(tick)}
            </text>
          </g>
        ))}
        <text x={(plot.left + plot.right) / 2} y={height - 10} textAnchor="middle" fontSize={13} fontWeight={600} fill="var(--ink)" data-testid="schedule-axis-label">
          {axisLabel}
        </text>
        {lines.map((line, index) => {
          const y = rowY(index);
          if (line.type === "note") {
            return (
              <g key={line.testId} data-testid={line.testId} pointerEvents="none">
                <line x1={8} x2={width - 8} y1={y} y2={y} stroke="var(--line-strong)" strokeDasharray="4 4" />
                <text x={width / 2} y={y} textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={600} fill="var(--ink-muted)" stroke="var(--surface-card)" strokeWidth={4} paintOrder="stroke">
                  {line.text}
                </text>
              </g>
            );
          }
          const { row } = line;
          const searched = row.team === highlight;
          const from = sx(row.neutral);
          const to = sx(row.adjusted);
          return (
            <g
              key={row.team}
              ref={register(row.team)}
              role={interactive ? "button" : "img"}
              aria-pressed={interactive ? searched : undefined}
              aria-label={describe(row)}
              tabIndex={interactive ? 0 : undefined}
              data-team={row.team}
              data-state={searched ? "searched" : "active"}
              className="outline-none [&:focus-visible>rect.focus-ring]:opacity-100"
              {...(interactive ? handlers(row.team) : {})}
              onClick={interactive ? () => { handlers(row.team).onClick(); onToggleHighlight(row.team); } : undefined}
              onKeyDown={interactive ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onToggleHighlight(row.team);
                } else handlers(row.team).onKeyDown(event);
              } : undefined}
            >
              {/* Full-row hit target. */}
              <rect x={0} y={y - ROW / 2} width={width} height={ROW} fill="transparent" />
              {interactive && <rect className="focus-ring opacity-0" x={1} y={y - ROW / 2 + 1} width={width - 2} height={ROW - 2} rx={4} fill="none" stroke="var(--accent)" strokeWidth={2} />}
              {searched && <rect x={1} y={y - ROW / 2 + 1} width={width - 2} height={ROW - 2} rx={4} fill="var(--accent-soft)" opacity={0.7} />}
              <TeamMark team={row.team} cx={14} cy={y} size={18} />
              <text x={28} y={y} dominantBaseline="central" fontSize={12} fontWeight={searched ? 700 : 400} fill="var(--ink)">
                {wide ? row.team : teamAbbr(row.team)}
              </text>
              <line x1={from} x2={to} y1={y} y2={y} stroke="var(--ink-faint)" strokeWidth={2} />
              <circle cx={from} cy={y} r={4.5} fill="var(--surface-card)" stroke="var(--ink-muted)" strokeWidth={1.5} />
              <circle cx={to} cy={y} r={5} fill="var(--accent)" stroke="var(--surface-card)" strokeWidth={1.5} />
              <text x={width - 8} y={y} textAnchor="end" dominantBaseline="central" fontSize={12} fill="var(--ink-muted)" className="tabular-nums">
                {formatEpa(row.effect)}
              </text>
            </g>
          );
        })}
      </svg>
      {tipRow && (
        <div
          role="status"
          data-testid="chart-tooltip"
          className="pointer-events-none absolute z-10 max-w-72 rounded-lg border border-line bg-surface-card px-2.5 py-1.5 text-xs leading-snug text-ink shadow-md"
          style={{
            left: `${(sx(tipRow.adjusted) / width) * 100}%`,
            top: `${(rowY(tipIndex) / height) * 100}%`,
            transform: `translate(${sx(tipRow.adjusted) > width * 0.55 ? "-105%" : "12px"}, ${rowY(tipIndex) > height * 0.6 ? "-105%" : "10px"})`,
          }}
        >
          {describe(tipRow)}
        </div>
      )}
    </div>
  );
}
