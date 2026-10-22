"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import { createPortal } from "react-dom";
import { nearestScatterTeams } from "@/lib/scatter-selection";
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
  highlight?: string | null;
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
  /** Live mobile details live outside the horizontally scrolling plot. */
  detailsContainer?: HTMLElement | null;
};

const EXPORT_MARGIN = { top: 18, right: 22, bottom: 52, left: 84 };
const INTERACTIVE_MARGIN = { top: 20, right: 26, bottom: 56, left: 86 };
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
  highlight,
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
  detailsContainer,
}: ScatterChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [renderedWidth, setRenderedWidth] = useState(interactive ? 760 : width);
  const [choices, setChoices] = useState<string[]>([]);
  const touch = useRef<{ x: number; y: number; pointerId: number; cancelled: boolean } | null>(null);
  const suppressClick = useRef(false);
  useEffect(() => {
    if (!interactive || !svgRef.current) return;
    const observer = new ResizeObserver(([entry]) => setRenderedWidth(entry.contentRect.width));
    observer.observe(svgRef.current);
    const cancel = () => { if (touch.current) touch.current.cancelled = true; };
    document.addEventListener("scroll", cancel, true);
    return () => { observer.disconnect(); document.removeEventListener("scroll", cancel, true); };
  }, [interactive]);
  // Export typography is intentionally untouched. Live labels compensate for base SVG scale.
  const textSize = (size: number) => interactive ? Math.max(size, 12 * width / Math.max(renderedWidth, 1)) : size;
  const labelScale = textSize(11) / 11;
  const margin = interactive ? INTERACTIVE_MARGIN : EXPORT_MARGIN;
  const plot = { left: margin.left, right: width - margin.right, top: margin.top, bottom: height - margin.bottom };
  const xd = xDomain;
  const yd = yDomain;
  const fraction = (value: number, domain: Domain) => (value - domain[0]) / (domain[1] - domain[0]);
  const sx = (v: number) => plot.left + (invertX ? 1 - fraction(v, xd) : fraction(v, xd)) * (plot.right - plot.left);
  const sy = (v: number) => plot.top + (invertY ? fraction(v, yd) : 1 - fraction(v, yd)) * (plot.bottom - plot.top);

  const ordered = points.filter((p) => stateOf(p) !== "dim").map((p) => p.team);
  const { selected, setSelected, register, handlers } = useChartSelection(ordered, { manualTouch: true });
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
    labelScale,
  }) : null;

  const selectTeam = (team: string) => {
    setChoices([]);
    setSelected(team);
  };
  const onTouchUp = (event: PointerEvent<SVGSVGElement>) => {
    const start = touch.current;
    touch.current = null;
    if (!start || start.pointerId !== event.pointerId || start.cancelled) return;
    if (Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) return;
    const svg = svgRef.current;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return;
    const candidates = nearestScatterTeams(points.filter((p) => stateOf(p) !== "dim").map((p) => {
      const screen = new DOMPoint(sx(p.x), sy(p.y)).matrixTransform(matrix);
      return { team: p.team, x: screen.x, y: screen.y };
    }), event.clientX, event.clientY);
    if (candidates.length === 1) {
      if (selected === candidates[0]) {
        setSelected(null);
        setChoices([]);
      } else {
        selectTeam(candidates[0]);
      }
    } else {
      setSelected(null);
      setChoices(candidates);
    }
  };
  const validChoices = choices.filter((team) => points.some((p) => p.team === team));
  const isHighlighted = highlight === tip?.team;
  const details = interactive && (tip || validChoices.length > 0) ? (
    <div className="show-on-touch-or-small mt-3 rounded-lg border border-line bg-surface-inset p-3 text-sm leading-relaxed text-ink" data-testid="scatter-details">
      {validChoices.length > 0 ? (
        <>
          <p role="status">Several teams are nearby. Choose a team:</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {validChoices.map((team) => (
              <button key={team} type="button" className="min-h-11 rounded-lg border border-line bg-surface-card px-3 text-ink" onClick={() => selectTeam(team)}>
                {team}
              </button>
            ))}
          </div>
        </>
      ) : (
        <>
          <p role="status">{tip && describe(tip)}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {tip && (
              <button
                type="button"
                className="min-h-11 rounded-lg border border-line bg-surface-card px-3 font-semibold text-ink focus-visible:outline-2 focus-visible:outline-accent"
                onClick={() => onToggleHighlight(tip.team)}
              >
                {isHighlighted ? "Remove highlight" : "Highlight this team"}
              </button>
            )}
            <button
              type="button"
              className="min-h-11 rounded-lg border border-line bg-surface-card px-3 text-ink focus-visible:outline-2 focus-visible:outline-accent"
              onClick={() => { setSelected(null); setChoices([]); }}
            >
              Clear details
            </button>
          </div>
        </>
      )}
    </div>
  ) : null;

  return (
    <div className="relative" data-testid="scatter-chart" data-x-domain={xd.join(",")} data-y-domain={yd.join(",")}>
      <svg ref={svgRef}
        onPointerDownCapture={interactive ? (event) => {
          suppressClick.current = event.pointerType === "touch";
          if (event.pointerType === "touch") {
            // A second finger cancels selection; native scrolling/browser zoom remain in charge.
            if (touch.current) touch.current.cancelled = true;
            else touch.current = { x: event.clientX, y: event.clientY, pointerId: event.pointerId, cancelled: false };
          }
        } : undefined}
        onPointerMoveCapture={interactive ? (event) => {
          const start = touch.current;
          if (start && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) start.cancelled = true;
        } : undefined}
        onPointerCancelCapture={interactive ? () => { touch.current = null; } : undefined}
        onPointerUpCapture={interactive ? onTouchUp : undefined}
        onClickCapture={interactive ? (event) => {
          if (suppressClick.current && event.detail !== 0) event.stopPropagation();
        } : undefined}
        viewBox={`0 0 ${width} ${height}`} width="100%" role="group" aria-label={label} className="block h-auto w-full select-none">
        <rect x={plot.left} y={plot.top} width={plot.right - plot.left} height={plot.bottom - plot.top} fill="var(--surface-card)" stroke="var(--line)" />
        {niceTicks(xd[0], xd[1], 6).map((tick, index) => (
          <g key={`x${tick}`}>
            {/* Every other vertical line, and fainter than the axis, so the marks carry the picture. */}
            {index % 2 === 0 && <line x1={sx(tick)} x2={sx(tick)} y1={plot.top} y2={plot.bottom} stroke="var(--line)" strokeWidth={0.5} opacity={GRID_OPACITY} data-grid="x" />}
            <text x={sx(tick)} y={plot.bottom + (interactive ? 16 : 18)} textAnchor="middle" data-chart-label="true" data-axis="x-tick" fontSize={textSize(12)} fill="var(--ink-muted)">
              {formatX(tick)}
            </text>
          </g>
        ))}
        {niceTicks(yd[0], yd[1], 6).map((tick) => (
          <g key={`y${tick}`}>
            <line x1={plot.left} x2={plot.right} y1={sy(tick)} y2={sy(tick)} stroke="var(--line)" strokeWidth={0.5} opacity={GRID_OPACITY} data-grid="y" />
            <text x={plot.left - (interactive ? 10 : 8)} y={sy(tick)} textAnchor="end" dominantBaseline="central" data-chart-label="true" data-axis="y-tick" fontSize={textSize(12)} fill="var(--ink-muted)">
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
          <g data-chart-label="true" fontSize={textSize(11)} fontWeight={600} fill="var(--ink-muted)" stroke="var(--surface-card)" strokeWidth={3} paintOrder="stroke" pointerEvents="none" data-testid="average-labels">
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
                  y={top ? plot.top + (interactive ? Math.max(20, textSize(13) + 7) : 20) : plot.bottom - 10}
                  textAnchor={left ? "start" : "end"}
                  data-chart-label="true" fontSize={textSize(13)}
                  fontWeight={700}
                  fill="var(--ink-muted)"
                >
                  {cornerCaptions.names[key]}
                </text>
              </g>
            ))}
          </g>
        )}
        <text x={(plot.left + plot.right) / 2} y={height - (interactive ? 8 : 10)} textAnchor="middle" data-chart-label="true" data-axis="x-title" fontSize={textSize(14)} fontWeight={600} fill="var(--ink)">
          {xLabel}
        </text>
        <text transform={`translate(${interactive ? 18 : 14} ${(plot.top + plot.bottom) / 2}) rotate(-90)`} textAnchor="middle" data-chart-label="true" data-axis="y-title" fontSize={textSize(14)} fontWeight={600} fill="var(--ink)">
          {yLabel}
        </text>
        {/* Every scatter is drawn so up and right is the good end (defense axes are inverted). */}
        {(plot.right - plot.left) / 2 - (xLabel.length * (interactive ? textSize(14) * 0.58 : 8)) / 2 > DIRECTION_CAPTION.length * (interactive ? textSize(11) * 0.55 : 6) + 12 && (
          <text x={plot.right} y={height - (interactive ? 8 : 10)} textAnchor="end" data-chart-label="true" fontSize={textSize(11)} fill="var(--ink-muted)" pointerEvents="none" data-testid="direction-caption">
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
          const labelHalfWidth = p.team.length * (interactive ? textSize(13) * 0.32 : 4);
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
              {state === "searched" && <text x={labelX} y={labelY} textAnchor="middle" data-testid="highlight-label" data-chart-label="true" fontSize={textSize(13)} fontWeight={700} fill="var(--ink)" stroke="var(--surface-card)" strokeWidth={3} paintOrder="stroke">{p.team}</text>}
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
          className="pointer-events-none absolute z-10 hide-on-touch-or-small max-w-72 rounded-lg border border-line bg-surface-card px-2.5 py-1.5 text-xs leading-snug text-ink shadow-md"
          style={{
            left: `${(sx(tip.x) / width) * 100}%`,
            top: `${(sy(tip.y) / height) * 100}%`,
            transform: `translate(${sx(tip.x) > width * 0.6 ? "-105%" : "12px"}, ${sy(tip.y) > height * 0.65 ? "-105%" : "8px"})`,
          }}
        >
          {describe(tip)}
        </div>
      )}
      {detailsContainer ? createPortal(details, detailsContainer) : details}
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
function placeAverageLabels({ average, names, formatX, formatY, sx, sy, plot, points, cornerNames, labelScale = 1 }: {
  average: { x: number; y: number };
  names: { x: string; y: string };
  formatX: (value: number) => string;
  formatY: (value: number) => string;
  sx: (value: number) => number;
  sy: (value: number) => number;
  plot: { left: number; right: number; top: number; bottom: number };
  points: readonly ScatterPoint[];
  cornerNames?: CornerCaptions["names"];
  labelScale?: number;
}): { x: LabelSpot; y: LabelSpot } {
  const bounds: Box = { x: plot.left, y: plot.top, w: plot.right - plot.left, h: plot.bottom - plot.top };
  const obstacles: Box[] = points.map((p) => ({ x: sx(p.x) - BASE_SIZE / 2, y: sy(p.y) - BASE_SIZE / 2, w: BASE_SIZE, h: BASE_SIZE }));
  if (cornerNames) {
    const width = (text: string) => text.length * 8 * labelScale;
    obstacles.push(
      { x: plot.left + 10, y: plot.top + 6, w: width(cornerNames.topLeft), h: 18 * labelScale },
      { x: plot.right - 10 - width(cornerNames.topRight), y: plot.top + 6, w: width(cornerNames.topRight), h: 18 * labelScale },
      { x: plot.left + 10, y: plot.bottom - 24, w: width(cornerNames.bottomLeft), h: 18 * labelScale },
      { x: plot.right - 10 - width(cornerNames.bottomRight), y: plot.bottom - 24, w: width(cornerNames.bottomRight), h: 18 * labelScale },
    );
  }
  const spotBox = (spot: LabelSpot): Box => {
    const w = spot.text.length * LABEL_CHAR * labelScale;
    return { x: spot.anchor === "end" ? spot.x - w : spot.x, y: spot.baseline - 11 * labelScale, w, h: LABEL_HEIGHT * labelScale };
  };
  const choose = (spots: LabelSpot[]): LabelSpot => spots[leastCrowdedSpot(spots.map(spotBox), obstacles, bounds)];

  const lineX = sx(average.x);
  const textX = `${names.x} ${formatX(average.x)}`;
  const height = plot.bottom - plot.top;
  const verticalSpots: LabelSpot[] = [0.0, 1.0, 0.3, 0.7].flatMap((fraction) => {
    const baseline = fraction === 0 ? plot.top + 14 * labelScale : fraction === 1 ? plot.bottom - 8 : plot.top + height * fraction;
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
    { text: textY, ...spot, baseline: lineY + 14 * labelScale },
  ]);
  return { x: vertical, y: choose(horizontalSpots) };
}
