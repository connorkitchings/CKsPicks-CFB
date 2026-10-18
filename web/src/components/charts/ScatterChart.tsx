"use client";

import type { CornerCaptions } from "@/lib/chart-config";
import { niceTicks, type Domain, type ScatterPoint } from "@/lib/charts";
import { TeamMark } from "./TeamMark";
import { useChartSelection } from "./useChartSelection";

export type MarkerState = "active" | "dim" | "searched";

export type ScatterChartProps = {
  points: readonly ScatterPoint[];
  xDomain: Domain;
  yDomain: Domain;
  onToggleHighlight: (team: string) => void;
  average: { x: number; y: number } | null;
  invertX: boolean;
  invertY: boolean;
  xLabel: string;
  yLabel: string;
  /** ViewBox size; the SVG scales to its container. */
  width: number;
  height: number;
  /** Quadrant captions, drawn with the average lines; none when omitted. */
  cornerCaptions?: CornerCaptions;
  stateOf: (point: ScatterPoint) => MarkerState;
  /** Accessible and tooltip text of one point. */
  describe: (point: ScatterPoint) => string;
  formatX: (value: number) => string;
  formatY: (value: number) => string;
  /** False in the static export card: no focus stops or tooltips. */
  interactive?: boolean;
  label: string;
};

const MARGIN = { top: 18, right: 22, bottom: 52, left: 84 };
const BASE_SIZE = 26;
const SEARCHED_SIZE = 44;

function rank(state: MarkerState): number {
  return state === "dim" ? 0 : state === "active" ? 1 : 2;
}

