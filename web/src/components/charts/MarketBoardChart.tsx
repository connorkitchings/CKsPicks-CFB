"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { etTime } from "@/lib/time-et";
import { teamAbbr } from "@/lib/team-logos";
import { niceTicks, type Domain, type MarketBoardMetric, type MarketBoardPoint } from "@/lib/charts";

export type MarketBoardChartProps = {
  points: readonly MarketBoardPoint[];
  metric: MarketBoardMetric;
  xDomain: Domain;
  yDomain: Domain;
  width: number;
  height: number;
  selectedGameId: number | null;
  onSelectGame: (gameId: number | null) => void;
  interactive?: boolean;
  label: string;
};

const MARGIN = { top: 24, right: 32, bottom: 56, left: 80 };
const MOBILE_MARGIN = { top: 16, right: 16, bottom: 50, left: 60 };

export function MarketBoardChart({
  points,
  metric,
  xDomain,
  yDomain,
  width,
  height,
  selectedGameId,
  onSelectGame,
  interactive = true,
  label,
}: MarketBoardChartProps) {
  const chartId = useId();
  const [hoveredGameId, setHoveredGameId] = useState<number | null>(null);

  const isMobile = width < 500;
  const margin = isMobile ? MOBILE_MARGIN : MARGIN;
  const plotWidth = Math.max(10, width - margin.left - margin.right);
  const plotHeight = Math.max(10, height - margin.top - margin.bottom);

  const xSpan = xDomain[1] - xDomain[0] || 1;
  const ySpan = yDomain[1] - yDomain[0] || 1;

  const scaleX = (v: number) => margin.left + ((v - xDomain[0]) / xSpan) * plotWidth;
  const scaleY = (v: number) => margin.top + (1 - (v - yDomain[0]) / ySpan) * plotHeight;

  const xTicks = niceTicks(xDomain[0], xDomain[1], isMobile ? 4 : 6);
  const yTicks = niceTicks(yDomain[0], yDomain[1], isMobile ? 4 : 6);

  const diagMin = Math.max(xDomain[0], yDomain[0]);
  const diagMax = Math.min(xDomain[1], yDomain[1]);
  const hasDiag = diagMin < diagMax;

  const activeId = hoveredGameId ?? selectedGameId;
  const activePoint = points.find((p) => p.gameId === activeId);

  const formatLine = (v: number) => (metric === "spread" ? (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)) : v.toFixed(1));

  return (
    <div className="relative flex flex-col items-center">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height="100%"
        role="img"
        aria-label={label}
        className="overflow-visible select-none"
      >
        <title>{label}</title>
        <desc>
          Market line vs Model prediction scatter chart for {metric}.
          Consensus line y = x runs diagonally.
        </desc>

        {/* Grid lines */}
        <g aria-hidden="true" className="stroke-line/50">
          {xTicks.map((tick) => {
            const x = scaleX(tick);
            return <line key={`gx-${tick}`} x1={x} x2={x} y1={margin.top} y2={margin.top + plotHeight} strokeDasharray="2 2" />;
          })}
          {yTicks.map((tick) => {
            const y = scaleY(tick);
            return <line key={`gy-${tick}`} x1={margin.left} x2={margin.left + plotWidth} y1={y} y2={y} strokeDasharray="2 2" />;
          })}
        </g>

        {/* Consensus diagonal line (y = x) */}
        {hasDiag && (
          <g aria-hidden="true">
            <line
              x1={scaleX(diagMin)}
              y1={scaleY(diagMin)}
              x2={scaleX(diagMax)}
              y2={scaleY(diagMax)}
              stroke="currentColor"
              strokeDasharray="4 4"
              strokeWidth={1.5}
              className="text-ink-muted/60"
            />
            <text
              x={scaleX(diagMax) - 6}
              y={scaleY(diagMax) - 8}
              textAnchor="end"
              className="fill-ink-faint text-[10px] font-medium"
            >
              Consensus (Model = Market)
            </text>
          </g>
        )}

        {/* Axes */}
        <g aria-hidden="true" className="stroke-line">
          <line x1={margin.left} x2={margin.left + plotWidth} y1={margin.top + plotHeight} y2={margin.top + plotHeight} strokeWidth={1} />
          <line x1={margin.left} x2={margin.left} y1={margin.top} y2={margin.top + plotHeight} strokeWidth={1} />
        </g>

        {/* Ticks and tick labels */}
        <g aria-hidden="true" className="fill-ink-muted text-[11px] font-mono">
          {xTicks.map((tick) => (
            <text key={`tx-${tick}`} x={scaleX(tick)} y={margin.top + plotHeight + 18} textAnchor="middle">
              {formatLine(tick)}
            </text>
          ))}
          {yTicks.map((tick) => (
            <text key={`ty-${tick}`} x={margin.left - 10} y={scaleY(tick) + 4} textAnchor="end">
              {formatLine(tick)}
            </text>
          ))}
        </g>

        {/* Axis titles */}
        <text
          x={margin.left + plotWidth / 2}
          y={margin.top + plotHeight + (isMobile ? 38 : 44)}
          textAnchor="middle"
          className="fill-ink-primary text-xs font-semibold"
        >
          {metric === "spread" ? "Market Home Team Spread Line" : "Market Over/Under Total Line"}
        </text>
        <text
          x={-(margin.top + plotHeight / 2)}
          y={isMobile ? 18 : 24}
          transform="rotate(-90)"
          textAnchor="middle"
          className="fill-ink-primary text-xs font-semibold"
        >
          {metric === "spread" ? "V5 Model Home Spread Projection" : "V5 Model Predicted Total"}
        </text>

        {/* Plot points */}
        <g role="group" aria-label="Games">
          {points.map((p) => {
            const cx = scaleX(p.x);
            const cy = scaleY(p.y);
            const isHovered = activeId === p.gameId;
            const r = isHovered ? (p.highEdge ? 9 : 8) : p.highEdge ? 7 : 5;

            return (
              <g
                key={`game-${p.gameId}-${chartId}`}
                className="cursor-pointer transition-transform duration-150"
                onPointerEnter={() => interactive && setHoveredGameId(p.gameId)}
                onPointerLeave={() => interactive && setHoveredGameId(null)}
                onClick={() => interactive && onSelectGame(selectedGameId === p.gameId ? null : p.gameId)}
              >
                {/* Hit target */}
                <circle cx={cx} cy={cy} r={16} fill="transparent" />

                {/* High edge halo */}
                {p.highEdge && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={r + 4}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    className="text-accent/40 animate-pulse"
                  />
                )}

                {/* Main dot */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={r}
                  className={
                    p.highEdge
                      ? isHovered
                        ? "fill-accent stroke-white stroke-2 shadow-sm"
                        : "fill-accent stroke-surface-card stroke-2"
                      : isHovered
                        ? "fill-ink stroke-white stroke-2"
                        : "fill-ink-muted/80 hover:fill-ink stroke-surface-card stroke-1"
                  }
                />

                {/* Matchup label for high-edge or hovered games */}
                {(p.highEdge || isHovered) && (
                  <text
                    x={cx}
                    y={cy - r - 4}
                    textAnchor="middle"
                    className={`pointer-events-none text-[10px] font-bold ${
                      isHovered ? "fill-ink font-extrabold" : "fill-ink-muted"
                    }`}
                  >
                    {teamAbbr(p.awayTeam)}@{teamAbbr(p.homeTeam)}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* Active game tooltip / details card */}
      {activePoint && (
        <div
          data-testid="market-board-tooltip"
          className="mt-3 w-full max-w-md rounded-xl border border-line bg-surface-card p-3 shadow-sm transition-all text-xs"
        >
          <div className="flex items-center justify-between border-b border-line/60 pb-2">
            <div className="font-semibold text-ink-primary">
              {activePoint.awayTeam} at {activePoint.homeTeam}
            </div>
            <div className="text-[11px] text-ink-muted">{etTime(activePoint.startDate)}</div>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-ink-secondary">
            <div>
              <span className="text-ink-muted">Market: </span>
              <span className="font-mono font-medium">{formatLine(activePoint.marketLine)}</span>
            </div>
            <div>
              <span className="text-ink-muted">Model: </span>
              <span className="font-mono font-medium">{formatLine(activePoint.modelLine)}</span>
            </div>
            <div>
              <span className="text-ink-muted">Edge: </span>
              <span
                className={`font-mono font-bold ${
                  activePoint.highEdge ? "text-accent" : "text-ink-primary"
                }`}
              >
                {activePoint.edge.toFixed(1)} pts
              </span>
            </div>
            {activePoint.lean && (
              <div>
                <span className="text-ink-muted">Lean: </span>
                <span className="font-semibold uppercase text-ink-primary">{activePoint.lean}</span>
              </div>
            )}
          </div>
          <div className="mt-2.5 pt-2 border-t border-line/40 flex justify-end">
            <Link
              href={`/matchup/${activePoint.gameId}`}
              className="inline-flex items-center gap-1 font-semibold text-accent hover:underline"
            >
              View Matchup Details &rarr;
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
