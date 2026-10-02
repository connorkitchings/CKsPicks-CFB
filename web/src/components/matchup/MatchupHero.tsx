import clsx from "clsx";
import Link from "next/link";
import TeamLogo from "@/components/TeamLogo";
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
              data-testid="model-rating"
              className="inline-flex flex-wrap items-baseline justify-center gap-x-1.5 rounded bg-surface-inset px-2 py-0.5 text-xs font-semibold text-ink"
              title="Model overall rank among FBS teams"
            >
              <span>Model Rank</span>
              <span className="font-mono">#{rating.rank ?? "—"}</span>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

/** One centered value in the forecast grid, with the sportsbook beneath when known. */
function Cell({
  value,
  book,
  accent = false,
  muted = false,
  testId,
}: {
  value: string;
  book?: string | null;
  accent?: boolean;
  muted?: boolean;
  testId?: string;
}) {
  return (
    <div className="text-center" data-testid={testId}>
      <span
        className={clsx(
          "font-mono",
          muted ? "text-ink-faint" : accent ? "font-medium text-accent-ink" : "font-medium text-ink",
        )}
      >
        {value}
      </span>
      {book && <span className="block font-sans text-[11px] leading-tight text-ink-faint">{book}</span>}
    </div>
  );
}

/** "Market lines: Bovada", or "Spread: A · Total: B" when the books differ; null when none is recorded. */
function marketBookLine(spread: string | null, total: string | null): string | null {
  if (spread && total && spread !== total) return `Market lines: ${spread} (spread) · ${total} (total)`;
  const book = spread ?? total;
  return book ? `Market lines: ${book}` : null;
}

export function MatchupHero({ matchup }: { matchup: MatchupData }) {
  const isFinal = matchup.homeFinalPoints !== null && matchup.awayFinalPoints !== null;
  const venue = venueLine(matchup);
  const bookLine = marketBookLine(matchup.spreadSource, matchup.totalSource);

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

            <div
              data-testid="forecast-grid"
              className="mt-3 grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-5 gap-y-3 text-sm"
            >
              <span aria-hidden />
              <span className="text-center text-[10px] font-semibold uppercase tracking-wider text-ink-faint">Spread</span>
              <span className="text-center text-[10px] font-semibold uppercase tracking-wider text-ink-faint">Total</span>

              <span className="whitespace-nowrap pt-px text-left font-medium text-ink-muted">Market</span>
              <Cell value={matchup.marketSpread} />
              <Cell value={matchup.marketTotal ? matchup.marketTotal.toFixed(1) : "—"} />

              {matchup.publicationMode === "predictions" && (
                <>
                  <span className="whitespace-nowrap pt-px text-left font-medium text-ink-muted">Model</span>
                  <Cell value={matchup.modelSpread} />
                  <Cell value={matchup.modelTotal ? matchup.modelTotal.toFixed(1) : "—"} />

                  <div className="col-span-3 border-t border-line/60" aria-hidden />
                  <span className="whitespace-nowrap pt-px text-left font-medium text-ink-muted">Model Bet</span>
                  <Cell
                    accent
                    testId="model-bet-spread"
                    value={
                      matchup.spreadLean
                        ? matchup.spreadLean === "home"
                          ? matchup.homeTeam
                          : matchup.awayTeam
                        : "No Spread"
                    }
                    muted={!matchup.spreadLean}
                  />
                  <Cell
                    accent
                    testId="model-bet-total"
                    value={matchup.totalLean ? (matchup.totalLean === "over" ? "Over" : "Under") : "—"}
                    muted={!matchup.totalLean}
                  />
                </>
              )}
            </div>

            {bookLine && (
              <p className="mt-2.5 text-[11px] leading-tight text-ink-faint" data-testid="forecast-books">
                {bookLine}
              </p>
            )}

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
