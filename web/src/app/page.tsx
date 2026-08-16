import {
  getCurrentWeek,
  getGamesForWeek,
  getMarketGamesForWeek,
  getSystemStats,
  getAvailableWeeks,
  type Game,
  type Stats,
} from "@/lib/queries";
import { Header, Footer } from "@/components/Header";
import { RecordBanner } from "@/components/RecordBanner";
import { WeekNav } from "@/components/WeekNav";
import { GamesList } from "@/components/GamesList";
import { publicationScope } from "@/lib/publication";

// Revalidate every 5 minutes (ISR).
export const revalidate = 300;

type SearchParams = Promise<{ season?: string; week?: string }>;

/**
 * Resolve only the server-configured public release scope. Query parameters
 * can choose an allowed week, but cannot expose another season or week.
 */
async function resolveTarget(
  searchParams: SearchParams,
): Promise<{
  season: number;
  week: number;
  weeks: number[];
  activeSeason: number | null;
  activeWeek: number | null;
  currentUpdatedAt: Date | null;
}> {
  const params = await searchParams;
  const current = await getCurrentWeek();
  const activeSeason = current?.season === publicationScope.season
    ? current.season
    : null;
  const activeWeek = activeSeason !== null
    && current !== null
    && publicationScope.weeks.includes(current.week)
    ? current.week
    : null;
  const season = publicationScope.season;
  const availableWeeks = (await getAvailableWeeks(season))
    .filter((week) => publicationScope.weeks.includes(week));
  const requestedWeek = params.week ? Number(params.week) : activeWeek;

  // Invalid URLs and unready future weeks stay within the release boundary.
  let week = publicationScope.weeks.includes(requestedWeek ?? -1)
    ? requestedWeek!
    : activeWeek ?? availableWeeks[availableWeeks.length - 1] ?? publicationScope.weeks[0];
  if (availableWeeks.length > 0 && !availableWeeks.includes(week)) {
    week = availableWeeks[availableWeeks.length - 1];
  }

  return {
    season: season ?? 0,
    week,
    weeks: availableWeeks,
    activeSeason,
    activeWeek,
    currentUpdatedAt: activeWeek !== null ? current?.updatedAt ?? null : null,
  };
}

export default async function Home({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const { season, week, weeks, currentUpdatedAt } = await resolveTarget(
    searchParams,
  );

  let games: Game[] = [];
  let stats: Stats | null = null;
  let dbError: string | null = null;
  let systemName: string | null = null;
  let modelId: string | null = null;
  let runState: string | null = null;

  try {
    if (season > 0 && week >= 0) {
      if (publicationScope.mode === "predictions") {
        [games, stats] = await Promise.all([
          getGamesForWeek(season, week),
          getSystemStats(season),
        ]);
      } else {
        games = await getMarketGamesForWeek(season, week);
      }
      if (games.length > 0 && games[0].publicationMode === "predictions") {
        systemName = games[0].systemName;
        modelId = games[0].modelId;
        runState = games[0].runState;
      }
    }
  } catch (err) {
    console.error("Weekly data query failed", err);
    dbError = "Weekly data is temporarily unavailable.";
  }

  // Most-recent updatedAt among the games in view, falling back to the
  // current_week row's updatedAt when the view is empty (e.g., future week).
  const gamesUpdatedAt = games
    .map((g) => g.updatedAt.getTime())
    .reduce<number>((max, t) => (t > max ? t : max), 0);
  const updatedAt =
    gamesUpdatedAt > 0
      ? new Date(gamesUpdatedAt)
      : currentUpdatedAt;

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        season={season > 0 ? season : null}
        week={season > 0 ? week : null}
        systemName={systemName}
        modelId={modelId}
        updatedAt={updatedAt}
        runState={runState}
        publicationMode={publicationScope.mode}
      />

      <main className="mx-auto w-full max-w-4xl flex-1 space-y-4 px-4 py-6">
        {dbError && (
          <div className="rounded-xl border border-warn-line bg-warn-soft p-4 text-sm text-warn">
            <strong>Database not connected.</strong> Set <code>DATABASE_URL</code>{" "}
            (see <code>web/.env.example</code>) and run the migration in{" "}
            <code>web/db/migrations/0001_init.sql</code>. Then publish a week with{" "}
            <code>scripts/pipeline/publish_to_db.py</code>.
            <p className="mt-2">{dbError}</p>
          </div>
        )}

        {!dbError && !season && (
          <div className="rounded-xl border border-line bg-surface-card p-6 text-center text-sm text-ink-faint">
            No active week has been published yet. Complete the Week 0
            publication workflow to load the approved schedule and market data.
          </div>
        )}

        {season > 0 && (
          <>
            {stats && (
              <RecordBanner season={season} stats={stats} />
            )}

            {weeks.length > 1 && (
              <WeekNav season={season} week={week} weeks={weeks} />
            )}

            {games.length === 0 ? (
              <div className="rounded-xl border border-line bg-surface-card p-6 text-center text-sm text-ink-faint">
                No games loaded for {season} week {week}.
              </div>
            ) : (
              <GamesList games={games} />
            )}
          </>
        )}
      </main>

      <Footer publicationMode={publicationScope.mode} />
    </div>
  );
}
