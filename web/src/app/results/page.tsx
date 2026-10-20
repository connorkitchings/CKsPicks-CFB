import { redirect } from "next/navigation";
import { getScoredWeeks } from "@/lib/queries";
import { SlateView } from "@/components/slate/SlateView";
import { publicationScope } from "@/lib/publication";
import {
  loadSlateData,
  slatePublicationMode,
  slateSeason,
  slateSort,
  slateUpdatedAt,
  type SlateSearchParams,
} from "@/lib/slate-page";

// Revalidate every 5 minutes (ISR).
export const revalidate = 300;

export default async function ResultsPage({
  searchParams,
}: {
  searchParams: SlateSearchParams;
}) {
  const params = await searchParams;
  const publicationMode = slatePublicationMode(params);
  const season = slateSeason(params);

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

  const requested = requestedWeek ?? (scoredWeeks.length > 0 ? scoredWeeks[scoredWeeks.length - 1] : 0);
  const data = await loadSlateData({ view: "results", season, week: requested, publicationMode });
  const week = data.fixtureWeek?.week ?? requested;
  const weeks = data.fixtureWeek?.weeks ?? scoredWeeks;
  const { games } = data;

  const firstPrediction = games.find((g) => g.publicationMode === "predictions");
  const retrospective = data.retrospectiveRepair || firstPrediction?.evidenceClass === "replay";

  return (
    <SlateView
      mode="results"
      season={season}
      week={week}
      weeks={weeks}
      basePath="/results"
      games={games}
      performance={data.performance}
      systemName={data.systemName}
      runState={firstPrediction?.runState ?? null}
      retrospective={retrospective}
      updatedAt={slateUpdatedAt(games, null)}
      publicationMode={publicationMode}
      allowedSeasons={publicationScope.allowedSeasons}
      dbError={data.dbError}
      retrospectiveRepair={data.retrospectiveRepair}
      displayOnlyNotice={data.displayOnlyText}
      initialSort={slateSort(params)}
      emptyMessage={
        scoredWeeks.length === 0
          ? `No completed or scored weeks have been recorded for the ${season} season yet.`
          : undefined
      }
    />
  );
}
