import { redirect } from "next/navigation";
import {
  getAvailableWeeks,
  getBiggestEdgesRecord,
  getCurrentWeek,
  getScoredWeeks,
} from "@/lib/queries";
import { SlateView } from "@/components/slate/SlateView";
import { topLeansRecord, type Tally } from "@/lib/slate";
import { publicationScope } from "@/lib/publication";
import {
  isUiTestMode,
  loadSlateData,
  slateSort,
  slatePublicationMode,
  slateSeason,
  slateUpdatedAt,
  type SlateSearchParams,
} from "@/lib/slate-page";

// Revalidate every 5 minutes (ISR).
export const revalidate = 300;

/**
 * Resolve the target season and week from URL params and publication scope.
 * Scored historical weeks are automatically redirected to /results.
 */
async function resolveTarget(
  searchParams: SlateSearchParams,
): Promise<{
  season: number;
  week: number;
  weeks: number[];
  activeSeason: number | null;
  activeWeek: number | null;
  currentUpdatedAt: Date | null;
}> {
  const params = await searchParams;
  if (isUiTestMode()) {
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

  const season = slateSeason(params);

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
  if (
    activeWeek !== null &&
    !scoredWeeks.includes(activeWeek) &&
    !upcomingWeeks.includes(activeWeek)
  ) {
    upcomingWeeks.push(activeWeek);
    upcomingWeeks.sort((a, b) => a - b);
  }
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
  searchParams: SlateSearchParams;
}) {
  const params = await searchParams;
  const publicationMode = slatePublicationMode(params);

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
  const { season } = target;

  const data = await loadSlateData({
    view: "picks",
    season,
    week: target.week,
    publicationMode,
    dbError: targetError ? "Weekly data is temporarily unavailable." : null,
  });
  const week = data.fixtureWeek?.week ?? target.week;
  const weeks = data.fixtureWeek?.weeks ?? target.weeks;
  const { games } = data;

  let biggestEdges: Tally | null = null;
  if (publicationMode === "predictions" && !data.dbError) {
    if (isUiTestMode()) {
      const fx = await import("@/test/fixtures/slate");
      biggestEdges = topLeansRecord([fx.slateResults().games]);
    } else if (season > 0) {
      try {
        biggestEdges = await getBiggestEdgesRecord(season);
      } catch (err) {
        console.error("Biggest edges record query failed", err);
      }
    }
  }

  const firstPrediction = games.find((g) => g.publicationMode === "predictions");

  return (
    <SlateView
      mode="picks"
      season={season}
      week={week}
      weeks={weeks}
      basePath="/"
      games={games}
      roster={data.roster}
      performance={data.performance}
      topLeansRecord={biggestEdges}
      systemName={data.systemName}
      runState={firstPrediction?.runState ?? null}
      retrospective={false}
      updatedAt={slateUpdatedAt(games, target.currentUpdatedAt)}
      publicationMode={publicationMode}
      allowedSeasons={publicationScope.allowedSeasons}
      dbError={data.dbError}
      retrospectiveRepair={data.retrospectiveRepair}
      displayOnlyNotice={data.displayOnlyText}
      initialSort={slateSort(params)}
    />
  );
}
