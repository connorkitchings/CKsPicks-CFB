import {
  getCurrentWeek,
  getGamesForWeek,
  getMarketGamesForWeek,
  getAvailableWeeks,
  getRunForWeek,
  type Game,
} from "@/lib/queries";
import { getV5Performance, type Performance } from "@/lib/v5";
import { selectsV5 } from "@/lib/run-selection";
import { Header, Footer } from "@/components/Header";
import { V5PerformanceBanner } from "@/components/V5PerformanceBanner";
import { WeekNav } from "@/components/WeekNav";
import { GamesList } from "@/components/GamesList";
import { publicationScope, isAllowedSeason } from "@/lib/publication";
import { uiFixture } from "@/test/fixtures/publication";

// Revalidate every 5 minutes (ISR).
export const revalidate = 300;

type SearchParams = Promise<{ season?: string; week?: string; mode?: string }>;

/**
 * Resolve the target season and week from URL params and publication scope.
 * A valid requested week remains the target even when it has no V5 selection.
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
  if (process.env.CFB_UI_TEST_MODE === "1") {
    const requestedWeek = Number(params.week);
    const week = [0, 1, 2].includes(requestedWeek) ? requestedWeek : 0;
    return {
      season: 2026,
      week,
      weeks: [0, 1, 2],
      activeSeason: 2026,
      activeWeek: 0,
      currentUpdatedAt: new Date("2026-08-29T19:30:00.000Z"),
    };
  }
  const current = await getCurrentWeek();
  const activeSeason = current?.season === publicationScope.season
    ? current.season
    : null;
  const activeWeek = activeSeason !== null
    && current !== null
    && publicationScope.weeks.includes(current.week)
    ? current.week
    : null;

  const requestedSeason = params.season ? Number(params.season) : publicationScope.season;
  const season = isAllowedSeason(requestedSeason) ? requestedSeason : publicationScope.season;

  const allAvailableWeeks = await getAvailableWeeks(season);
  const isHistoricalSeason = season !== publicationScope.season;
  const availableWeeks = isHistoricalSeason
    ? allAvailableWeeks
    : allAvailableWeeks.filter((week) => publicationScope.weeks.includes(week));

  const parsedWeek = params.week === undefined ? null : Number(params.week);
  const requestedWeek = parsedWeek !== null
    && Number.isInteger(parsedWeek)
    && parsedWeek >= 0
    && publicationScope.weeks.includes(parsedWeek)
    ? parsedWeek
    : null;

  const week = requestedWeek
    ?? (activeWeek !== null && availableWeeks.includes(activeWeek) ? activeWeek : null)
    ?? availableWeeks[availableWeeks.length - 1]
    ?? (isHistoricalSeason ? allAvailableWeeks[0] : publicationScope.weeks[0]);

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
  const params = await searchParams;
  // Test fixtures are opt-in at process start; production ignores this query
  // parameter and remains governed exclusively by server environment values.
  // In test mode an explicit param must win in both directions so market-mode
  // checks stay deterministic even when a local env file opts into predictions.
  const testModeParam = params.mode === "predictions" || params.mode === "market"
    ? params.mode
    : null;
  const publicationMode = process.env.CFB_UI_TEST_MODE === "1" && testModeParam
    ? testModeParam
    : publicationScope.mode;
  let targetError = false;
  let target: Awaited<ReturnType<typeof resolveTarget>>;
  try {
    target = await resolveTarget(Promise.resolve(params));
  } catch (error) {
    console.error("Weekly target query failed", error);
    targetError = true;
    const requested = Number(params.week);
    target = {
      season: publicationScope.season,
      week: Number.isInteger(requested) && publicationScope.weeks.includes(requested)
        ? requested : publicationScope.weeks[0],
      weeks: [], activeSeason: null, activeWeek: null, currentUpdatedAt: null,
    };
  }
  const { season, week, weeks, currentUpdatedAt } = target;

  let games: Game[] = [];
  let performance: Performance[] = [];
  let dbError: string | null = targetError ? "Weekly data is temporarily unavailable." : null;
  let systemName: string | null = null;

  if (process.env.CFB_UI_TEST_MODE === "1") {
    const fixture = uiFixture(publicationMode, week);
    games = fixture.games;
    if (games[0]?.publicationMode === "predictions") {
      systemName = games[0].systemName;
      performance = selectsV5(games[0].modelId) ? fixture.performance : [];
    }
  } else if (!targetError) {
    try {
      if (season > 0 && week >= 0) {
        if (publicationMode === "predictions") {
          // The V5 performance banner belongs to weeks whose explicit
          // selection is V5; a legacy V4 fallback week renders its own
          // record without it.
          const selectedRun = await getRunForWeek(season, week);
          [games, performance] = await Promise.all([
            getGamesForWeek(season, week),
            selectsV5(selectedRun?.modelId)
              ? getV5Performance(season, week)
              : Promise.resolve([]),
          ]);
        } else {
          games = await getMarketGamesForWeek(season, week);
        }
        if (games.length > 0 && games[0].publicationMode === "predictions") {
          systemName = games[0].systemName;
        }
      }
    } catch (err) {
      console.error("Weekly data query failed", err);
      dbError = "Weekly data is temporarily unavailable.";
    }
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
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface-card focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-ink focus:shadow-lg"
      >
        Skip to main content
      </a>
      <Header
        season={season > 0 ? season : null}
        systemName={systemName}
        updatedAt={updatedAt}
        publicationMode={publicationMode}
        allowedSeasons={publicationScope.allowedSeasons}
      />

      <main id="main-content" className="mx-auto w-full max-w-4xl flex-1 space-y-4 px-4 py-6">
        {dbError && (
          <div className="rounded-xl border border-warn-line bg-warn-soft p-4 text-sm text-warn">
            Forecast data is temporarily unavailable. Please try again shortly.
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
            {publicationMode === "predictions" && <V5PerformanceBanner performance={performance} />}

            {weeks.length > 1 && (
              <WeekNav season={season} week={week} weeks={weeks} />
            )}

            {publicationMode === "predictions" && (
              <p className="px-1 text-xs text-ink-faint">
                Market consensus varies by sportsbook; edge shows the model&rsquo;s difference.
              </p>
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

      <Footer publicationMode={publicationMode} />
    </div>
  );
}
