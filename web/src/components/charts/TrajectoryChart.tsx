"use client";

import { chartColor, niceTicks, type Domain, type TrajectoryData, type TrajectoryPoint, type TrajectorySeries } from "@/lib/charts";
import { layoutTrajectoryEndpoints } from "@/lib/chart-trajectory-layout";
import { FALLBACK_TEAM_COLOR, teamAltColor, teamColor } from "@/lib/team-logos";
import { TeamMark } from "./TeamMark";
import { useChartSelection } from "./useChartSelection";

/** "context": faint gray; "group": in the conference filter (team color, end logo); "highlight": bold and labeled. */
export type TrajectoryState = "context" | "group" | "highlight";

export type TrajectoryChartProps = {
  data: TrajectoryData;
  yDomain: Domain;
  stateOf: (series: TrajectorySeries) => TrajectoryState;
  onToggleHighlight: (team: string) => void;
  describe: (series: TrajectorySeries) => string;
  formatY: (value: number) => string;
  yLabel: string;
  /** ViewBox size; the SVG scales to its container. */
  width: number;
  height: number;
  /** False in the static export card: no focus stops or tooltips. */
  interactive?: boolean;
  label: string;
};

const MARGIN = { top: 18, right: 64, bottom: 52, left: 84 };
const STROKE: Record<TrajectoryState, number> = { context: 1, group: 2, highlight: 3.5 };
const DOT: Record<TrajectoryState, number> = { context: 2.5, group: 3.5, highlight: 5.5 };
const LOGO: Record<TrajectoryState, number> = { context: 0, group: 20, highlight: 30 };
const ORDER: Record<TrajectoryState, number> = { context: 0, group: 1, highlight: 2 };

function colorOf(team: string, state: TrajectoryState): string {
  return state === "context" ? "var(--ink-faint)" : chartColor(teamColor(team), teamAltColor(team), FALLBACK_TEAM_COLOR);
}

function lastPoint(series: TrajectorySeries): TrajectoryPoint {
  const segment = series.segments[series.segments.length - 1];
  return segment[segment.length - 1];
}

