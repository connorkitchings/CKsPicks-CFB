"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { teamAbbr, teamColor } from "@/lib/team-logos";
import type { UnitMatchupRow } from "@/lib/team-stats";
import type { TeamRatingSummary } from "@/lib/matchup";

export type TaleOfTheTapeProps = {
  awayTeam: string;
  homeTeam: string;
  awayOffVsHomeDef: UnitMatchupRow[];
  homeOffVsAwayDef: UnitMatchupRow[];
  awayRating: TeamRatingSummary;
  homeRating: TeamRatingSummary;
};

type FactorKey = "efficiency" | "explosiveness" | "finishing" | "passing_downs" | "field_position";

type FactorDef = {
  key: FactorKey;
  label: string;
  metricKey: string;
  description: string;
};

const FIVE_FACTORS: FactorDef[] = [
  {
    key: "efficiency",
    label: "Overall Efficiency",
    metricKey: "success_rate",
    description: "Success rate (% of plays gaining necessary yardage)",
  },
  {
    key: "explosiveness",
    label: "Explosiveness",
    metricKey: "explosive_rate",
    description: "20+ yard play rate on standard downs",
  },
  {
    key: "finishing",
    label: "Finishing Drives",
    metricKey: "pts_per_scoring_opp",
    description: "Points per scoring opportunity (inside the 40)",
  },
  {
    key: "passing_downs",
    label: "Late-Down Conversions",
    metricKey: "conv_rate_3rd_4th",
    description: "3rd & 4th down conversion rate",
  },
  {
    key: "field_position",
    label: "Starting Field Position",
    metricKey: "avg_start_field_pos",
    description: "Average offensive starting yardline",
  },
];

