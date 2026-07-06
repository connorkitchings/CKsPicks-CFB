import {
  getCurrentWeek,
  getGamesForWeek,
  getSystemStats,
  type Game,
  type Stats,
} from "@/lib/queries";
import { Header, Footer } from "@/components/Header";
import { RecordBanner } from "@/components/RecordBanner";
import { GameRow } from "@/components/GameRow";

// Revalidate every 5 minutes (ISR).
export const revalidate = 300;

export default async function Home() {
  // Gracefully handle DB-not-yet-connected (e.g. first deploy before Neon setup).
  let current: { season: number; week: number } | null = null;
  let games: Game[] = [];
  let stats: Stats | null = null;
  let dbError: string | null = null;
  let systemName: string | null = null;
  let modelId: string | null = null;

  try {
    current = await getCurrentWeek();
    if (current) {
      [games, stats] = await Promise.all([
        getGamesForWeek(current.season, current.week),
        getSystemStats(current.season),
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

  const generatedAt = new Date();

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 text-zinc-900 dark:bg-black dark:text-zinc-100">
      <Header
        season={current?.season ?? null}
        week={current?.week ?? null}
        systemName={systemName}
        modelId={modelId}
        generatedAt={generatedAt}
      />

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6">
        {dbError && (
          <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            <strong>Database not connected.</strong> Set <code>DATABASE_URL</code>{" "}
            (see <code>web/.env.example</code>) and run the migration in{" "}
            <code>web/db/migrations/0001_init.sql</code>. Then publish a week with{" "}
            <code>scripts/pipeline/publish_to_db.py</code>.
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-[11px]">
              {dbError}
            </pre>
          </div>
        )}

        {!dbError && !current && (
          <div className="rounded-xl border border-zinc-200 bg-white p-6 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
            No active week has been published yet. Run{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono dark:bg-zinc-900">
              publish_to_db.py --year 2026 --week 1
            </code>{" "}
            after generating predictions.
          </div>
        )}

        {current && (
          <>
            <div className="mb-4">
              <RecordBanner season={current.season} stats={stats} />
            </div>

            {games.length === 0 ? (
              <div className="rounded-xl border border-zinc-200 bg-white p-6 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
                No games loaded for {current.season} week {current.week}.
              </div>
            ) : (
              <ul className="space-y-3">
                {games.map((g) => (
                  <GameRow key={g.gameId} game={g} />
                ))}
              </ul>
            )}
          </>
        )}
      </main>

      <Footer />
    </div>
  );
}
