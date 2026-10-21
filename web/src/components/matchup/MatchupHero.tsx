import clsx from "clsx";
import Link from "next/link";
import TeamLogo from "@/components/TeamLogo";
import type { MatchupData, TeamRatingSummary } from "@/lib/matchup";
import { formatKickoff, venueLine } from "@/lib/matchup-format";
import { bookName } from "@/lib/slate";
import { ResultBadge } from "@/components/slate/ResultBadge";
import { ShareButton } from "./ShareButton";

function TeamBlock({
  name,
  side,
  record,
  rating,
  finalPoints,
  isFinal,
  showRating,
}: {
  name: string;
  side: "Away" | "Home";
  record: string | null;
  rating: TeamRatingSummary;
  finalPoints: number | null;
  isFinal: boolean;
  showRating: boolean;
}) {
  return (
    <div className="flex min-w-0 flex-col items-center gap-2 text-center" data-side={side.toLowerCase()}>
      <TeamLogo name={name} px={80} decorative={false} priority className="h-12 w-12 sm:h-16 sm:w-16" />
      <div className="w-full min-w-0">
        <span className="block break-words text-base font-bold tracking-tight text-ink sm:text-xl">{name}</span>
        <p className="text-xs text-ink-muted">
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
          <div className="mt-2 flex flex-col items-center">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">Final Score</span>
            <span className="font-mono text-3xl font-bold text-ink">{finalPoints}</span>
          </div>
        ) : showRating ? (
          <div className="mt-2 flex flex-col items-center gap-1 text-xs">
            <span
              data-testid="model-rating"
              className="inline-flex flex-wrap items-baseline justify-center gap-x-1.5 rounded bg-surface-inset px-2 py-0.5 text-xs font-semibold text-ink"
              title="Model overall rank among FBS teams"
            >
              <span>Model Rank</span>
              <span className="font-mono">#{rating.rank ?? "—"}</span>
            </span>
          </div>
        ) : <p className="mt-2 text-xs text-ink-muted">Model ratings unavailable</p>}
      </div>
    </div>
  );
}

/** One centered value in the forecast grid, with the sportsbook beneath when known. */
function Cell({
  value,
  book,
  badge,
  accent = false,
  muted = false,
  testId,
}: {
  value: string;
  book?: string | null;
  badge?: React.ReactNode;
  accent?: boolean;
  muted?: boolean;
  testId?: string;
}) {
  return (
    <div className="flex min-w-0 flex-col items-center justify-center text-center" data-testid={testId}>
      <div className="inline-flex max-w-full flex-wrap items-center justify-center gap-1 sm:gap-1.5">
        <span
          className={clsx(
            "break-words leading-snug text-center",
            accent
              ? "font-sans text-xs font-semibold text-accent-ink sm:text-sm"
              : "font-mono text-xs font-medium text-ink sm:text-sm",
            muted && "!font-normal !text-ink-muted",
          )}
        >
          {value}
        </span>
        {badge}
      </div>
      {book && <span className="block font-sans text-xs leading-tight text-ink-muted">{book}</span>}
    </div>
  );
}

export function MatchupHero({ matchup }: { matchup: MatchupData }) {
  const isFinal = matchup.homeFinalPoints !== null && matchup.awayFinalPoints !== null;
  const venue = venueLine(matchup);

  return (
    <section aria-labelledby="matchup-header" className="space-y-4">
      <h1 id="matchup-header" className="sr-only">
        {matchup.awayTeam} at {matchup.homeTeam}
      </h1>

      {/* Breadcrumb and game facts */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3 text-xs text-ink-muted">
        <Link
          href={isFinal ? `/results?week=${matchup.week}` : `/?week=${matchup.week}`}
          className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-accent-ink hover:underline"
        >
          ← Back to {isFinal ? "Results" : "Picks"} (Week {matchup.week})
        </Link>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-ink-muted" data-testid="game-facts">
          <span>{formatKickoff(matchup.startDate)}</span>
          {venue && (
            <>
              <span aria-hidden>·</span>
              <span>{venue}</span>
            </>
          )}
          <span className="rounded bg-surface-inset px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-ink-muted">
            Game Breakdown
          </span>
          <ShareButton matchup={matchup} disabled={matchup.lineageStatus !== "ready"} />
        </div>
      </div>

      <div className="rounded-2xl border border-line bg-surface-card p-4 shadow-sm sm:p-6">
        {/* Phones: teams side by side with the forecast beneath. lg+: forecast between the teams. */}
        <div className="grid grid-cols-2 items-start gap-4 lg:grid-cols-[1fr_auto_1fr] lg:items-center">
          <TeamBlock
            name={matchup.awayTeam}
            side="Away"
            record={matchup.awayRecord}
            rating={matchup.awayRating}
            finalPoints={matchup.awayFinalPoints}
            isFinal={isFinal}
            showRating={matchup.lineageStatus === "ready"}
          />

          <TeamBlock
            name={matchup.homeTeam}
            side="Home"
            record={matchup.homeRecord}
            rating={matchup.homeRating}
            finalPoints={matchup.homeFinalPoints}
            isFinal={isFinal}
            showRating={matchup.lineageStatus === "ready"}
          />
        {/* Market and model: beneath the teams on phones, between them from lg. */}
        <div className="col-span-2 mt-2 flex min-w-0 flex-col items-center justify-center rounded-xl border border-line/60 bg-surface-inset px-3 py-4 text-center sm:px-5 lg:col-span-1 lg:col-start-2 lg:row-start-1 lg:mt-0 lg:w-[475px]">
          <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">Forecast & Lines</span>

          <div
            data-testid="forecast-grid"
            className="mt-3 grid w-full grid-cols-[auto_minmax(0,1fr)_minmax(0,1fr)] items-start gap-x-2 gap-y-3 text-sm sm:gap-x-4"
          >
            <span aria-hidden />
            <span className="text-center text-xs font-semibold uppercase tracking-wider text-ink-muted">Spread</span>
            <span className="text-center text-xs font-semibold uppercase tracking-wider text-ink-muted">Total</span>

            <span className="whitespace-nowrap pt-px text-left font-medium text-ink-muted">Market</span>
            <Cell value={matchup.marketSpread} book={bookName(matchup.spreadSource)} />
            <Cell value={matchup.marketTotal ? matchup.marketTotal.toFixed(1) : "—"} book={bookName(matchup.totalSource)} />

            {matchup.publicationMode === "predictions" && matchup.lineageStatus === "ready" && (
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
                  badge={
                    isFinal && matchup.spreadLean && matchup.spreadResult ? (
                      <ResultBadge grade={matchup.spreadResult} />
                    ) : null
                  }
                />
                <Cell
                  accent
                  testId="model-bet-total"
                  value={matchup.totalLean ? (matchup.totalLean === "over" ? "Over" : "Under") : "—"}
                  muted={!matchup.totalLean}
                  badge={
                    isFinal && matchup.totalLean && matchup.totalResult ? (
                      <ResultBadge grade={matchup.totalResult} />
                    ) : null
                  }
                />
              </>
            )}
          </div>

          {isFinal && (
            <span className="mt-2.5 rounded-full border border-line bg-surface-card px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider text-ink-muted">
              Final: {matchup.awayFinalPoints}–{matchup.homeFinalPoints}
            </span>
          )}
        </div>
        </div>
      </div>
    </section>
  );
}
