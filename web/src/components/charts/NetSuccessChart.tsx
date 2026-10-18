"use client";

import { chartColor, niceTicks, type NetSuccessBar } from "@/lib/charts";
import { FALLBACK_TEAM_COLOR, teamAltColor, teamColor } from "@/lib/team-logos";
import type { MarkerState } from "./ScatterChart";
import { TeamMark } from "./TeamMark";
import { useChartSelection } from "./useChartSelection";

export type NetSuccessChartProps = {
  bars: readonly NetSuccessBar[];
  stateOf: (bar: NetSuccessBar) => MarkerState;
  describe: (bar: NetSuccessBar) => string;
  /** Vertical bars (default) or horizontal rows for narrow screens. */
  orientation?: "vertical" | "horizontal";
  width: number;
  height: number;
  interactive?: boolean;
  label: string;
};

const LOGO = 26;

function fillFor(bar: NetSuccessBar): string {
  return chartColor(teamColor(bar.winner), teamAltColor(bar.winner), FALLBACK_TEAM_COLOR);
}

/** Smallest symmetric half-range covering every bar, with room for the tip logos. */
function halfRange(bars: readonly NetSuccessBar[]): number {
  return Math.max(0.05, ...bars.map((b) => Math.abs(b.value))) * 1.18;
}

