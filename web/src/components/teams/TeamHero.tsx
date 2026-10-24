import clsx from "clsx";
import TeamLogo from "@/components/TeamLogo";
import { MatchupButton } from "@/components/MatchupLinks";
import { ratingText } from "@/components/ratings/StatGrid";
import { dayShort } from "@/components/slate/format";
import type { TeamGame } from "@/components/teams/TeamGameRow";
import { forecastText, marketText } from "@/lib/team-games";
import { phoneTeamName } from "@/lib/team-logos";
import type { TeamSummary } from "@/lib/team-summary";

const rankText = (rank: number | null | undefined) => (typeof rank === "number" ? `#${rank}` : "—");

/** "▲ 4 spots · +0.15": the move since the previous stored week, green up and red down. */
function WeeklyChange({ change }: { change: NonNullable<TeamSummary["change"]> }) {
  const { spots, delta } = change;
  const tone = spots > 0 ? "bg-win-soft text-win" : spots < 0 ? "bg-loss-soft text-loss" : "bg-surface-inset text-ink-muted";
  return (
    <span data-testid="rating-change" title="Change since the previous week" className={clsx("rounded px-1.5 py-px font-mono text-xs font-medium tabular-nums", tone)}>
      {spots === 0 ? "no rank change" : `${spots > 0 ? "▲" : "▼"} ${Math.abs(spots)} ${Math.abs(spots) === 1 ? "spot" : "spots"}`} · {ratingText(delta)}
    </span>
  );
}

function StripCell({ label, title, value, rank }: { label: string; title: string; value?: string; rank?: number | null }) {
  return (
    <div title={title} role="group" aria-label={title} className="min-w-0 bg-surface-card px-3 py-2.5">
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">{label}</dt>
      <dd className="mt-0.5 whitespace-nowrap font-mono text-base font-semibold tabular-nums text-ink sm:text-lg">
        {value ?? rankText(rank)}
        {value !== undefined && rank !== undefined && <small className="ml-1 font-sans text-[11px] font-normal text-ink-muted">{rankText(rank)}</small>}
      </dd>
    </div>
  );
}

/** The callout for a team's next unplayed game: opponent, date, market line and total, and the model's forecast. */
function NextGame({ game, team }: { game: TeamGame; team: string }) {
  const home = game.homeTeam === team;
  const opponent = home ? game.awayTeam : game.homeTeam;
  const market = marketText(game);
  const forecast = forecastText(game);
  return (
    <section aria-label="Next game" className="flex min-w-0 flex-col gap-1.5 rounded-lg border border-accent-line bg-accent-soft px-3.5 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-accent-ink">Next game · Wk {game.week} · {dayShort(game.startDate)}</p>
      <p className="flex items-center gap-2 text-base font-semibold text-ink">
        <span className="text-[13px] font-normal text-ink-muted">{home ? "vs" : "at"}</span>
        <TeamLogo name={opponent} px={24} />
        <span className="min-w-0 truncate">{phoneTeamName(opponent)}</span>
      </p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[13px]">
        <dt className="text-ink-muted">Market</dt><dd className="font-mono tabular-nums text-ink">{market ?? "—"}</dd>
        <dt className="text-ink-muted">Forecast</dt><dd className="font-mono tabular-nums text-ink">{forecast ?? "—"}</dd>
      </dl>
      <div className="-mb-1 flex"><MatchupButton gameId={game.gameId} className="-ml-3 font-semibold text-accent-ink hover:underline sm:-ml-2" /></div>
    </section>
  );
}

/**
 * The team page's summary card: identity and record, overall rating with rank and weekly move,
 * the six-stat strip and the next-game callout. `summary` is null when the ratings read failed.
 */
export function TeamHero({ team, conference, summary, nextGame }: {
  team: string;
  conference: string | null;
  summary: TeamSummary | null;
  nextGame: TeamGame | null;
}) {
  const rating = summary?.rating;
  const record = typeof rating?.wins === "number" && typeof rating.losses === "number" ? `${rating.wins}–${rating.losses}` : null;
  const identity = [conference, record && `${record} overall`].filter(Boolean).join(" · ");
  return (
    <section aria-label="Team summary" data-testid="team-hero" data-card="" className="grid gap-4 rounded-xl border border-line bg-surface-card p-3.5 shadow-2xs sm:grid-cols-2 sm:p-4 lg:grid-cols-[auto_minmax(0,1fr)_minmax(0,20rem)] lg:gap-6">
      <div className="min-w-0 sm:col-span-2 lg:col-span-1">
        <div className="flex items-center gap-3 sm:gap-4">
          <TeamLogo name={team} px={64} priority className="max-sm:h-12 max-sm:w-12" />
          <div className="min-w-0">
            <h1 className="text-balance text-[22px] font-bold leading-tight tracking-tight text-ink sm:text-[28px]">{team}</h1>
            {identity && <p className="mt-1 text-sm text-ink-muted" title="Record against FBS teams">{identity}</p>}
          </div>
        </div>
        {rating && summary && (
          <p className="mt-3 flex flex-wrap items-baseline gap-x-2.5 gap-y-1" title="Overall rating">
            <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-ink-faint">Overall</span>
            <span className="font-mono text-3xl font-semibold tabular-nums tracking-tight text-ink">{ratingText(rating.overallRating)}</span>
            <span className="font-semibold tabular-nums text-ink" title="Overall rank">{rankText(summary.overallRank)}</span>
            {summary.change && <WeeklyChange change={summary.change} />}
          </p>
        )}
      </div>
      {rating && summary && (
        <dl className="grid grid-cols-3 gap-px self-center overflow-hidden rounded-lg border border-line bg-line">
          <StripCell label="OFF" title="Offense rating and rank" value={ratingText(rating.offenseRating)} rank={summary.offenseRank} />
          <StripCell label="DEF" title="Defense rating and rank" value={ratingText(rating.defenseRating)} rank={summary.defenseRank} />
          <StripCell label="SOR" title="Strength of record rank" rank={rating.sorRank} />
          <StripCell label="SOS played" title="Strength of schedule played, rank" rank={summary.sos.played} />
          <StripCell label="SOS left" title="Strength of schedule remaining, rank" rank={summary.sos.remaining} />
          <StripCell label="Wins vs avg" title="Wins above average" value={typeof rating.waa === "number" ? `${rating.waa > 0 ? "+" : ""}${rating.waa.toFixed(1)}` : "—"} />
        </dl>
      )}
      {nextGame && <NextGame game={nextGame} team={team} />}
    </section>
  );
}
