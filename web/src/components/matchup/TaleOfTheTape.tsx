"use client";

import { Card } from "@/components/ui/Card";
import { RankChip } from "@/components/ui/RankChip";
import { chartColor } from "@/lib/charts";
import { buildTapeRows } from "@/lib/tale-of-tape";
import { FALLBACK_TEAM_COLOR, teamAltColor, teamColor } from "@/lib/team-logos";
import { rankLabel, rankTitle, type UnitMatchupRow } from "@/lib/team-stats";
import type { TeamRatingSummary } from "@/lib/matchup";

export type TaleOfTheTapeProps = {
  selectedSide: "away" | "home";
  awayTeam: string;
  homeTeam: string;
  awayOffVsHomeDef: UnitMatchupRow[];
  homeOffVsAwayDef: UnitMatchupRow[];
  awayRating: TeamRatingSummary;
  homeRating: TeamRatingSummary;
};

const sideColor = (team: string) => chartColor(teamColor(team), teamAltColor(team), FALLBACK_TEAM_COLOR);

export function TaleOfTheTape({
  selectedSide,
  awayTeam,
  homeTeam,
  awayOffVsHomeDef,
  homeOffVsAwayDef,
  awayRating,
  homeRating,
}: TaleOfTheTapeProps) {
  const isAwayOff = selectedSide === "away";
  const offTeam = isAwayOff ? awayTeam : homeTeam;
  const defTeam = isAwayOff ? homeTeam : awayTeam;
  const offRating = isAwayOff ? awayRating : homeRating;
  const defRating = isAwayOff ? homeRating : awayRating;

  const offColor = sideColor(offTeam);
  const defColor = sideColor(defTeam);

  const tapeRows = buildTapeRows(isAwayOff ? awayOffVsHomeDef : homeOffVsAwayDef);

  return (
    <Card
      as="section"
      aria-label="Key factors tale of the tape"
      data-testid="tale-of-the-tape"
      padding="none"
      className="p-5 sm:p-6"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-line pb-4 mb-5">
        <div className="min-w-0">
          <h2 className="text-base font-bold text-ink-primary">Key factors</h2>
          <p className="text-xs text-ink-muted mt-0.5">
            Descriptive offense-versus-defense comparisons. These contextual statistics do not feed the rating. Turnovers are not included.
          </p>
        </div>

      </div>

      {/* Clash header */}
      <div className="grid grid-cols-2 gap-4 pb-3 text-sm font-semibold border-b border-line/40">
        <div className="flex min-w-0 items-center gap-2">
          <span className="w-3 h-3 shrink-0 rounded-full" style={{ backgroundColor: offColor }} />
          <span className="min-w-0 truncate text-ink-primary">{offTeam} Offense</span>
          {offRating.offenseRank !== null && offRating.offenseRank !== undefined && (
            <RankChip rank={offRating.offenseRank} title="Model Offense Rank" className="shrink-0 text-[11px]" />
          )}
        </div>
        <div className="flex min-w-0 items-center justify-end gap-2 text-right">
          {defRating.defenseRank !== null && defRating.defenseRank !== undefined && (
            <RankChip rank={defRating.defenseRank} title="Model Defense Rank" className="shrink-0 text-[11px]" />
          )}
          <span className="min-w-0 truncate text-ink-primary">{defTeam} Defense</span>
          <span className="w-3 h-3 shrink-0 rounded-full" style={{ backgroundColor: defColor }} />
        </div>
      </div>

      {/* Factors list */}
      <div className="divide-y divide-line/30">
        {tapeRows.map((row) => {
          const { factor, edge } = row;
          return (
            <div key={factor.key} data-testid="tape-row" className="py-3.5 first:pt-3 last:pb-1">
              <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-xs mb-1.5">
                <div className="flex items-baseline gap-2">
                  <span className="font-mono font-bold text-sm text-ink-primary">{row.offenseValue}</span>
                  {row.offenseRank !== null && (
                    <RankChip
                      rank={row.offenseRank}
                      total={row.offenseCohort ?? undefined}
                      label={rankLabel(row.offenseRank, row.offenseTied)}
                      className="text-[11px] font-medium"
                      title={rankTitle(row.offenseRank, row.offenseTied, row.offenseCohort)}
                    />
                  )}
                </div>

                <div className="order-first basis-full text-center font-semibold text-ink-primary text-xs tracking-tight sm:order-none sm:basis-auto">
                  {factor.label}
                </div>

                <div className="flex items-baseline gap-2 justify-end">
                  {row.defenseRank !== null && (
                    <RankChip
                      rank={row.defenseRank}
                      total={row.defenseCohort ?? undefined}
                      label={rankLabel(row.defenseRank, row.defenseTied)}
                      className="text-[11px] font-medium"
                      title={rankTitle(row.defenseRank, row.defenseTied, row.defenseCohort)}
                    />
                  )}
                  <span className="font-mono font-bold text-sm text-ink-primary">{row.defenseValue}</span>
                </div>
              </div>

              {/* Bi-directional comparison bar; none when a rank is missing */}
              <div className="grid grid-cols-2 gap-1 h-2 rounded-full overflow-hidden bg-surface-inset">
                {edge && row.offenseBar !== null && row.defenseBar !== null && (
                  <>
                    <div className="flex justify-end">
                      <div
                        className="h-full rounded-l-full transition-all duration-300"
                        style={{
                          width: `${row.offenseBar * 100}%`,
                          backgroundColor: offColor,
                          opacity: edge.side === "offense" ? 1 : 0.45,
                        }}
                      />
                    </div>
                    <div className="flex justify-start">
                      <div
                        className="h-full rounded-r-full transition-all duration-300"
                        style={{
                          width: `${row.defenseBar * 100}%`,
                          backgroundColor: defColor,
                          opacity: edge.side === "defense" ? 1 : 0.45,
                        }}
                      />
                    </div>
                  </>
                )}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-x-3 text-[10px] text-ink-muted mt-1 px-0.5">
                <span className="min-w-0">{factor.description}</span>
                {!edge ? (
                  <span className="font-medium text-ink-muted">Not available</span>
                ) : edge.side === "offense" ? (
                  <span className="font-bold text-ink-primary">
                    Higher-ranked unit: <span style={{ color: offColor }}>{offTeam}</span>
                  </span>
                ) : edge.side === "defense" ? (
                  <span className="font-bold text-ink-primary">
                    Higher-ranked unit: <span style={{ color: defColor }}>{defTeam}</span>
                  </span>
                ) : (
                  <span className="font-medium text-ink-muted">Similar rank percentiles</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary Footer */}
      <div className="mt-4 pt-3.5 border-t border-line flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-ink-muted">
        <div className="text-[11px] text-ink-faint">National ranks based on FBS-vs-FBS games.</div>
      </div>
    </Card>
  );
}