export function TrajectoryChart({
  data,
  yDomain,
  stateOf,
  onToggleHighlight,
  describe,
  formatY,
  yLabel,
  width,
  height,
  interactive = true,
  label,
}: TrajectoryChartProps) {
  const plot = { left: MARGIN.left, right: width - MARGIN.right, top: MARGIN.top, bottom: height - MARGIN.bottom };
  const { weeks, series, average, invertY } = data;
  const first = weeks[0] ?? 0;
  const last = weeks[weeks.length - 1] ?? 0;
  const inset = 18;
  const sx = (week: number) =>
    first === last ? (plot.left + plot.right) / 2 : plot.left + inset + ((week - first) / (last - first)) * (plot.right - plot.left - 2 * inset);
  const fraction = (value: number) => (value - yDomain[0]) / (yDomain[1] - yDomain[0]);
  const sy = (value: number) => plot.top + (invertY ? fraction(value) : 1 - fraction(value)) * (plot.bottom - plot.top);
  const path = (points: readonly TrajectoryPoint[]) => points.map((p, i) => `${i ? "L" : "M"}${sx(p.week)},${sy(p.value)}`).join("");

  const { selected, register, handlers } = useChartSelection(series.map((s) => s.team));
  const drawOrder = [...series].sort((a, b) => ORDER[stateOf(a)] - ORDER[stateOf(b)]);
  const endpoints = layoutTrajectoryEndpoints(
    series.filter((s) => LOGO[stateOf(s)] > 0).map((s) => ({ team: s.team, y: sy(lastPoint(s).value), size: LOGO[stateOf(s)] })),
    plot.top,
    plot.bottom,
  );
  const logoX = plot.right + 24;
  const tip = interactive && selected ? series.find((s) => s.team === selected) : undefined;
  const tipEnd = tip ? lastPoint(tip) : null;

  // The average is never interpolated across a window without one.
  const averageRuns: TrajectoryPoint[][] = [];
  average.forEach((value, index) => {
    if (value === null) averageRuns.push([]);
    else {
      if (!averageRuns.length) averageRuns.push([]);
      averageRuns[averageRuns.length - 1].push({ week: weeks[index], value });
    }
  });
  const averageEnd = [...averageRuns].reverse().find((run) => run.length)?.at(-1);

  return (
    <div className="relative" data-testid="trajectory-chart" data-y-domain={yDomain.join(",")} data-invert-y={invertY}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="group" aria-label={label} className="block h-auto w-full select-none">
        <rect x={plot.left} y={plot.top} width={plot.right - plot.left} height={plot.bottom - plot.top} fill="var(--surface-card)" stroke="var(--line)" />
        {weeks.map((week) => (
          <g key={`x${week}`}>
            <line x1={sx(week)} x2={sx(week)} y1={plot.top} y2={plot.bottom} stroke="var(--line)" strokeWidth={0.6} />
            <text x={sx(week)} y={plot.bottom + 18} textAnchor="middle" fontSize={12} fill="var(--ink-muted)">
              {week}
            </text>
          </g>
        ))}
        {niceTicks(yDomain[0], yDomain[1], 6).map((tick) => (
          <g key={`y${tick}`}>
            <line x1={plot.left} x2={plot.right} y1={sy(tick)} y2={sy(tick)} stroke="var(--line)" strokeWidth={0.6} />
            <text x={plot.left - 8} y={sy(tick)} textAnchor="end" dominantBaseline="central" fontSize={12} fill="var(--ink-muted)">
              {formatY(tick)}
            </text>
          </g>
        ))}
        <text x={(plot.left + plot.right) / 2} y={height - 10} textAnchor="middle" fontSize={14} fontWeight={600} fill="var(--ink)">
          Through Week
        </text>
        <text transform={`translate(14 ${(plot.top + plot.bottom) / 2}) rotate(-90)`} textAnchor="middle" fontSize={14} fontWeight={600} fill="var(--ink)">
          {yLabel}
        </text>

        {drawOrder.map((s) => {
          const state = stateOf(s);
          const color = colorOf(s.team, state);
          const end = lastPoint(s);
          const ex = sx(end.week);
          const ey = sy(end.value);
          const endpoint = endpoints.get(s.team);
          return (
            <g
              key={s.team}
              ref={register(s.team)}
              role={interactive ? "button" : "img"}
              aria-pressed={interactive ? state === "highlight" : undefined}
              aria-label={describe(s)}
              tabIndex={interactive ? 0 : undefined}
              data-team={s.team}
              data-state={state}
              className="outline-none [&:focus-visible>circle.focus-ring]:opacity-100"
              {...(interactive ? handlers(s.team) : {})}
              onClick={interactive ? () => { handlers(s.team).onClick(); onToggleHighlight(s.team); } : undefined}
              onKeyDown={interactive ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onToggleHighlight(s.team);
                } else handlers(s.team).onKeyDown(event);
              } : undefined}
            >
              {s.segments.map((segment) =>
                segment.length === 1 ? (
                  <circle
                    key={segment[0].week}
                    cx={sx(segment[0].week)}
                    cy={sy(segment[0].value)}
                    r={DOT[state]}
                    fill={color}
                    stroke="var(--surface-card)"
                    strokeWidth={state === "context" ? 0 : 2}
                    opacity={state === "context" ? 0.45 : 1}
                    data-testid="trajectory-dot"
                    data-week={segment[0].week}
                  />
                ) : (
                  <g key={segment[0].week}>
                    {state !== "context" && <path d={path(segment)} fill="none" stroke="var(--surface-card)" strokeWidth={STROKE[state] + 2} strokeLinejoin="round" strokeLinecap="round" />}
                    <path
                      d={path(segment)}
                      fill="none"
                      stroke={color}
                      strokeWidth={STROKE[state]}
                      strokeLinejoin="round"
                      strokeLinecap="round"
                      opacity={state === "context" ? 0.35 : 1}
                      data-testid="trajectory-line"
                      data-weeks={segment.map((p) => p.week).join(",")}
                    />
                    {interactive && <path d={path(segment)} fill="none" stroke="transparent" strokeWidth={10} />}
                  </g>
                ),
              )}
              {interactive && <circle className="focus-ring opacity-0" cx={ex} cy={ey} r={8} fill="none" stroke="var(--accent)" strokeWidth={2.5} />}
              {endpoint && (
                <g data-testid="trajectory-endpoint" data-y={endpoint.y} data-size={endpoint.size}>
                  <path d={`M${ex},${ey}L${plot.right + 3},${ey}L${logoX - endpoint.size / 2 - 3},${endpoint.y}`} fill="none" stroke={color} strokeWidth={1} opacity={0.7} />
                  <TeamMark team={s.team} cx={logoX} cy={endpoint.y} size={endpoint.size} />
                </g>
              )}
              {state === "highlight" && endpoint && (
                <text
                  x={plot.right - 5}
                  y={Math.max(plot.top + 14, Math.min(plot.bottom - 4, endpoint.y - 8))}
                  textAnchor="end"
                  fontSize={13}
                  fontWeight={700}
                  fill="var(--ink)"
                  stroke="var(--surface-card)"
                  strokeWidth={3}
                  paintOrder="stroke"
                  data-testid="highlight-label"
                >
                  {s.team}
                </text>
              )}
            </g>
          );
        })}

        <g data-testid="trajectory-average" data-average={average.map((v) => (v === null ? "" : v)).join(",")} pointerEvents="none">
          {averageRuns.filter((run) => run.length).map((run) =>
            run.length === 1 ? (
              <line key={run[0].week} x1={sx(run[0].week) - 10} x2={sx(run[0].week) + 10} y1={sy(run[0].value)} y2={sy(run[0].value)} stroke="var(--ink-muted)" strokeDasharray="4 3" strokeWidth={1.5} />
            ) : (
              <path key={run[0].week} d={path(run)} fill="none" stroke="var(--ink-muted)" strokeDasharray="6 5" strokeWidth={1.5} />
            ),
          )}
          {averageEnd && (
            <text x={sx(averageEnd.week) - 8} y={sy(averageEnd.value) + 14} textAnchor="end" fontSize={11} fill="var(--ink-muted)" stroke="var(--surface-card)" strokeWidth={3} paintOrder="stroke">
              FBS avg
            </text>
          )}
        </g>
      </svg>
      {tip && tipEnd && (
        <div
          role="status"
          data-testid="chart-tooltip"
          className="pointer-events-none absolute z-10 max-w-80 rounded-lg border border-line bg-surface-card px-2.5 py-1.5 text-xs leading-snug text-ink shadow-md"
          style={{
            left: `${(sx(tipEnd.week) / width) * 100}%`,
            top: `${(sy(tipEnd.value) / height) * 100}%`,
            transform: `translate(${sx(tipEnd.week) > width * 0.6 ? "-105%" : "12px"}, ${sy(tipEnd.value) > height * 0.65 ? "-105%" : "8px"})`,
          }}
        >
          {describe(tip)}
        </div>
      )}
    </div>
  );
}
