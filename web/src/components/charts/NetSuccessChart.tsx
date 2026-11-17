"use client";

import { useEffect, useRef, useState } from "react";
import { chartColor, netSuccessCap, netSuccessDomain, niceTicks, type NetSuccessBar } from "@/lib/charts";
import { Card } from "@/components/ui/Card";
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

/** Two short parallel diagonals across a capped bar near its tip. */
function BarBreak({ horizontal, c, tip, outward, thick }: { horizontal: boolean; c: number; tip: number; outward: number; thick: number }) {
  const half = thick / 2 + 1.5;
  // Offsets run from the tip back toward zero.
  const mark = (back: number) => {
    const at = horizontal ? tip - outward * back : tip + outward * back;
    return horizontal
      ? <line x1={at - 3} x2={at + 3} y1={c + half} y2={c - half} stroke="var(--surface-card)" strokeWidth={2} />
      : <line x1={c - half} x2={c + half} y1={at + 3} y2={at - 3} stroke="var(--surface-card)" strokeWidth={2} />;
  };
  return (
    <g pointerEvents="none" data-bar-break>
      {mark(8)}
      {mark(14)}
    </g>
  );
}

type Box = { x: number; y: number; w: number; h: number };

/** Gap kept between a break value's backing card and a logo it is moved clear of. */
const LOGO_CLEARANCE = 2;

function overlaps(a: Box, b: Box): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

/** Moves a box along the bar axis to the nearer side of each logo it overlaps. */
function clearLogos(box: Box, logos: readonly Box[]): Box {
  let moved = box;
  for (let pass = 0; pass < logos.length; pass++) {
    const hit = logos.find((logo) => overlaps(moved, logo));
    if (!hit) break;
    const above = hit.y - moved.h - LOGO_CLEARANCE;
    const below = hit.y + hit.h + LOGO_CLEARANCE;
    moved = { ...moved, y: Math.abs(above - moved.y) <= Math.abs(below - moved.y) ? above : below };
  }
  return moved;
}

/**
 * A capped bar's true value on a card-coloured backing, so a neighbour's logo cannot show through.
 * Drawn after every bar and kept inside the chart's right edge. In a vertical chart it is also moved along the bar axis off any logo.
 */
function BreakValue({ gameId, horizontal, c, tip, outward, thick, text, unit, width, dim, logos }: { gameId: number | string; horizontal: boolean; c: number; tip: number; outward: number; thick: number; text: string; unit: number; width: number; dim: boolean; logos: readonly Box[] }) {
  const fontSize = 12 * unit;
  const pad = 3 * unit;
  const textWidth = text.length * 7.5 * unit;
  const flip = !horizontal && c + thick / 2 + 4 + textWidth > width;
  const anchor = horizontal || flip ? "end" : "start";
  const x = horizontal ? tip : flip ? c - thick / 2 - 4 : c + thick / 2 + 4;
  let baseline = horizontal ? c - thick / 2 - 4 : tip + outward * 11 * unit;
  const boxAt = (y: number): Box => ({
    x: anchor === "end" ? x - textWidth - pad : x - pad,
    y: y - fontSize * 0.8 - pad,
    w: textWidth + 2 * pad,
    h: fontSize + 2 * pad,
  });
  let box = boxAt(baseline);
  if (!horizontal) {
    box = clearLogos(box, logos);
    baseline = box.y + fontSize * 0.8 + pad;
  }
  return (
    <g pointerEvents="none" opacity={dim ? 0.15 : 1}>
      <rect data-testid="break-value-bg" data-game={gameId} x={box.x} y={box.y} width={box.w} height={box.h} rx={3 * unit} fill="var(--surface-card)" stroke="var(--line)" strokeWidth={unit} />
      <text x={x} y={baseline} textAnchor={anchor} fontSize={fontSize} fontWeight={600} fill="var(--ink)" data-break-value>
        {text}
      </text>
    </g>
  );
}

