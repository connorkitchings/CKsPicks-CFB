import { redirect } from "next/navigation";
import {
  getGamesForWeek,
  getMarketGamesForWeek,
  getRunForWeek,
  getScoredWeeks,
  type Game,
} from "@/lib/queries";
import { getV5Performance, type Performance } from "@/lib/v5";
import { selectsV5 } from "@/lib/run-selection";
import { WeeklySlateView } from "@/components/WeeklySlateView";
import { publicationScope, isAllowedSeason } from "@/lib/publication";
import { uiFixture } from "@/test/fixtures/publication";

// Revalidate every 5 minutes (ISR).
export const revalidate = 300;

type SearchParams = Promise<{ season?: string; week?: string; mode?: string; sort?: string }>;

export default async function ResultsPage({
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

  const requestedSeason = params.season ? Number(params.season) : publicationScope.season;
  const season = isAllowedSeason(requestedSeason) ? requestedSeason : publicationScope.season;

  let scoredWeeks: number[] = [];
  try {
    scoredWeeks = await getScoredWeeks(season);
  } catch (err) {
    console.error("Failed to query scored weeks", err);
  }

  const parsedWeek = params.week === undefined ? null : Number(params.week);
  const requestedWeek = parsedWeek !== null && Number.isInteger(parsedWeek) ? parsedWeek : null;

  // If a user asks for an unscored week (e.g. week 5) on /results, redirect to /?week=N
  if (requestedWeek !== null && scoredWeeks.length > 0 && !scoredWeeks.includes(requestedWeek)) {
    redirect(`/?week=${requestedWeek}`);
  }

  const week = requestedWeek ?? (scoredWeeks.length > 0 ? scoredWeeks[scoredWeeks.length - 1] : 0);

  let games: Game[] = [];
  let performance: Performance[] = [];
  let systemName: string | null = null;
  let retrospectiveRepair = false;
  let dbError: string | null = null;

  if (process.env.CFB_UI_TEST_MODE === "1") {
    const fixture = uiFixture(publicationMode, week);
    games = fixture.games;
    if (games[0]?.publicationMode === "predictions") {
      systemName = games[0].systemName;
      performance = selectsV5(games[0].modelId) ? fixture.performance : [];
    }
  } else {
    try {
      if (season > 0 && week >= 0) {
        if (publicationMode === "predictions") {
          const selectedRun = await getRunForWeek(season, week);
          retrospectiveRepair = selectedRun?.modelId === "v5-intended-update-2026-v1"
            && selectedRun.evidenceClass === "replay";
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
      console.error("Results weekly data query failed", err);
      dbError = "Weekly results data is temporarily unavailable.";
    }
  }

  const gamesUpdatedAt = games
    .map((g) => g.updatedAt.getTime())
    .reduce<number>((max, t) => (t > max ? t : max), 0);
  const updatedAt = gamesUpdatedAt > 0 ? new Date(gamesUpdatedAt) : null;

  const initialSort =
    params.sort === "spreadEdge" || params.sort === "totalEdge"
      ? params.sort
      : "kickoff";

  return (
    <WeeklySlateView
      mode="results"
      season={season}
      week={week}
      weeks={scoredWeeks}
      basePath="/results"
      games={games}
      performance={performance}
      systemName={systemName}
      updatedAt={updatedAt}
      publicationMode={publicationMode}
      allowedSeasons={publicationScope.allowedSeasons}
      dbError={dbError}
      retrospectiveRepair={retrospectiveRepair}
      initialSort={initialSort}
      emptyMessage={
        scoredWeeks.length === 0
          ? `No completed or scored weeks have been recorded for the ${season} season yet.`
          : undefined
      }
    />
  );
}