export function TaleOfTheTape({
  awayTeam,
  homeTeam,
  awayOffVsHomeDef,
  homeOffVsAwayDef,
  awayRating,
  homeRating,
}: TaleOfTheTapeProps) {
  const [selectedClash, setSelectedClash] = useState<"awayOff" | "homeOff">("awayOff");

  const isAwayOff = selectedClash === "awayOff";
  const offTeam = isAwayOff ? awayTeam : homeTeam;
  const defTeam = isAwayOff ? homeTeam : awayTeam;
  const offRating = isAwayOff ? awayRating : homeRating;
  const defRating = isAwayOff ? homeRating : awayRating;
  const rows = isAwayOff ? awayOffVsHomeDef : homeOffVsAwayDef;

  const offColor = teamColor(offTeam);
  const defColor = teamColor(defTeam);

  // Tally factor edges
  let offEdgeCount = 0;
  let defEdgeCount = 0;

  FIVE_FACTORS.forEach((factor) => {
    const row = rows.find((r) => r.key === factor.metricKey);
    if (row?.edge?.side === "offense") offEdgeCount++;
    else if (row?.edge?.side === "defense") defEdgeCount++;
  });

  return (
    <Card as="section" aria-label="Five Factors Tale of the Tape" padding="none" className="p-5 sm:p-6 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-line pb-4 mb-5">
        <div>
          <h2 className="text-base font-bold text-ink-primary flex items-center gap-2">
            <span>Five Factors: Head-to-Head Tape</span>
            <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-accent/10 text-accent">
              Core Analytics
            </span>
          </h2>
          <p className="text-xs text-ink-muted mt-0.5">
            Bi-directional contrast of unit strength based on Bill Connelly&apos;s Five Factors.
          </p>
        </div>

        <SegmentedControl
          size="sm"
          label="Unit matchup clash"
          options={[
            { value: "awayOff", label: `${teamAbbr(awayTeam)} Off vs ${teamAbbr(homeTeam)} Def` },
            { value: "homeOff", label: `${teamAbbr(homeTeam)} Off vs ${teamAbbr(awayTeam)} Def` },
          ]}
          value={selectedClash}
          onChange={setSelectedClash}
        />
      </div>

      {/* Clash header */}
      <div className="grid grid-cols-2 gap-4 pb-3 text-sm font-semibold border-b border-line/40">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: offColor }} />
          <span className="text-ink-primary">{offTeam} Offense</span>
          {offRating.offenseRank !== null && offRating.offenseRank !== undefined && (
            <span className="text-[11px] font-mono text-ink-muted">#{offRating.offenseRank}</span>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 text-right">
          {defRating.defenseRank !== null && defRating.defenseRank !== undefined && (
            <span className="text-[11px] font-mono text-ink-muted">#{defRating.defenseRank}</span>
          )}
          <span className="text-ink-primary">{defTeam} Defense</span>
          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: defColor }} />
        </div>
      </div>

      {/* Factors list */}
      <div className="divide-y divide-line/30">
        {FIVE_FACTORS.map((factor) => {
          const row = rows.find((r) => r.key === factor.metricKey);
          const offVal = row?.offenseValue ?? "—";
          const defVal = row?.defenseValue ?? "—";
          const offRank = row?.offenseRank;
          const defRank = row?.defenseRank;
          const edge = row?.edge;

          // Normalized percentile relative to 134 FBS teams (1 = best rank #1, 0 = worst rank #134)
          const offPct = offRank ? Math.max(0.05, Math.min(1, 1 - (offRank - 1) / 133)) : 0.5;
          const defPct = defRank ? Math.max(0.05, Math.min(1, 1 - (defRank - 1) / 133)) : 0.5;

          return (
            <div key={factor.key} className="py-3.5 first:pt-3 last:pb-1">
              <div className="flex items-center justify-between text-xs mb-1.5">
                {/* Offense stat */}
                <div className="flex items-baseline gap-2">
                  <span className="font-mono font-bold text-sm text-ink-primary">{offVal}</span>
                  {offRank !== null && offRank !== undefined && (
                    <span className="text-[11px] font-medium text-ink-muted">#{offRank}</span>
                  )}
                </div>

                {/* Metric title */}
                <div className="text-center font-semibold text-ink-primary text-xs tracking-tight">
                  {factor.label}
                </div>

                {/* Defense stat */}
                <div className="flex items-baseline gap-2 justify-end">
                  {defRank !== null && defRank !== undefined && (
                    <span className="text-[11px] font-medium text-ink-muted">#{defRank}</span>
                  )}
                  <span className="font-mono font-bold text-sm text-ink-primary">{defVal}</span>
                </div>
              </div>

              {/* Bi-directional comparison bar */}
              <div className="grid grid-cols-2 gap-1 h-2 rounded-full overflow-hidden bg-surface-inset">
                {/* Left side (Offense) */}
                <div className="flex justify-end">
                  <div
                    className="h-full rounded-l-full transition-all duration-300"
                    style={{
                      width: `${offPct * 100}%`,
                      backgroundColor: offColor,
                      opacity: edge?.side === "offense" ? 1 : 0.45,
                    }}
                  />
                </div>
                {/* Right side (Defense) */}
                <div className="flex justify-start">
                  <div
                    className="h-full rounded-r-full transition-all duration-300"
                    style={{
                      width: `${defPct * 100}%`,
                      backgroundColor: defColor,
                      opacity: edge?.side === "defense" ? 1 : 0.45,
                    }}
                  />
                </div>
              </div>

              {/* Edge summary badge */}
              <div className="flex items-center justify-between text-[10px] text-ink-muted mt-1 px-0.5">
                <span>{factor.description}</span>
                {edge?.side === "offense" ? (
                  <span className="font-bold text-ink-primary">
                    Advantage: <span style={{ color: offColor }}>{offTeam}</span>
                  </span>
                ) : edge?.side === "defense" ? (
                  <span className="font-bold text-ink-primary">
                    Advantage: <span style={{ color: defColor }}>{defTeam}</span>
                  </span>
                ) : (
                  <span className="font-medium text-ink-muted">Even matchup</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary Footer */}
      <div className="mt-4 pt-3.5 border-t border-line flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-ink-muted">
        <div>
          <span className="font-semibold text-ink-primary">Tape Verdict: </span>
          {offEdgeCount > defEdgeCount ? (
            <span>
              <strong style={{ color: offColor }}>{offTeam} Offense</strong> controls the statistical edge in{" "}
              {offEdgeCount} of 5 core factors.
            </span>
          ) : defEdgeCount > offEdgeCount ? (
            <span>
              <strong style={{ color: defColor }}>{defTeam} Defense</strong> controls the statistical edge in{" "}
              {defEdgeCount} of 5 core factors.
            </span>
          ) : (
            <span>Both units split advantages evenly across the core factors.</span>
          )}
        </div>
        <div className="text-[11px] text-ink-faint">National ranks based on FBS-vs-FBS games.</div>
      </div>
    </Card>
  );
}
