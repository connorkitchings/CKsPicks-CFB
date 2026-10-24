"use client";

import { useState } from "react";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { TeamSection } from "@/components/teams/TeamSection";
import { useIsPhone } from "@/lib/use-is-phone";
import type { GameLogBar } from "@/lib/team-game-log";
import { teamAbbr } from "@/lib/team-logos";

type Measure = "success" | "points";

const MEASURES = [{ value: "success", label: "Success rate" }, { value: "points", label: "Points" }] as const;

const HEIGHT = 216;
const PAD = { left: 38, right: 8, top: 14, bottom: 36 };
/** Tick spacing and the smallest axis maximum: success rate in steps of 20 points, points in steps of 20. */
const SCALE = { success: { step: 0.2, min: 0.6 }, points: { step: 20, min: 20 } } as const;

const valueOf = (bar: GameLogBar, measure: Measure) => (measure === "success"
  ? [bar.offenseSuccess, bar.defenseSuccess] as const
  : [bar.pointsFor, bar.pointsAgainst] as const);
const format = (value: number, measure: Measure) => (measure === "success" ? `${Math.round(value * 100)}` : `${value}`);

/** Offense and defense bars for each played game, switchable between success rate and points. */
function Bars({ bars, measure, width }: { bars: readonly GameLogBar[]; measure: Measure; width: number }) {
  const { step, min } = SCALE[measure];
  const peak = Math.max(0, ...bars.flatMap((bar) => valueOf(bar, measure).filter((value) => value !== null)));
  const max = Math.max(min, Math.ceil(peak / step - 1e-9) * step);
  const ticks = Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step);
  const plotW = width - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const y = (value: number) => PAD.top + plotH - (value / max) * plotH;
  const slot = plotW / bars.length;
  const barW = Math.min(26, slot / 2 - 3);
  const summary = `${measure === "success" ? "Success rate" : "Points"} by game, offense then defense: ${bars.map((bar) => {
    const [off, def] = valueOf(bar, measure);
    const show = (value: number | null) => (value === null ? "n/a" : measure === "success" ? `${format(value, measure)}%` : format(value, measure));
    return `Week ${bar.week} ${teamAbbr(bar.opponent)} ${show(off)}, ${show(def)}`;
  }).join("; ")}`;
  return (
    <svg viewBox={`0 0 ${width} ${HEIGHT}`} role="img" aria-label={summary} className="block h-auto w-full text-[11px]">
      {ticks.map((tick) => (
        <g key={tick}>
          <line x1={PAD.left} x2={width - PAD.right} y1={y(tick)} y2={y(tick)} className="stroke-line" />
          <text x={PAD.left - 6} y={y(tick) + 4} textAnchor="end" className="fill-ink-muted font-mono">{measure === "success" ? `${Math.round(tick * 100)}%` : tick}</text>
        </g>
      ))}
      {bars.map((bar, i) => {
        const center = PAD.left + slot * (i + 0.5);
        const [off, def] = valueOf(bar, measure);
        return (
          <g key={bar.gameId}>
            {([[off, center - barW - 1, "fill-accent"], [def, center + 1, "fill-warn"]] as const).map(([value, x, fill]) => value === null ? null : (
              <g key={fill}>
                <rect x={x} y={y(value)} width={barW} height={Math.max(plotH - (y(value) - PAD.top), 1)} rx={2} className={fill} />
                <text x={x + barW / 2} y={y(value) - 4} textAnchor="middle" className="fill-ink-muted font-mono">{format(value, measure)}</text>
              </g>
            ))}
            <text x={center} y={HEIGHT - 20} textAnchor="middle" className="fill-ink-muted font-mono">Wk {bar.week}</text>
            <text x={center} y={HEIGHT - 6} textAnchor="middle" className="fill-ink-muted font-mono">{teamAbbr(bar.opponent)}</text>
          </g>
        );
      })}
    </svg>
  );
}

/** The team page's game log card: paired offense and defense bars per played game. */
export function GameLogChart({ bars }: { bars: readonly GameLogBar[] }) {
  const [measure, setMeasure] = useState<Measure>("success");
  const phone = useIsPhone();
  return (
    <TeamSection
      id="team-game-log"
      title="Game log"
      actions={bars.length > 0 && <SegmentedControl<Measure> label="Game log measure" value={measure} onChange={setMeasure} options={MEASURES} size="sm" testId="game-log-measure" />}
    >
      {bars.length === 0 ? <p className="text-sm text-ink-muted">Game-by-game bars appear after the first game.</p> : <>
        <Bars bars={bars} measure={measure} width={phone ? 360 : 640} />
        <p className="mt-2 flex gap-4 text-xs text-ink-muted" aria-hidden>
          <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-sm bg-accent" />Offense</span>
          <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-sm bg-warn" />Defense (opponent)</span>
        </p>
      </>}
    </TeamSection>
  );
}
