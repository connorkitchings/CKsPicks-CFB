"use client";

import { useState } from "react";
import type { MatchupData } from "@/lib/matchup";
import { etDateTime } from "@/lib/time-et";
import { statsWindowLabel } from "@/lib/stats-window";
import { pppText, priorPercent, type UnitRatingBreakdown } from "@/lib/rating-breakdown";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { ShareButton } from "./ShareButton";
import { UnitMatchups } from "./UnitMatchups";
import { TaleOfTheTape } from "./TaleOfTheTape";
import { RatingBreakdown } from "./RatingBreakdown";

function CompactEvidence({ team, unit }: { team: string; unit: UnitRatingBreakdown }) {
  return <div className="min-w-0 border-l-2 border-line-strong pl-4">
    <h3 className="text-sm font-semibold">{team} {unit.role}</h3>
    {unit.status === "ready" ? <>
      <p className="mt-2 text-lg tabular-nums"><span className="text-xs text-ink-muted">Raw PPP</span> {unit.rawPpp === null ? "—" : pppText(unit.rawPpp)} <span aria-hidden="true">→</span><span className="sr-only">to</span> <span className="text-xs text-ink-muted">Adjusted PPP</span> {unit.adjustedPpp === null ? "—" : pppText(unit.adjustedPpp)}</p>
      <p className="text-xs text-ink-muted">{unit.completedGames} games · {Math.round(unit.possessions)} possessions · {priorPercent(unit.priorWeight)} prior weight</p>
    </> : <p className="mt-2 text-sm text-ink-muted">Verified rating evidence unavailable.</p>}
  </div>;
}