export function NetSuccessChart({
  bars,
  stateOf,
  describe,
  orientation = "vertical",
  width: requestedWidth,
  height: requestedHeight,
  interactive = true,
  label,
}: NetSuccessChartProps) {
  const root = useRef<HTMLDivElement>(null);
  const [renderedWidth, setRenderedWidth] = useState<number | null>(null);
  const horizontal = orientation === "horizontal";
  useEffect(() => {
    if (!interactive || !root.current) return;
    const observer = new ResizeObserver(([entry]) => setRenderedWidth(entry.contentRect.width));
    observer.observe(root.current);
    return () => observer.disconnect();
  }, [interactive]);
  // Phones match the viewBox to CSS pixels for readable text and >=44px row targets.
  const width = interactive && horizontal ? renderedWidth ?? requestedWidth : requestedWidth;
  // viewBox units per CSS pixel, so SVG text keeps a 12px floor at any container width.
  const unit = interactive && renderedWidth ? width / renderedWidth : 1;
  const phone = interactive && horizontal;
  const height = phone ? 72 + 48 * bars.length : requestedHeight;
  const ordered = bars.filter((b) => stateOf(b) !== "dim").map((b) => String(b.gameId));
  const { selected, register, handlers, setSelected } = useChartSelection(ordered);
  const tipBar = interactive && selected ? bars.find((b) => String(b.gameId) === selected) : undefined;
  const narrowLabels = phone && width < 340;
  const margin = horizontal ? { top: 28, right: 20, bottom: phone ? 44 : 28, left: narrowLabels ? 76 : 100 } : { top: 10, right: 12, bottom: Math.round(90 * unit), left: 56 };
  const plot = { left: margin.left, right: width - margin.right, top: margin.top, bottom: height - margin.bottom };
  const span = horizontal ? plot.right - plot.left : plot.bottom - plot.top;
  const count = Math.max(1, bars.length);
  const band = (horizontal ? plot.bottom - plot.top : plot.right - plot.left) / count;
  const thick = Math.max(2, Math.min(horizontal ? 18 : 34, band * 0.64));
  const logo = Math.max(10, Math.min(LOGO, horizontal ? band * 0.9 : band * 0.95));
  // The winner's logo sits 0.6 logos past the bar tip; the loser's just across zero.
  const cap = netSuccessCap(bars.map((b) => b.value));
  const [domainLow, domainHigh] = netSuccessDomain(
    bars.map((b) => b.value),
    span,
    logo * 1.1 + 4,
    logo + 10,
  );
  const along = (value: number) => {
    const fraction = (value - domainLow) / (domainHigh - domainLow);
    return horizontal ? plot.left + fraction * span : plot.bottom - fraction * span;
  };
  const ticks = niceTicks(domainLow, domainHigh, horizontal && interactive ? 3 : 8);
  const zero = along(0);
  const isCapped = (bar: NetSuccessBar) => bar.value > cap.high || bar.value < cap.low;
  // A capped bar's tip is held at its cap.
  const tipOf = (bar: NetSuccessBar) => along(isCapped(bar) ? (bar.value > 0 ? cap.high : cap.low) : bar.value);
  // Dense slates (about 50+ games) read best as upright columns sized to the band.
  const verticalLabels = band < 20;
  const labelSize = 12 * unit;

  function center(index: number): number {
    return (horizontal ? plot.top : plot.left) + band * (index + 0.5);
  }

  // Keep the winner beyond the bar tip and the loser just across the zero axis.
  function logoSlots(bar: NetSuccessBar, index: number) {
    const c = center(index);
    const tip = tipOf(bar);
    const outward = bar.value >= 0 ? 1 : -1;
    const gap = logo * 0.6;
    const loserGap = logo / 2 + 6;
    return {
      winner: horizontal ? { cx: tip + outward * gap, cy: c } : { cx: c, cy: tip - outward * gap },
      loser: horizontal ? { cx: zero - outward * loserGap, cy: c } : { cx: c, cy: zero + outward * loserGap },
    };
  }
  const logoBoxes: Box[] = bars.flatMap((bar, index) =>
    Object.values(logoSlots(bar, index)).map(({ cx, cy }) => ({ x: cx - logo / 2, y: cy - logo / 2, w: logo, h: logo })),
  );

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
    <div ref={root} className="relative" data-testid="net-success-chart" data-orientation={orientation}>
      {tipBar && horizontal && interactive && (
        <Card padding="sm" role="status" data-testid="chart-selected-details" className="sticky top-2 z-10 mb-3 text-sm text-ink">
          <p>{describe(tipBar)}</p>
          <button type="button" className="min-h-11 px-3 font-semibold text-accent" onClick={() => setSelected(null)}>Clear selection</button>
        </Card>
      )}
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
                <text x={along(tick)} y={plot.top - 8} textAnchor="middle" fontSize={horizontal && interactive ? 12 : 11} fill="var(--ink-muted)">
                  {(tick * 100).toFixed(0)}
                </text>
                {phone && (
                  <text x={along(tick)} y={plot.bottom + 16} textAnchor="middle" fontSize={12} fill="var(--ink-muted)" data-axis="x-tick-bottom">
                    {(tick * 100).toFixed(0)}
                  </text>
                )}
              </>
            ) : (
              <>
                <line x1={plot.left} x2={plot.right} y1={along(tick)} y2={along(tick)} stroke="var(--line)" strokeWidth={0.6} />
                <text x={plot.left - 8} y={along(tick)} textAnchor="end" dominantBaseline="central" fontSize={12 * unit} fill="var(--ink-muted)">
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
          <text transform={`translate(14 ${(plot.top + plot.bottom) / 2}) rotate(-90)`} textAnchor="middle" fontSize={13 * unit} fontWeight={600} fill="var(--ink)">
            Net success rate (pct)
          </text>
        )}
        {horizontal && (
          <text x={(plot.left + plot.right) / 2} y={height - 4} textAnchor="middle" fontSize={interactive ? 12 : 11} fontWeight={600} fill="var(--ink)">
            Net success rate (pct)
          </text>
        )}
        {bars.map((bar, index) => {
          const state = stateOf(bar);
          const focusable = interactive && state !== "dim";
          const c = center(index);
          // A bar past the cap is drawn only up to it; a break mark and its true value say so.
          const capped = isCapped(bar);
          const tip = tipOf(bar);
          const outward = bar.value >= 0 ? 1 : -1;
          const { winner: winnerAt, loser: loserAt } = logoSlots(bar, index);
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
              {focusable && horizontal && <rect x={0} y={c - band / 2} width={width} height={band} fill="transparent" data-row-target />}
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
              {capped && <BarBreak horizontal={horizontal} c={c} tip={tip} outward={outward} thick={thick} />}
              <TeamMark team={bar.winner} cx={winnerAt.cx} cy={winnerAt.cy} size={logo} />
              <TeamMark team={bar.loser} cx={loserAt.cx} cy={loserAt.cy} size={logo} />
              {horizontal ? (
                <text x={plot.left - 6} y={c} textAnchor="end" dominantBaseline="central" fontSize={interactive ? 12 : Math.min(11, band * 0.7)} fill="var(--ink)">
                  {narrowLabels && bar.label.includes(" ") ? (
                    <>
                      <tspan x={plot.left - 6} dy="-0.6em">{bar.label.slice(0, bar.label.indexOf(" "))}</tspan>
                      <tspan x={plot.left - 6} dy="1.2em">{bar.label.slice(bar.label.indexOf(" ") + 1)}</tspan>
                    </>
                  ) : bar.label}
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
        {bars.map((bar, index) => {
          if (!isCapped(bar)) return null;
          return <BreakValue key={bar.gameId} gameId={bar.gameId} horizontal={horizontal} c={center(index)} tip={tipOf(bar)} outward={bar.value >= 0 ? 1 : -1} thick={thick} text={(bar.value * 100).toFixed(1)} unit={unit} width={width} dim={stateOf(bar) === "dim"} logos={logoBoxes} />;
        })}
      </svg>
      {tipBar && !horizontal && (
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
