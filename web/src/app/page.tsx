import { redirect } from "next/navigation";
import {
  getCurrentWeek,
  getGamesForWeek,
  getMarketGamesForWeek,
  getAvailableWeeks,
  getScoredWeeks,
  getRunForWeek,
  type Game,
} from "@/lib/queries";
import { getV5Performance, getTeamRankMap, type Performance } from "@/lib/v5";
import { selectsV5 } from "@/lib/run-selection";
import { WeeklySlateView } from "@/components/WeeklySlateView";
import { publicationScope, isAllowedSeason } from "@/lib/publication";
import { uiFixture } from "@/test/fixtures/publication";

// Revalidate every 5 minutes (ISR).
export const revalidate = 300;

type SearchParams = Promise<{ season?: string; week?: string; mode?: string; sort?: string }>;

/**
 * Resolve the target season and week from URL params and publication scope.
 * Scored historical weeks are automatically redirected to /results.
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

  const [allAvailableWeeks, scoredWeeks] = await Promise.all([
    getAvailableWeeks(season),
    getScoredWeeks(season),
  ]);

  const parsedWeek = params.week === undefined ? null : Number(params.week);
  const requestedWeek = parsedWeek !== null
    && Number.isInteger(parsedWeek)
    && parsedWeek >= 0
    && publicationScope.weeks.includes(parsedWeek)
    ? parsedWeek
    : null;

  // Scored historical weeks belong on the /results archive
  if (requestedWeek !== null && scoredWeeks.includes(requestedWeek)) {
    redirect(`/results?week=${requestedWeek}`);
  }

  // Picks targets the upcoming / unscored slate
  const upcomingWeeks = allAvailableWeeks.filter((w) => !scoredWeeks.includes(w));
  const availableWeeks = upcomingWeeks.length > 0 ? upcomingWeeks : allAvailableWeeks;

  const week = requestedWeek
    ?? (activeWeek !== null && availableWeeks.includes(activeWeek) ? activeWeek : null)
    ?? availableWeeks[availableWeeks.length - 1]
    ?? (season !== publicationScope.season ? allAvailableWeeks[0] : publicationScope.weeks[0]);

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
    if ((error as { digest?: string })?.digest?.startsWith("NEXT_REDIRECT")) {
      throw error;
    }
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
  let ranks: Map<string, number> | undefined;
  let dbError: string | null = targetError ? "Weekly data is temporarily unavailable." : null;
  let systemName: string | null = null;
  let retrospectiveRepair = false;

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
          const selectedRun = await getRunForWeek(season, week);
          retrospectiveRepair = selectedRun?.modelId === "v5-intended-update-2026-v1"
            && selectedRun.evidenceClass === "replay";
          [games, performance, ranks] = await Promise.all([
            getGamesForWeek(season, week),
            selectsV5(selectedRun?.modelId)
              ? getV5Performance(season, week)
              : Promise.resolve([]),
            getTeamRankMap(season).catch(() => new Map<string, number>()),
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

  const gamesUpdatedAt = games
    .map((g) => g.updatedAt.getTime())
    .reduce<number>((max, t) => (t > max ? t : max), 0);
  const updatedAt = gamesUpdatedAt > 0 ? new Date(gamesUpdatedAt) : currentUpdatedAt;

  const initialSort =
    params.sort === "spreadEdge" || params.sort === "totalEdge"
      ? params.sort
      : "kickoff";

  return (
    <WeeklySlateView
      mode="picks"
      season={season}
      week={week}
      weeks={weeks}
      basePath="/"
      games={games}
      ranks={ranks}
      performance={performance}
      systemName={systemName}
      updatedAt={updatedAt}
      publicationMode={publicationMode}
      allowedSeasons={publicationScope.allowedSeasons}
      dbError={dbError}
      retrospectiveRepair={retrospectiveRepair}
      initialSort={initialSort}
    />
  );
}
