import Link from "next/link";
import TeamLogo from "@/components/TeamLogo";
import { EdgeNote } from "@/components/slate/EdgeNote";
import type { MatchupData, TeamRatingSummary } from "@/lib/matchup";

function formatKickoff(startDate: Date): string {
  return startDate.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function formatRating(value: number | null): string {
  if (value === null) return "—";
  return `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(2)}`;
}

/** "Las Cruces, NM", "Neutral site · Dublin", or null when no location is known. */
function venueLine(matchup: MatchupData): string | null {
  const place = matchup.venueCity
    ? matchup.venueState
      ? `${matchup.venueCity}, ${matchup.venueState}`
      : matchup.venueCity
    : null;
  if (matchup.neutralSite) return place ? `Neutral site · ${place}` : "Neutral site";
  return place;
}

function TeamBlock({
  name,
  side,
  record,
  rating,
  finalPoints,
  isFinal,
}: {
  name: string;
  side: "Away" | "Home";
  record: string | null;
  rating: TeamRatingSummary;
  finalPoints: number | null;
  isFinal: boolean;
}) {
  return (
    <div className="flex items-center gap-4 sm:flex-col sm:text-center" data-side={side.toLowerCase()}>
      <TeamLogo name={name} px={80} decorative={false} className="h-16 w-16 sm:h-20 sm:w-20" />
      <div className="min-w-0 flex-1 sm:w-full">
        <span className="block truncate text-xl font-bold tracking-tight text-ink">{name}</span>
        <p className="text-xs text-ink-faint">
          {side}
          {record && (
            <>
              {" · "}
              <span className="font-medium tabular-nums text-ink-muted" title="Season record before this game">
                {record}
              </span>
            </>
          )}
        </p>

        {isFinal ? (
          <div className="mt-3 flex flex-col items-center">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">Final Score</span>
            <span className="font-mono text-3xl font-bold text-ink">{finalPoints}</span>
          </div>
        ) : (
          <div className="mt-3 flex flex-col items-center gap-1 text-xs">
            <span
              className="inline-flex items-center gap-1 rounded bg-surface-inset px-2 py-0.5 font-mono text-xs font-semibold text-ink"
              title="V5 overall rating rank among FBS teams"
            >
              V5 rank #{rating.rank ?? "—"}
            </span>
            <span className="text-[11px] text-ink-muted">
              Rating <span className="font-mono">{formatRating(rating.overallRating)}</span>
            </span>
            <span className="text-[11px] text-ink-muted">
              Off #{rating.offenseRank ?? "—"} · Def #{rating.defenseRank ?? "—"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

/** A line plus the sportsbook behind it when the run recorded one. */
function Source({ book }: { book: string | null }) {
  if (!book) return null;
  return <span className="ml-1.5 font-sans text-[11px] text-ink-faint">({book})</span>;
}

export function MatchupHero({ matchup }: { matchup: MatchupData }) {
  const isFinal = matchup.homeFinalPoints !== null && matchup.awayFinalPoints !== null;
  const venue = venueLine(matchup);

  return (
    <section aria-labelledby="matchup-header" className="space-y-4">
      <h2 id="matchup-header" className="sr-only">
        {matchup.awayTeam} at {matchup.homeTeam}
      </h2>

      {/* Breadcrumb and game facts */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3 text-xs text-ink-muted">
        <Link
          href={isFinal ? `/results?week=${matchup.week}` : `/?week=${matchup.week}`}
          className="inline-flex items-center gap-1 font-medium text-accent-ink hover:underline"
        >
          ← Back to {isFinal ? "Results" : "Picks"} (Week {matchup.week})
        </Link>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-ink-faint" data-testid="game-facts">
          <span>{formatKickoff(matchup.startDate)}</span>
          {venue && (
            <>
              <span aria-hidden>·</span>
              <span>{venue}</span>
            </>
          )}
          <span className="rounded bg-surface-inset px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
            Game Breakdown
          </span>
        </div>
      </div>

      <div className="rounded-2xl border border-line bg-surface-card p-5 shadow-sm sm:p-6">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
          <TeamBlock
            name={matchup.awayTeam}
            side="Away"
            record={matchup.awayRecord}
            rating={matchup.awayRating}
            finalPoints={matchup.awayFinalPoints}
            isFinal={isFinal}
          />

          {/* Center: market and model */}
          <div className="flex flex-col items-center justify-center rounded-xl border border-line/60 bg-surface-inset px-5 py-4 text-center sm:min-w-[360px]">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">Forecast & Lines</span>

            <div className="mt-3 inline-grid grid-cols-[auto_1fr] items-baseline gap-x-3.5 gap-y-2 text-left text-sm">
              <span className="whitespace-nowrap font-medium text-ink-muted">Market:</span>
              <div className="flex flex-wrap items-baseline font-mono text-ink">
                <span className="font-medium">{matchup.marketSpread}</span>
                <Source book={matchup.spreadSource} />
                {matchup.marketTotal && (
                  <span className="ml-1.5 font-sans text-xs text-ink-muted">
                    · O/U {matchup.marketTotal.toFixed(1)}
                    <Source book={matchup.totalSource} />
                  </span>
                )}
              </div>

              {matchup.publicationMode === "predictions" && (
                <>
                  <span className="whitespace-nowrap font-medium text-ink-muted">Model:</span>
                  <div className="flex flex-wrap items-baseline font-mono text-ink">
                    <span className="font-medium">{matchup.modelSpread}</span>
                    <EdgeNote edge={matchup.modelSpreadEdge} target="spread" />
                    {matchup.modelTotal && (
                      <span className="ml-1.5 font-sans text-xs text-ink-muted">
                        · O/U {matchup.modelTotal.toFixed(1)}
                        <EdgeNote edge={matchup.modelTotalEdge} target="total" />
                      </span>
                    )}
                  </div>

                  <span className="whitespace-nowrap font-medium text-ink-muted">Model Bet:</span>
                  <div className="flex flex-wrap items-baseline font-mono text-sm">
                    {matchup.spreadLean ? (
                      <span className="font-medium text-accent-ink">
                        {matchup.spreadLean === "home" ? matchup.homeTeam : matchup.awayTeam}
                      </span>
                    ) : (
                      <span className="text-ink-faint">No Spread</span>
                    )}
                    {matchup.totalLean && (
                      <>
                        <span className="mx-1.5 font-sans text-xs text-ink-muted">·</span>
                        <span className="font-medium text-accent-ink">
                          {matchup.totalLean === "over" ? "Over" : "Under"}
                        </span>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>

            {isFinal && (
              <span className="mt-2.5 rounded-full border border-line bg-surface-card px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
                Final: {matchup.awayFinalPoints}–{matchup.homeFinalPoints}
              </span>
            )}
          </div>

          <TeamBlock
            name={matchup.homeTeam}
            side="Home"
            record={matchup.homeRecord}
            rating={matchup.homeRating}
            finalPoints={matchup.homeFinalPoints}
            isFinal={isFinal}
          />
        </div>
      </div>
    </section>
  );
}
