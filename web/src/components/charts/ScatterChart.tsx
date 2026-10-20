"use client";

import type { CornerCaptions } from "@/lib/chart-config";
import { leastCrowdedSpot, niceTicks, type Box, type Domain, type ScatterPoint } from "@/lib/charts";
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
  /** Names of the two average lines ("Avg offense"), printed with their values. */
  averageNames?: { x: string; y: string };
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
const HOVER_SIZE = 38;
const DIRECTION_CAPTION = "Up and right is better ↗";
const GRID_OPACITY = 0.55;
/** Marks other than the hovered or focused one fade to this opacity. */
const FADED_OPACITY = 0.22;

const CORNERS = [
  { key: "topLeft", left: true, top: true },
  { key: "topRight", left: false, top: true },
  { key: "bottomLeft", left: true, top: false },
  { key: "bottomRight", left: false, top: false },
] as const;

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
  averageNames = { x: "FBS avg", y: "FBS avg" },
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
  // Hovering or focusing a team fades every other mark; a larger copy is drawn on top
  // below (not a DOM reorder, which would fire a spurious mouse-leave).
  const isolating = tip !== undefined;

  // The two average labels go where the fewest logos (and corner names) are.
  const labels = average ? placeAverageLabels({
    average,
    names: averageNames,
    formatX,
    formatY,
    sx,
    sy,
    plot,
    points,
    cornerNames: cornerCaptions?.names,
  }) : null;

  return (
    <div className="relative" data-testid="scatter-chart" data-x-domain={xd.join(",")} data-y-domain={yd.join(",")}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="group" aria-label={label} className="block h-auto w-full select-none">
        <rect x={plot.left} y={plot.top} width={plot.right - plot.left} height={plot.bottom - plot.top} fill="var(--surface-card)" stroke="var(--line)" />
        {niceTicks(xd[0], xd[1], 6).map((tick, index) => (
          <g key={`x${tick}`}>
            {/* Every other vertical line, and fainter than the axis, so the marks carry the picture. */}
            {index % 2 === 0 && <line x1={sx(tick)} x2={sx(tick)} y1={plot.top} y2={plot.bottom} stroke="var(--line)" strokeWidth={0.5} opacity={GRID_OPACITY} data-grid="x" />}
            <text x={sx(tick)} y={plot.bottom + 18} textAnchor="middle" fontSize={12} fill="var(--ink-muted)">
              {formatX(tick)}
            </text>
          </g>
        ))}
        {niceTicks(yd[0], yd[1], 6).map((tick) => (
          <g key={`y${tick}`}>
            <line x1={plot.left} x2={plot.right} y1={sy(tick)} y2={sy(tick)} stroke="var(--line)" strokeWidth={0.5} opacity={GRID_OPACITY} data-grid="y" />
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
        {labels && (
          <g fontSize={11} fontWeight={600} fill="var(--ink-muted)" stroke="var(--surface-card)" strokeWidth={3} paintOrder="stroke" pointerEvents="none" data-testid="average-labels">
            {[labels.x, labels.y].map((label) => (
              <text key={label.text} x={label.x} y={label.baseline} textAnchor={label.anchor}>{label.text}</text>
            ))}
          </g>
        )}
        {average && cornerCaptions && (
          <g data-testid="corner-labels" pointerEvents="none">
            {CORNERS.map(({ key, left, top }) => (
              <g key={key} data-corner={key}>
                {/* The precise meaning stays available to assistive technology. */}
                <title>{cornerCaptions[key]}</title>
                <text
                  x={left ? plot.left + 10 : plot.right - 10}
                  y={top ? plot.top + 20 : plot.bottom - 10}
                  textAnchor={left ? "start" : "end"}
                  fontSize={13}
                  fontWeight={700}
                  fill="var(--ink-muted)"
                >
                  {cornerCaptions.names[key]}
                </text>
              </g>
            ))}
          </g>
        )}
        <text x={(plot.left + plot.right) / 2} y={height - 10} textAnchor="middle" fontSize={14} fontWeight={600} fill="var(--ink)">
          {xLabel}
        </text>
        <text transform={`translate(14 ${(plot.top + plot.bottom) / 2}) rotate(-90)`} textAnchor="middle" fontSize={14} fontWeight={600} fill="var(--ink)">
          {yLabel}
        </text>
        {/* Every scatter is drawn so up and right is the good end (defense axes are inverted). */}
        {(plot.right - plot.left) / 2 - (xLabel.length * 8) / 2 > DIRECTION_CAPTION.length * 6 + 12 && (
          <text x={plot.right} y={height - 10} textAnchor="end" fontSize={11} fill="var(--ink-muted)" pointerEvents="none" data-testid="direction-caption">
            {DIRECTION_CAPTION}
          </text>
        )}
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
              opacity={state === "dim" ? 0.15 : isolating && p.team !== selected ? (state === "searched" ? 0.6 : FADED_OPACITY) : 1}
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
        {tip && stateOf(tip) !== "dim" && (
          <g pointerEvents="none" data-testid="hover-mark" data-hover-team={tip.team}>
            <circle cx={sx(tip.x)} cy={sy(tip.y)} r={Math.max(HOVER_SIZE, stateOf(tip) === "searched" ? SEARCHED_SIZE : 0) / 2 + 3} fill="var(--surface-card)" stroke="var(--accent)" strokeWidth={2} />
            <TeamMark team={tip.team} cx={sx(tip.x)} cy={sy(tip.y)} size={Math.max(HOVER_SIZE, stateOf(tip) === "searched" ? SEARCHED_SIZE : 0)} />
          </g>
        )}
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

type LabelSpot = { text: string; x: number; baseline: number; anchor: "start" | "end" };

const LABEL_CHAR = 6.3;
const LABEL_HEIGHT = 14;

/**
 * Where the two average-line labels sit: for each, the least crowded of a few spots along
 * its line (line ends first, then further in), so it stays clear of logos and corner names
 * in any week or filter. The vertical label is placed first and then counts as an obstacle.
 */
function placeAverageLabels({ average, names, formatX, formatY, sx, sy, plot, points, cornerNames }: {
  average: { x: number; y: number };
  names: { x: string; y: string };
  formatX: (value: number) => string;
  formatY: (value: number) => string;
  sx: (value: number) => number;
  sy: (value: number) => number;
  plot: { left: number; right: number; top: number; bottom: number };
  points: readonly ScatterPoint[];
  cornerNames?: CornerCaptions["names"];
}): { x: LabelSpot; y: LabelSpot } {
  const bounds: Box = { x: plot.left, y: plot.top, w: plot.right - plot.left, h: plot.bottom - plot.top };
  const obstacles: Box[] = points.map((p) => ({ x: sx(p.x) - BASE_SIZE / 2, y: sy(p.y) - BASE_SIZE / 2, w: BASE_SIZE, h: BASE_SIZE }));
  if (cornerNames) {
    const width = (text: string) => text.length * 8;
    obstacles.push(
      { x: plot.left + 10, y: plot.top + 6, w: width(cornerNames.topLeft), h: 18 },
      { x: plot.right - 10 - width(cornerNames.topRight), y: plot.top + 6, w: width(cornerNames.topRight), h: 18 },
      { x: plot.left + 10, y: plot.bottom - 24, w: width(cornerNames.bottomLeft), h: 18 },
      { x: plot.right - 10 - width(cornerNames.bottomRight), y: plot.bottom - 24, w: width(cornerNames.bottomRight), h: 18 },
    );
  }
  const spotBox = (spot: LabelSpot): Box => {
    const w = spot.text.length * LABEL_CHAR;
    return { x: spot.anchor === "end" ? spot.x - w : spot.x, y: spot.baseline - 11, w, h: LABEL_HEIGHT };
  };
  const choose = (spots: LabelSpot[]): LabelSpot => spots[leastCrowdedSpot(spots.map(spotBox), obstacles, bounds)];

  const lineX = sx(average.x);
  const textX = `${names.x} ${formatX(average.x)}`;
  const height = plot.bottom - plot.top;
  const verticalSpots: LabelSpot[] = [0.0, 1.0, 0.3, 0.7].flatMap((fraction) => {
    const baseline = fraction === 0 ? plot.top + 14 : fraction === 1 ? plot.bottom - 8 : plot.top + height * fraction;
    return [
      { text: textX, x: lineX + 6, baseline, anchor: "start" as const },
      { text: textX, x: lineX - 6, baseline, anchor: "end" as const },
    ];
  });
  const vertical = choose(verticalSpots);
  obstacles.push(spotBox(vertical));

  const lineY = sy(average.y);
  const textY = `${names.y} ${formatY(average.y)}`;
  const width = plot.right - plot.left;
  const horizontalSpots: LabelSpot[] = [
    { x: plot.right - 6, anchor: "end" as const },
    { x: plot.left + 6, anchor: "start" as const },
    { x: plot.left + width * 0.7, anchor: "end" as const },
    { x: plot.left + width * 0.3, anchor: "start" as const },
  ].flatMap((spot) => [
    { text: textY, ...spot, baseline: lineY - 6 },
    { text: textY, ...spot, baseline: lineY + 14 },
  ]);
  return { x: vertical, y: choose(horizontalSpots) };
}
