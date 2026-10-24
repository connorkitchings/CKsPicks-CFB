import clsx from "clsx";
import Link from "next/link";
import TeamLogo from "@/components/TeamLogo";
import { Card } from "@/components/ui/Card";
import { RankChip } from "@/components/ui/RankChip";
import { Eyebrow } from "@/components/ui/SectionHeading";
import type { MatchupData, TeamRatingSummary } from "@/lib/matchup";
import { formatKickoff, venueLine } from "@/lib/matchup-format";
import { bookName } from "@/lib/slate";
import { spreadBetLabel } from "@/lib/betting-format";
import { teamAbbr } from "@/lib/team-logos";
import { teamHref } from "@/lib/teams";
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
    <div className="flex min-w-0 flex-col items-center gap-1 text-center sm:gap-2" data-side={side.toLowerCase()}>
      <TeamLogo name={name} px={80} decorative={false} priority className="h-10 w-10 sm:h-16 sm:w-16" />
      <div className="w-full min-w-0">
        <Link
          href={teamHref(name)}
          className="inline-flex min-h-11 max-w-full items-center justify-center break-words text-base leading-tight font-bold tracking-tight text-ink hover:text-accent-ink hover:underline sm:text-xl"
        >
          {name}
        </Link>
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
          <div className="mt-1 flex flex-col items-center sm:mt-2">
            <Eyebrow as="span">Final Score</Eyebrow>
            <span className="font-mono text-2xl font-bold text-ink sm:text-3xl">{finalPoints}</span>
          </div>
        ) : showRating ? (
          <div className="mt-1 flex flex-col items-center gap-1 text-xs sm:mt-2">
            <span
              data-testid="model-rating"
              className="inline-flex flex-wrap items-center justify-center gap-x-1.5 text-xs font-semibold text-ink"
              title="Model overall rank among FBS teams"
            >
              <span>Model Rank</span>
              <RankChip rank={rating.rank} />
            </span>
          </div>
        ) : <p className="mt-1 text-xs text-ink-muted sm:mt-2">Model ratings unavailable</p>}
      </div>
    </div>
  );
}

/** "James Madison -10.5" -> "JMU -10.5" for the team that leads the label (or is the whole label); other values pass through. */
function abbreviateLead(value: string, teams: readonly string[]): string {
  const team = teams.find((name) => value === name || value.startsWith(`${name} `));
  return team ? `${teamAbbr(team)}${value.slice(team.length)}` : value;
}

/** One centered value in the forecast grid, with the sportsbook beneath when known. */
function Cell({
  value,
  short = value,
  book,
  badge,
  accent = false,
  muted = false,
  testId,
}: {
  value: string;
  /** Phones show this instead, so a long team name never wraps the cell. */
  short?: string;
  book?: string | null;
  badge?: React.ReactNode;
  accent?: boolean;
  muted?: boolean;
  testId?: string;
}) {
  return (
    <div className="flex min-w-0 flex-col items-center justify-center text-center max-sm:flex-row max-sm:flex-wrap max-sm:gap-x-1" data-testid={testId}>
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
          {short === value ? value : (
            <>
              <span className="max-sm:hidden">{value}</span>
              <span className="sm:hidden" title={value}>{short}</span>
            </>
          )}
        </span>
        {badge}
      </div>
      {book && <span className="block font-sans text-xs leading-tight text-ink-muted max-sm:text-[10px]">{book}</span>}
    </div>
  );
}

