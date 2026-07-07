import {
  getCurrentWeek,
  getGamesForWeek,
  getSystemStats,
  getAvailableWeeks,
  type Game,
  type Stats,
} from "@/lib/queries";
import { Header, Footer } from "@/components/Header";
import { RecordBanner } from "@/components/RecordBanner";
import { WeekNav } from "@/components/WeekNav";
import { GamesList } from "@/components/GamesList";

// Revalidate every 5 minutes (ISR).
export const revalidate = 300;

type SearchParams = Promise<{ season?: string; week?: string }>;

/** Parse ?season= / ?week= query params; fall back to the active week. */
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
  const activeSeason = current?.season ?? null;
  const activeWeek = current?.week ?? null;

  const season = params.season ? Number(params.season) : activeSeason;
  const requestedWeek = params.week ? Number(params.week) : activeWeek;

  const weeks = season ? await getAvailableWeeks(season) : [];

  // If the requested week has no data, clamp to the most recent available week.
  let week = requestedWeek ?? 0;
  if (weeks.length > 0 && !weeks.includes(week)) {
    week = weeks[weeks.length - 1];
  }

  return {
    season: season ?? 0,
    week,
    weeks,
    activeSeason,
    activeWeek,
    currentUpdatedAt: current?.updatedAt ?? null,
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

  try {
    if (season && week) {
      [games, stats] = await Promise.all([
        getGamesForWeek(season, week),
        getSystemStats(season),
      ]);
      if (games.length > 0) {
        systemName = games[0].systemName;
        modelId = games[0].modelId;
      }
    }
  } catch (err) {
    dbError =
      err instanceof Error ? err.message : "Unknown error connecting to database.";
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
    <div className="flex min-h-screen flex-col bg-zinc-50 text-zinc-900 dark:bg-black dark:text-zinc-100">
      <Header
        season={season || null}
        week={week || null}
        systemName={systemName}
        modelId={modelId}
        updatedAt={updatedAt}
      />

      <main className="mx-auto w-full max-w-4xl flex-1 space-y-4 px-4 py-6">
        {dbError && (
          <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            <strong>Database not connected.</strong> Set <code>DATABASE_URL</code>{" "}
            (see <code>web/.env.example</code>) and run the migration in{" "}
            <code>web/db/migrations/0001_init.sql</code>. Then publish a week with{" "}
            <code>scripts/pipeline/publish_to_db.py</code>.
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-[11px]">
              {dbError}
            </pre>
          </div>
        )}

        {!dbError && !season && (
          <div className="rounded-xl border border-zinc-200 bg-white p-6 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
            No active week has been published yet. Run{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono dark:bg-zinc-900">
              publish_to_db.py --year 2026 --week 1
            </code>{" "}
            after generating predictions.
          </div>
        )}

        {season > 0 && (
          <>
            {stats && (
              <RecordBanner season={season} stats={stats} />
            )}

            {weeks.length > 0 && (
              <WeekNav season={season} week={week} weeks={weeks} />
            )}

            {games.length === 0 ? (
              <div className="rounded-xl border border-zinc-200 bg-white p-6 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
                No games loaded for {season} week {week}.
              </div>
            ) : (
              <GamesList games={games} />
            )}
          </>
        )}
      </main>

      <Footer />
    </div>
  );
}