export function MatchupAnalysis({ matchup }: { matchup: MatchupData }) {
  const [side, setSide] = useState<"away" | "home">("away");
  const ready = matchup.lineageStatus === "ready";
  const forecast = ready && matchup.publicationMode === "predictions";
  const stats = ready ? matchup.stats : null;
  const offTeam = side === "away" ? matchup.awayTeam : matchup.homeTeam;
  const defTeam = side === "away" ? matchup.homeTeam : matchup.awayTeam;
  const offRating = side === "away" ? matchup.awayRating : matchup.homeRating;
  const defRating = side === "away" ? matchup.homeRating : matchup.awayRating;
  const facts: string[] = [];
  if (forecast && matchup.modelSpreadEdge !== null) facts.push(`The spread forecast differs from the selected market line by ${Math.abs(matchup.modelSpreadEdge).toFixed(1)} points.`);
  if (forecast && matchup.modelSpreadEdge === null && matchup.modelTotalEdge !== null) facts.push(`The total forecast is ${Math.abs(matchup.modelTotalEdge).toFixed(1)} points ${matchup.modelTotalEdge >= 0 ? "above" : "below"} the selected market total.`);
  if (stats && offRating?.offenseRank != null && defRating?.defenseRank != null) facts.push(`${offTeam} has the No. ${offRating.offenseRank} model offense; ${defTeam} has the No. ${defRating.defenseRank} model defense.`);
  const selectedEvidence = side === "away" ? matchup.ratingBreakdown.awayOffense : matchup.ratingBreakdown.homeOffense;
  if (ready && selectedEvidence.status === "ready" && selectedEvidence.rawPpp !== null && selectedEvidence.adjustedPpp !== null) {
    facts.push(`${offTeam}'s offense averaged ${pppText(selectedEvidence.rawPpp)} raw points per possession and ${pppText(selectedEvidence.adjustedPpp)} after opponent adjustment.`);
  }
  return <div className="space-y-8">
    <div className="space-y-1 text-xs text-ink-muted" aria-label="Data context">
      <p>{matchup.publicationMode === "predictions" && `Forecast updated ${etDateTime(matchup.updatedAt)}. `}Finals and analysis update with published data releases; this is not a live feed.</p>
    </div>
    {facts.length > 0 && <section aria-labelledby="matchup-insights"><h2 id="matchup-insights" className="text-xl font-semibold">What stands out</h2><ul className="mt-3 grid gap-3 text-sm text-ink sm:grid-cols-3">{facts.map((fact) => <li key={fact} className="border-t border-line pt-3">{fact}</li>)}</ul></section>}
    {stats ? <>
      <section className="space-y-4" aria-label="Team stats">
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">When each team has the ball</h2><SegmentedControl label="Offense comparison" value={side} onChange={setSide} options={[{value:"away",label:matchup.awayTeam},{value:"home",label:matchup.homeTeam}]} /></div>
        {matchup.homeFinalPoints !== null && matchup.awayFinalPoints !== null && <p className="text-sm text-ink-muted">The forecast and supporting evidence below are frozen pregame context, not an actual-game statistical breakdown.</p>}
        <p data-testid="matchup-notes" className="text-xs leading-relaxed text-ink-muted">{statsWindowLabel(stats.asOfWeek)}. FBS opponents only; regulation play, garbage time excluded; raw, not opponent-adjusted. Defense values are allowed. {stats.cohortSize !== null && `Ranks among ${stats.cohortSize} teams; T = tied.`}</p>
        <TaleOfTheTape selectedSide={side} awayTeam={matchup.awayTeam} homeTeam={matchup.homeTeam} awayOffVsHomeDef={stats.awayOffVsHomeDef} homeOffVsAwayDef={stats.homeOffVsAwayDef} awayRating={matchup.awayRating} homeRating={matchup.homeRating} />
      </section>
      <section aria-label="Rating evidence" className="space-y-4"><h2 className="text-xl font-semibold">Rating evidence</h2><p className="text-sm text-ink-muted">The same verified possessions before and after opponent adjustment. The rating blends adjusted performance with its preseason estimate.</p><div className="grid gap-5 sm:grid-cols-2"><CompactEvidence team={offTeam} unit={side === "away" ? matchup.ratingBreakdown.awayOffense : matchup.ratingBreakdown.homeOffense}/><CompactEvidence team={defTeam} unit={side === "away" ? matchup.ratingBreakdown.homeDefense : matchup.ratingBreakdown.awayDefense}/></div></section>
      <details className="group border-t border-line py-4"><summary className="flex min-h-11 cursor-pointer items-center justify-between gap-2 text-lg font-semibold">Full unit statistics<DisclosureChevron /></summary><div className="mt-4"><UnitMatchups selected={side} away={{offenseTeam:matchup.awayTeam,defenseTeam:matchup.homeTeam,rows:stats.awayOffVsHomeDef,offenseRank:matchup.awayRating.offenseRank,defenseRank:matchup.homeRating.defenseRank}} home={{offenseTeam:matchup.homeTeam,defenseTeam:matchup.awayTeam,rows:stats.homeOffVsAwayDef,offenseRank:matchup.homeRating.offenseRank,defenseRank:matchup.awayRating.defenseRank}} /></div></details>
      <details className="group border-t border-line py-4"><summary className="flex min-h-11 cursor-pointer items-center justify-between gap-2 text-lg font-semibold">Full rating breakdown<DisclosureChevron /></summary><div className="mt-4"><RatingBreakdown selectedSide={side} awayTeam={matchup.awayTeam} homeTeam={matchup.homeTeam} breakdown={matchup.ratingBreakdown} /></div></details>
    </> : matchup.lineageStatus !== "ready"
      ? <p role="status" aria-label="Team stats" className="border-t border-line py-6 text-sm text-ink-muted">{matchup.lineageStatus === "updating" ? "Matchup data is updating. Model-derived ratings and statistics are temporarily hidden." : "Matchup data provenance is unavailable. Model-derived ratings and statistics are hidden."}</p>
      : <section aria-label="Team stats" className="border-t border-line py-6 text-sm text-ink-muted">{matchup.statsUnavailable ? "Team stats are temporarily unavailable." : "Team stats are not published for this game yet."}</section>}
    <section data-testid="matchup-summary-header" className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4"><h2 className="text-lg font-semibold">Share matchup</h2><ShareButton matchup={matchup} selectedSide={side} disabled={!stats} /></section>
  </div>;
}

function DisclosureChevron() {
  return <svg aria-hidden="true" viewBox="0 0 20 20" className="size-5 shrink-0 transition-transform group-open:rotate-180" fill="none" stroke="currentColor" strokeWidth="2"><path d="m5 7.5 5 5 5-5" /></svg>;
}
