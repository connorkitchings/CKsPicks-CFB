"use client";

import { useRef, useState } from "react";
import { chartColor, niceTicks, type GameLogGame } from "@/lib/charts";
import { FALLBACK_TEAM_COLOR, teamAltColor, teamColor } from "@/lib/team-logos";
import type { GameLogChartProps } from "./GameLogChart";

/** Shared increasing scale; exports never mount this mobile renderer. */
export function MobileGameLog({ log, domains, formatTick, formatValue, describe, label }: GameLogChartProps) {
  const [selected, setSelected] = useState<number | null>(null);
  const gesture = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const lo = Math.min(0, domains.offense[0], domains.defense[0]);
  const hi = Math.max(0, domains.offense[1], domains.defense[1]);
  const position = (value: number) => 100 * (value - lo) / (hi - lo || 1);
  const zero = position(0);
  const ticks = niceTicks(lo, hi, 3).filter((tick) => tick >= lo && tick <= hi);
  const fill = chartColor(teamColor(log.team), teamAltColor(log.team), FALLBACK_TEAM_COLOR);
  const current = log.games.find((game) => game.gameId === selected);

  function choose(game: GameLogGame) { setSelected(current?.gameId === game.gameId ? null : game.gameId); }

  return (
    <div data-testid="game-log-chart" data-orientation="horizontal" role="group" aria-label={label}>
      {current && <div role="status" data-testid="chart-selected-details" className="sticky top-2 z-10 mb-3 space-y-2 rounded-md border border-line bg-surface-card p-3 text-sm text-ink">
        <p>{describe(current)}</p>
        <button type="button" className="min-h-11 px-3 font-semibold text-accent" onClick={() => setSelected(null)}>Clear selection</button>
      </div>}
      {(["offense", "defense"] as const).map((side) => (
        <section key={side} className="mb-5 space-y-2" data-testid={`game-log-panel-${side}`}>
          <h3 className="text-sm font-semibold text-ink">{side === "offense" ? "Offense · higher is better" : "Defense allowed · lower is better"}</h3>
          <div className="relative mx-2 h-5 text-xs tabular-nums text-ink-muted" aria-label="Shared numeric scale" data-testid="game-log-mobile-scale">
            {ticks.map((tick) => <span key={tick} className="absolute" style={{ left: `${position(tick)}%`, transform: `translateX(${position(tick) < 10 ? 0 : position(tick) > 90 ? -100 : -50}%)` }}>{formatTick(tick)}</span>)}
          </div>
          {log.games.map((game) => {
            const value = game[side];
            const average = game.average[side];
            return (
              <button
                key={game.gameId}
                type="button"
                data-game={game.gameId}
                data-side={side}
                data-value={value ?? "missing"}
                aria-label={describe(game)}
                aria-pressed={current?.gameId === game.gameId}
                className="block min-h-11 w-full space-y-2 rounded-md border border-line p-2 text-left text-xs text-ink focus-visible:outline-2 focus-visible:outline-accent"
                onPointerDown={(event) => { gesture.current = { x: event.clientX, y: event.clientY, moved: false }; }}
                onPointerMove={(event) => { const start = gesture.current; if (start && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) start.moved = true; }}
                onPointerCancel={() => { if (gesture.current) gesture.current.moved = true; }}
                onKeyDown={(event) => { if (event.key === "Escape") setSelected(null); }}
                onClick={(event) => { if (event.detail > 0 && gesture.current?.moved) return; choose(game); }}
              >
                <span className="block break-words leading-relaxed">Wk {game.week} · {game.site === "away" ? "Away at" : game.site === "neutral" ? "Neutral vs" : "Home vs"} <strong>{game.opponent}</strong> · {game.result}</span>
                <span className="flex flex-wrap justify-between gap-x-2 gap-y-1 tabular-nums">
                  <span>{value === null ? "n/a" : formatValue(value)}</span>
                  <span className="text-ink-muted">Weekly FBS avg {average === null ? "n/a" : formatValue(average)}</span>
                </span>
                <svg className="block h-5 w-full" viewBox="0 0 1000 20" preserveAspectRatio="none" aria-hidden="true">
                  <line x1={zero * 10} x2={zero * 10} y1={0} y2={20} stroke="var(--line)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
                  {value !== null && (value === 0 ? <line data-bar x1={zero * 10} x2={zero * 10} y1={4} y2={16} stroke={fill} strokeWidth={2} vectorEffect="non-scaling-stroke" /> : <rect data-bar x={Math.min(zero, position(value)) * 10} y={4} width={Math.abs(position(value) - zero) * 10} height={12} fill={fill} />)}
                  {average !== null && <line data-average x1={position(average) * 10} x2={position(average) * 10} y1={0} y2={20} stroke="var(--ink)" strokeWidth={2} strokeDasharray="3 2" vectorEffect="non-scaling-stroke" />}
                </svg>
              </button>
            );
          })}
        </section>
      ))}

    </div>
  );
}