export function MatchupHero({ matchup }: { matchup: MatchupData }) {
  const isFinal = matchup.homeFinalPoints !== null && matchup.awayFinalPoints !== null;
  const venue = venueLine(matchup);
  const teams = [matchup.homeTeam, matchup.awayTeam];
  const betSpread =
    spreadBetLabel(matchup.homeTeam, matchup.awayTeam, matchup.spreadLean, matchup.marketSpreadLine) ??
    (matchup.spreadLean ? (matchup.spreadLean === "home" ? matchup.homeTeam : matchup.awayTeam) : "No Spread");

  return (
    <section aria-labelledby="matchup-header" className="space-y-2 sm:space-y-4">
      <h1 id="matchup-header" className="sr-only">
        {matchup.awayTeam} at {matchup.homeTeam}
      </h1>

      {/* Breadcrumb and game facts */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-muted max-sm:flex-nowrap sm:border-b sm:border-line sm:pb-3">
        <Link
          href={`/?week=${matchup.week}`}
          className="inline-flex max-sm:hidden min-h-11 items-center gap-1 text-sm font-medium text-accent-ink hover:underline"
        >
          ← Week {matchup.week} games
        </Link>
        {/* Right-aligned on every line so the share button, always last, keeps its tooltip inside the viewport. */}
        <div className="ml-auto flex flex-wrap items-center justify-end gap-x-2 gap-y-1 text-ink-muted max-sm:w-full max-sm:flex-nowrap max-sm:justify-between max-sm:gap-x-3" data-testid="game-facts">
          {/* Phones: the date and place share one left block beside the share buttons (wrapping if long); from sm the spans are items of the row. */}
          <p className="min-w-0 max-sm:flex-1 sm:contents">
            <span>{formatKickoff(matchup.startDate)}</span>
            {venue && (
              <>
                <span aria-hidden className="max-sm:mx-1.5">·</span>
                <span>{venue}</span>
              </>
            )}
          </p>
          <span className="rounded bg-surface-inset px-2 py-0.5 max-sm:hidden text-xs font-semibold uppercase tracking-wider text-ink-muted">
            Game Breakdown
          </span>
          <ShareButton matchup={matchup} disabled={matchup.lineageStatus !== "ready"} />
        </div>
      </div>

      <Card className="max-sm:p-3 sm:p-6">
        {/* Phones: teams side by side with the forecast beneath. lg+: forecast between the teams. */}
        <div className="grid grid-cols-2 items-start gap-2 sm:gap-4 lg:grid-cols-[1fr_auto_1fr] lg:items-center">
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
        <div className="col-span-2 mt-1 flex min-w-0 flex-col items-center justify-center rounded-xl border border-line/60 bg-surface-inset px-3 py-2 sm:mt-2 sm:py-4 text-center sm:px-5 lg:col-span-1 lg:col-start-2 lg:row-start-1 lg:mt-0 lg:w-[475px]">
          <Eyebrow as="span" className="max-sm:sr-only">Forecast & Lines</Eyebrow>

          <div
            data-testid="forecast-grid"
            className="grid w-full sm:mt-3 grid-cols-[auto_minmax(0,1fr)_minmax(0,1fr)] items-start gap-x-2 gap-y-2 text-sm sm:gap-y-3 sm:gap-x-4"
          >
            <span aria-hidden />
            <Eyebrow as="span" className="text-center">Spread</Eyebrow>
            <Eyebrow as="span" className="text-center">Total</Eyebrow>

            <span className="whitespace-nowrap pt-px text-left font-medium text-ink-muted">Market</span>
            <Cell value={matchup.marketSpread} short={abbreviateLead(matchup.marketSpread, teams)} book={bookName(matchup.spreadSource)} />
            <Cell value={matchup.marketTotal ? matchup.marketTotal.toFixed(1) : "—"} book={bookName(matchup.totalSource)} />

            {matchup.publicationMode === "predictions" && matchup.lineageStatus === "ready" && (
              <>
                <span className="whitespace-nowrap pt-px text-left font-medium text-ink-muted">Model</span>
                <Cell value={matchup.modelSpread} short={abbreviateLead(matchup.modelSpread, teams)} />
                <Cell value={matchup.modelTotal ? matchup.modelTotal.toFixed(1) : "—"} />

                <div className="col-span-3 border-t border-line/60" aria-hidden />
                <span className="whitespace-nowrap pt-px text-left font-medium text-ink-muted">Model Bet</span>
                <Cell
                  accent
                  testId="model-bet-spread"
                  value={betSpread}
                  short={abbreviateLead(betSpread, teams)}
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
      </Card>
    </section>
  );
}
