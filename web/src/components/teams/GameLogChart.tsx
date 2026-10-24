"use client";

import { useState } from "react";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { TeamSection } from "@/components/teams/TeamSection";
import { useIsPhone } from "@/lib/use-is-phone";
import type { GameLogBar } from "@/lib/team-game-log";
import { chartColor } from "@/lib/charts";
import { FALLBACK_TEAM_COLOR, phoneTeamName, teamAbbr, teamAltColor, teamColor } from "@/lib/team-logos";

type Measure = "success" | "points";

const MEASURES = [{ value: "success", label: "Success rate" }, { value: "points", label: "Points" }] as const;

const HEIGHT = 216;
const PAD = { left: 38, right: 8, top: 14, bottom: 36 };
/** Tick spacing and the smallest axis maximum: success rate in steps of 20 points, points in steps of 20. */
const SCALE = { success: { step: 0.2, min: 0.6 }, points: { step: 20, min: 20 } } as const;

const valueOf = (bar: GameLogBar, measure: Measure) => (measure === "success"
  ? [bar.teamSuccess, bar.opponentSuccess] as const
  : [bar.pointsFor, bar.pointsAgainst] as const);
const format = (value: number, measure: Measure) => (measure === "success" ? `${Math.round(value * 100)}` : `${value}`);

/** The team's bar beside its opponent's for each played game, switchable between success rate and points. */
function Bars({ bars, measure, width, team, teamFill }: { bars: readonly GameLogBar[]; measure: Measure; width: number; team: string; teamFill: string }) {
  const { step, min } = SCALE[measure];
  const peak = Math.max(0, ...bars.flatMap((bar) => valueOf(bar, measure).filter((value) => value !== null)));
  const max = Math.max(min, Math.ceil(peak / step - 1e-9) * step);
  const ticks = Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step);
  const plotW = width - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const y = (value: number) => PAD.top + plotH - (value / max) * plotH;
  const slot = plotW / bars.length;
  const barW = Math.min(26, slot / 2 - 3);
  const summary = `${measure === "success" ? "Success rate" : "Points"} by game, ${phoneTeamName(team)} then opponent: ${bars.map((bar) => {
    const [own, opp] = valueOf(bar, measure);
    const show = (value: number | null) => (value === null ? "n/a" : measure === "success" ? `${format(value, measure)}%` : format(value, measure));
    return `Week ${bar.week} ${teamAbbr(bar.opponent)} ${show(own)}, ${show(opp)}`;
  }).join("; ")}`;
  return (
    <svg viewBox={`0 0 ${width} ${HEIGHT}`} role="img" aria-label={summary} className="block h-auto w-full text-[11px]">
      <rect x={PAD.left} y={PAD.top} width={plotW} height={plotH} fill="var(--surface-card)" stroke="var(--line)" />
      {ticks.map((tick) => (
        <g key={tick}>
          <line x1={PAD.left} x2={width - PAD.right} y1={y(tick)} y2={y(tick)} stroke="var(--line)" strokeWidth={0.6} />
          <text x={PAD.left - 6} y={y(tick) + 4} textAnchor="end" className="fill-ink-muted font-mono">{measure === "success" ? `${Math.round(tick * 100)}%` : tick}</text>
        </g>
      ))}
      {bars.map((bar, i) => {
        const center = PAD.left + slot * (i + 0.5);
        const [own, opp] = valueOf(bar, measure);
        return (
          <g key={bar.gameId}>
            {([[own, center - barW - 1, teamFill], [opp, center + 1, "var(--ink-faint)"]] as const).map(([value, x, fill]) => value === null ? null : (
              <g key={x}>
                <rect x={x} y={y(value)} width={barW} height={Math.max(plotH - (y(value) - PAD.top), 1)} rx={2} fill={fill} />
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

/** The team page's game log card: the team's bars beside its opponent's per played game. */
export function GameLogChart({ bars, team }: { bars: readonly GameLogBar[]; team: string }) {
  const [measure, setMeasure] = useState<Measure>("success");
  const phone = useIsPhone();
  const teamFill = chartColor(teamColor(team), teamAltColor(team), FALLBACK_TEAM_COLOR);
  return (
    <TeamSection
      id="team-game-log"
      title="Game log"
      actions={bars.length > 0 && <SegmentedControl<Measure> label="Game log measure" value={measure} onChange={setMeasure} options={MEASURES} size="sm" testId="game-log-measure" />}
    >
      {bars.length === 0 ? <p className="text-sm text-ink-muted">Game-by-game bars appear after the first game.</p> : <>
        <Bars bars={bars} measure={measure} width={phone ? 360 : 640} team={team} teamFill={teamFill} />
        <p className="mt-2 flex gap-4 text-xs text-ink-muted" aria-hidden>
          <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: teamFill }} />{phoneTeamName(team)}</span>
          <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: "var(--ink-faint)" }} />Opponent</span>
        </p>
      </>}
    </TeamSection>
  );
}
