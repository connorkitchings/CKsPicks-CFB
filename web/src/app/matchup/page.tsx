import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Header, Footer } from "@/components/Header";
import TeamLogo from "@/components/TeamLogo";
import {
  getAvailableWeeks,
  getCurrentWeek,
  getGamesForWeek,
  getMarketGamesForWeek,
  type Game,
} from "@/lib/queries";
import { isMatchupEnabled } from "@/lib/matchup-gate";
import { groupGamesByDay, pickWeek } from "@/lib/matchup-index";
import { isPublishedWeek, publicationScope } from "@/lib/publication";
import { protoGames } from "@/test/fixtures/picks-prototype";

export const revalidate = 300;

export const metadata: Metadata = {
  title: "Matchups",
  robots: { index: false, follow: false },
};

const timeFormat = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  hour: "numeric",
  minute: "2-digit",
});

/** Game picker for the matchup pages. Same gate as /matchup/[gameId]; never indexed. */
export default async function MatchupIndexPage({
  searchParams,
}: {
  searchParams: Promise<{ week?: string }>;
}) {
  if (!isMatchupEnabled()) notFound();
  const { week: requested } = await searchParams;
  const season = publicationScope.season;

  let weeks: number[];
  let games: Game[];
  let week: number | null;
  if (process.env.CFB_UI_TEST_MODE === "1") {
    weeks = [5];
    week = 5;
    games = protoGames();
  } else {
    const available = (await getAvailableWeeks(season)).filter((w) => isPublishedWeek(season, w));
    weeks = available;
    const current = await getCurrentWeek();
    week = pickWeek(requested, available, current?.season === season ? current.week : null);
    games =
      week === null
        ? []
        : publicationScope.mode === "predictions"
          ? await getGamesForWeek(season, week)
          : await getMarketGamesForWeek(season, week);
  }
  const days = groupGamesByDay(games);

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        season={season}
        systemName={null}
        updatedAt={null}
        publicationMode={publicationScope.mode}
        allowedSeasons={publicationScope.allowedSeasons}
      />
      <main className="mx-auto w-full max-w-4xl flex-1 space-y-6 px-4 py-6">
        <div className="space-y-1">
          <h1 className="text-xl font-bold tracking-tight text-ink">Matchups</h1>
          <p className="text-sm text-ink-muted">
            Pre-game team stats for every game. Pick a game to open its breakdown.
          </p>
        </div>

        <nav aria-label="Week" className="flex flex-wrap gap-2">
          {weeks.map((w) => (
            <Link
              key={w}
              href={`/matchup?week=${w}`}
              aria-current={w === week ? "page" : undefined}
              className={
                w === week
                  ? "rounded-lg border border-accent bg-accent/15 px-3 py-1.5 text-xs font-bold text-accent-ink"
                  : "rounded-lg border border-line bg-surface-elevated px-3 py-1.5 text-xs font-medium text-ink hover:border-accent"
              }
            >
              Week {w}
            </Link>
          ))}
        </nav>

        {days.length === 0 ? (
          <p className="rounded-2xl border border-line bg-surface-card p-6 text-sm text-ink-muted">
            No games for this week.
          </p>
        ) : (
          days.map((day) => (
            <section key={day.label} aria-label={day.label} className="space-y-2">
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
                {day.label} · {day.games.length} {day.games.length === 1 ? "game" : "games"}
              </h2>
              <ul className="divide-y divide-line/60 rounded-2xl border border-line bg-surface-card shadow-sm">
                {day.games.map((game) => (
                  <li key={game.gameId}>
                    <Link
                      href={`/matchup/${game.gameId}`}
                      className="flex items-center gap-3 px-4 py-3 hover:bg-surface-inset/50"
                    >
                      <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                        <span className="flex items-center gap-2 text-sm text-ink">
                          <TeamLogo name={game.awayTeam} px={20} />
                          <span className="truncate">{game.awayTeam}</span>
                        </span>
                        <span className="flex items-center gap-2 text-sm font-semibold text-ink">
                          <TeamLogo name={game.homeTeam} px={20} />
                          <span className="truncate">{game.homeTeam}</span>
                        </span>
                      </span>
                      <span className="shrink-0 text-right text-xs text-ink-muted">
                        {timeFormat.format(game.startDate)} ET
                        <span className="block text-accent-ink">Open →</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))
        )}
      </main>
      <Footer publicationMode={publicationScope.mode} />
    </div>
  );
}