export function ScatterChart({
  points,
  xDomain,
  yDomain,
  onToggleHighlight,
  average,
  invertX,
  invertY,
  xLabel,
  yLabel,
  width,
  height,
  cornerCaptions,
  stateOf,
  describe,
  formatX,
  formatY,
  interactive = true,
  label,
}: ScatterChartProps) {
  const plot = { left: MARGIN.left, right: width - MARGIN.right, top: MARGIN.top, bottom: height - MARGIN.bottom };
  const xd = xDomain;
  const yd = yDomain;
  const fraction = (value: number, domain: Domain) => (value - domain[0]) / (domain[1] - domain[0]);
  const sx = (v: number) => plot.left + (invertX ? 1 - fraction(v, xd) : fraction(v, xd)) * (plot.right - plot.left);
  const sy = (v: number) => plot.top + (invertY ? fraction(v, yd) : 1 - fraction(v, yd)) * (plot.bottom - plot.top);

  const ordered = points.filter((p) => stateOf(p) !== "dim").map((p) => p.team);
  const { selected, register, handlers } = useChartSelection(ordered);
  // Dimmed first, then active, then the searched team on top.
  const drawOrder = [...points].sort((a, b) => rank(stateOf(a)) - rank(stateOf(b)));
  const tip = interactive && selected ? points.find((p) => p.team === selected) : undefined;

  return (
    <div className="relative" data-testid="scatter-chart" data-x-domain={xd.join(",")} data-y-domain={yd.join(",")}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="group" aria-label={label} className="block h-auto w-full select-none">
        <rect x={plot.left} y={plot.top} width={plot.right - plot.left} height={plot.bottom - plot.top} fill="var(--surface-card)" stroke="var(--line)" />
        {niceTicks(xd[0], xd[1], 6).map((tick) => (
          <g key={`x${tick}`}>
            <line x1={sx(tick)} x2={sx(tick)} y1={plot.top} y2={plot.bottom} stroke="var(--line)" strokeWidth={0.6} />
            <text x={sx(tick)} y={plot.bottom + 18} textAnchor="middle" fontSize={12} fill="var(--ink-muted)">
              {formatX(tick)}
            </text>
          </g>
        ))}
        {niceTicks(yd[0], yd[1], 6).map((tick) => (
          <g key={`y${tick}`}>
            <line x1={plot.left} x2={plot.right} y1={sy(tick)} y2={sy(tick)} stroke="var(--line)" strokeWidth={0.6} />
            <text x={plot.left - 8} y={sy(tick)} textAnchor="end" dominantBaseline="central" fontSize={12} fill="var(--ink-muted)">
              {formatY(tick)}
            </text>
          </g>
        ))}
        {average && (
          <g stroke="var(--ink-faint)" strokeDasharray="6 5" strokeWidth={1.1} data-testid="average-lines" data-average-x={average.x} data-average-y={average.y}>
            <line x1={sx(average.x)} x2={sx(average.x)} y1={plot.top} y2={plot.bottom} />
            <line x1={plot.left} x2={plot.right} y1={sy(average.y)} y2={sy(average.y)} />
          </g>
        )}
        {average && cornerCaptions && (
          <g fontSize={12} fontWeight={500} fill="var(--ink-faint)" data-testid="corner-labels" pointerEvents="none">
            <text x={plot.left + 10} y={plot.top + 20}>{cornerCaptions.topLeft}</text>
            <text x={plot.right - 10} y={plot.top + 20} textAnchor="end">{cornerCaptions.topRight}</text>
            <text x={plot.left + 10} y={plot.bottom - 10}>{cornerCaptions.bottomLeft}</text>
            <text x={plot.right - 10} y={plot.bottom - 10} textAnchor="end">{cornerCaptions.bottomRight}</text>
          </g>
        )}
        <text x={(plot.left + plot.right) / 2} y={height - 10} textAnchor="middle" fontSize={14} fontWeight={600} fill="var(--ink)">
          {xLabel}
        </text>
        <text transform={`translate(14 ${(plot.top + plot.bottom) / 2}) rotate(-90)`} textAnchor="middle" fontSize={14} fontWeight={600} fill="var(--ink)">
          {yLabel}
        </text>
        {drawOrder.map((p) => {
          const state = stateOf(p);
          const size = state === "searched" ? SEARCHED_SIZE : BASE_SIZE;
          const cx = sx(p.x);
          const cy = sy(p.y);
          const focusable = interactive && state !== "dim";
          // Keep the persistent name inside the plot, including bottom and side edges.
          const labelHalfWidth = p.team.length * 4;
          const labelX = Math.max(plot.left + labelHalfWidth + 4, Math.min(cx, plot.right - labelHalfWidth - 4));
          const labelY = Math.max(plot.top + 14, Math.min(
            cy + size / 2 + 20 > plot.bottom ? cy - size / 2 - 10 : cy + size / 2 + 16,
            plot.bottom - 8,
          ));
          return (
            <g
              key={p.team}
              ref={register(p.team)}
              role={interactive ? "button" : "img"}
              aria-pressed={interactive ? state === "searched" : undefined}
              aria-label={describe(p)}
              aria-hidden={state === "dim" ? true : undefined}
              tabIndex={focusable ? 0 : undefined}
              opacity={state === "dim" ? 0.15 : 1}
              data-team={p.team}
              data-state={state}
              className="outline-none [&:focus-visible>circle.focus-ring]:opacity-100"
              {...(focusable ? handlers(p.team) : {})}
              onClick={focusable ? () => {
                handlers(p.team).onClick();
                onToggleHighlight(p.team);
              } : undefined}
              onKeyDown={focusable ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onToggleHighlight(p.team);
                } else handlers(p.team).onKeyDown(event);
              } : undefined}
            >
              {interactive && <circle className="focus-ring opacity-0" cx={cx} cy={cy} r={size / 2 + 3} fill="none" stroke="var(--accent)" strokeWidth={2.5} />}
              {state === "searched" && <circle cx={cx} cy={cy} r={size / 2 + 3} fill="var(--accent-soft)" stroke="var(--accent)" strokeWidth={2.5} />}
              <TeamMark team={p.team} cx={cx} cy={cy} size={size} />
              {state === "searched" && <text x={labelX} y={labelY} textAnchor="middle" data-testid="highlight-label" fontSize={13} fontWeight={700} fill="var(--ink)" stroke="var(--surface-card)" strokeWidth={3} paintOrder="stroke">{p.team}</text>}
            </g>
          );
        })}
      </svg>
      {tip && (
        <div
          role="status"
          data-testid="chart-tooltip"
          className="pointer-events-none absolute z-10 max-w-72 rounded-lg border border-line bg-surface-card px-2.5 py-1.5 text-xs leading-snug text-ink shadow-md"
          style={{
            left: `${(sx(tip.x) / width) * 100}%`,
            top: `${(sy(tip.y) / height) * 100}%`,
            transform: `translate(${sx(tip.x) > width * 0.6 ? "-105%" : "12px"}, ${sy(tip.y) > height * 0.65 ? "-105%" : "8px"})`,
          }}
        >
          {describe(tip)}
        </div>
      )}
    </div>
  );
}
