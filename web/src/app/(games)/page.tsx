import {
  getAvailableWeeks,
  getBiggestEdgesRecord,
  getCurrentWeek,
} from "@/lib/queries";
import { SlateView } from "@/components/slate/SlateView";
import { isRetrospective, topLeansRecord, type Tally } from "@/lib/slate";
import { publicationScope } from "@/lib/publication";
import {
  isUiTestMode,
  loadSlateData,
  pageNow,
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
 * Every available week is browsable, plus the active week; the default is the
 * requested week, else the active week.
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
    // Market fixtures keep their own week list; prediction fixtures cover a final,
    // an upcoming and a partly graded week.
    const market = slatePublicationMode(params) === "market";
    const weeks = market ? [0, 1, 2] : [4, 5, 6];
    const activeWeek = market ? 0 : 5;
    return {
      season: 2026,
      week: weeks.includes(requestedWeek) ? requestedWeek : activeWeek,
      weeks,
      activeSeason: 2026,
      activeWeek,
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
  const availableWeeks = await getAvailableWeeks(season);
  const weeks = activeWeek !== null && !availableWeeks.includes(activeWeek)
    ? [...availableWeeks, activeWeek].sort((a, b) => a - b)
    : availableWeeks;

  const parsedWeek = params.week === undefined ? null : Number(params.week);
  const requestedWeek = parsedWeek !== null
    && Number.isInteger(parsedWeek)
    && parsedWeek >= 0
    && publicationScope.weeks.includes(parsedWeek)
    ? parsedWeek
    : null;

  const week = requestedWeek
    ?? activeWeek
    ?? weeks[weeks.length - 1]
    ?? (season !== publicationScope.season ? weeks[0] : publicationScope.weeks[0]);

  return {
    season: season ?? 0,
    week,
    weeks,
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
      // Only after the slate loaded: during an outage this would add a doomed query.
      biggestEdges = await getBiggestEdgesRecord(season).catch((err) => {
        console.error("Biggest edges record query failed", err);
        return null;
      });
    }
  }

  const firstPrediction = games.find((g) => g.publicationMode === "predictions");

  return (
    <SlateView
      season={season}
      week={week}
      weeks={weeks}
      basePath="/"
      games={games}
      roster={data.roster}
      performance={data.performance}
      weekPerformance={data.weekPerformance}
      topLeansRecord={biggestEdges}
      systemName={data.systemName}
      runState={firstPrediction?.runState ?? null}
      retrospective={isRetrospective(data.retrospectiveRepair, firstPrediction)}
      updatedAt={slateUpdatedAt(games, target.currentUpdatedAt)}
      publicationMode={publicationMode}
      allowedSeasons={publicationScope.allowedSeasons}
      dbError={data.dbError}
      retrospectiveRepair={data.retrospectiveRepair}
      displayOnlyNotice={data.displayOnlyText}
      initialSort={slateSort(params)}
      now={pageNow(params)}
    />
  );
}