export function NetSuccessChart({
  bars,
  stateOf,
  describe,
  orientation = "vertical",
  width,
  height,
  interactive = true,
  label,
}: NetSuccessChartProps) {
  const ordered = bars.filter((b) => stateOf(b) !== "dim").map((b) => String(b.gameId));
  const { selected, register, handlers } = useChartSelection(ordered);
  const half = halfRange(bars);
  const tipBar = interactive && selected ? bars.find((b) => String(b.gameId) === selected) : undefined;
  const horizontal = orientation === "horizontal";

  const margin = horizontal ? { top: 22, right: 34, bottom: 22, left: 76 } : { top: 10, right: 12, bottom: 78, left: 56 };
  const plot = { left: margin.left, right: width - margin.right, top: margin.top, bottom: height - margin.bottom };
  const span = horizontal ? plot.right - plot.left : plot.bottom - plot.top;
  const along = (value: number) =>
    horizontal ? plot.left + ((value + half) / (2 * half)) * span : plot.bottom - ((value + half) / (2 * half)) * span;
  const count = Math.max(1, bars.length);
  const band = (horizontal ? plot.bottom - plot.top : plot.right - plot.left) / count;
  const thick = Math.max(2, Math.min(horizontal ? 18 : 34, band * 0.64));
  const logo = Math.max(10, Math.min(LOGO, horizontal ? band * 0.9 : band * 0.95));
  const ticks = niceTicks(-half, half, 8);
  const zero = along(0);
  // Dense slates (about 50+ games) read best as upright columns sized to the band.
  const verticalLabels = band < 20;
  const labelSize = verticalLabels ? Math.max(8, Math.min(11, band * 0.72)) : Math.min(12, band * 0.5);

  function center(index: number): number {
    return (horizontal ? plot.top : plot.left) + band * (index + 0.5);
  }

  function tooltipPosition(bar: NetSuccessBar) {
    const index = bars.indexOf(bar);
    const x = horizontal ? along(bar.value) : center(index);
    const y = horizontal ? center(index) : along(bar.value);
    return {
      left: `${(x / width) * 100}%`,
      top: `${(y / height) * 100}%`,
      transform: `translate(${x > width * 0.6 ? "-105%" : "12px"}, ${y > height * 0.65 ? "-105%" : "8px"})`,
    };
  }

  return (
    <div className="relative" data-testid="net-success-chart" data-orientation={orientation}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="group" aria-label={label} className="block h-auto w-full select-none">
        <rect x={plot.left} y={plot.top} width={plot.right - plot.left} height={plot.bottom - plot.top} fill="var(--surface-card)" stroke="var(--line)" />
        {/* Below zero the winner had the lower success rate. */}
        <g data-testid="outplayed-band" pointerEvents="none">
          {horizontal ? (
            <rect x={plot.left} y={plot.top} width={zero - plot.left} height={plot.bottom - plot.top} fill="var(--surface-inset)" />
          ) : (
            <rect x={plot.left} y={zero} width={plot.right - plot.left} height={plot.bottom - zero} fill="var(--surface-inset)" />
          )}
        </g>
        {ticks.map((tick) => (
          <g key={tick}>
            {horizontal ? (
              <>
                <line x1={along(tick)} x2={along(tick)} y1={plot.top} y2={plot.bottom} stroke="var(--line)" strokeWidth={0.6} />
                <text x={along(tick)} y={plot.top - 8} textAnchor="middle" fontSize={11} fill="var(--ink-muted)">
                  {(tick * 100).toFixed(0)}
                </text>
              </>
            ) : (
              <>
                <line x1={plot.left} x2={plot.right} y1={along(tick)} y2={along(tick)} stroke="var(--line)" strokeWidth={0.6} />
                <text x={plot.left - 8} y={along(tick)} textAnchor="end" dominantBaseline="central" fontSize={12} fill="var(--ink-muted)">
                  {(tick * 100).toFixed(0)}
                </text>
              </>
            )}
          </g>
        ))}
        {horizontal ? (
          <line x1={zero} x2={zero} y1={plot.top} y2={plot.bottom} stroke="var(--ink-muted)" strokeWidth={1.2} />
        ) : (
          <line x1={plot.left} x2={plot.right} y1={zero} y2={zero} stroke="var(--ink-muted)" strokeWidth={1.2} />
        )}
        {!horizontal && (
          <text transform={`translate(14 ${(plot.top + plot.bottom) / 2}) rotate(-90)`} textAnchor="middle" fontSize={13} fontWeight={600} fill="var(--ink)">
            Net success rate (pct)
          </text>
        )}
        {horizontal && (
          <text x={(plot.left + plot.right) / 2} y={height - 4} textAnchor="middle" fontSize={11} fontWeight={600} fill="var(--ink)">
            Net success rate (pct)
          </text>
        )}
        {bars.map((bar, index) => {
          const state = stateOf(bar);
          const focusable = interactive && state !== "dim";
          const c = center(index);
          const tip = along(bar.value);
          // Keep the winner beyond the bar tip and the loser just across the zero axis.
          const outward = bar.value >= 0 ? 1 : -1;
          const gap = logo * 0.6;
          const loserGap = logo / 2 + 6;
          const winnerAt = horizontal ? { cx: tip + outward * gap, cy: c } : { cx: c, cy: tip - outward * gap };
          const loserAt = horizontal ? { cx: zero - outward * loserGap, cy: c } : { cx: c, cy: zero + outward * loserGap };
          const key = String(bar.gameId);
          return (
            <g
              key={key}
              ref={register(key)}
              role="img"
              aria-label={describe(bar)}
              aria-hidden={state === "dim" ? true : undefined}
              tabIndex={focusable ? 0 : undefined}
              opacity={state === "dim" ? 0.15 : 1}
              data-game={bar.gameId}
              data-state={state}
              className="outline-none [&:focus-visible>rect.focus-ring]:opacity-100"
              {...(focusable ? handlers(key) : {})}
            >
              {interactive && (
                <rect
                  className="focus-ring opacity-0"
                  x={horizontal ? plot.left : c - band / 2}
                  y={horizontal ? c - band / 2 : plot.top}
                  width={horizontal ? plot.right - plot.left : band}
                  height={horizontal ? band : plot.bottom - plot.top}
                  fill="none"
                  stroke="var(--accent)"
                  strokeWidth={2}
                />
              )}
              {state === "searched" && (
                <rect
                  x={horizontal ? plot.left : c - band / 2}
                  y={horizontal ? c - band / 2 : plot.top}
                  width={horizontal ? plot.right - plot.left : band}
                  height={horizontal ? band : plot.bottom - plot.top}
                  fill="var(--accent-soft)"
                  opacity={0.6}
                />
              )}
              {bar.value === 0 ? (
                horizontal ? (
                  <line x1={zero} x2={zero} y1={c - thick / 2} y2={c + thick / 2} stroke={fillFor(bar)} strokeWidth={2} data-hairline />
                ) : (
                  <line x1={c - thick / 2} x2={c + thick / 2} y1={zero} y2={zero} stroke={fillFor(bar)} strokeWidth={2} data-hairline />
                )
              ) : horizontal ? (
                <rect x={Math.min(zero, tip)} y={c - thick / 2} width={Math.abs(tip - zero)} height={thick} fill={fillFor(bar)} />
              ) : (
                <rect x={c - thick / 2} y={Math.min(zero, tip)} width={thick} height={Math.abs(tip - zero)} fill={fillFor(bar)} />
              )}
              <TeamMark team={bar.winner} cx={winnerAt.cx} cy={winnerAt.cy} size={logo} />
              <TeamMark team={bar.loser} cx={loserAt.cx} cy={loserAt.cy} size={logo} />
              {horizontal ? (
                <text x={plot.left - 6} y={c} textAnchor="end" dominantBaseline="central" fontSize={Math.min(11, band * 0.7)} fill="var(--ink)">
                  {bar.label}
                </text>
              ) : (
                <text
                  transform={`translate(${c} ${plot.bottom + 8}) rotate(${verticalLabels ? -90 : -45})`}
                  textAnchor="end"
                  dominantBaseline={verticalLabels ? "central" : undefined}
                  fontSize={labelSize}
                  fill="var(--ink)"
                >
                  {bar.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {tipBar && (
        <div
          role="status"
          data-testid="chart-tooltip"
          className="pointer-events-none absolute z-10 max-w-64 rounded-lg border border-line bg-surface-card px-2.5 py-1.5 text-xs leading-snug text-ink shadow-md"
          style={tooltipPosition(tipBar)}
        >
          {describe(tipBar)}
        </div>
      )}
    </div>
  );
}
