import { redirect } from "next/navigation";
import type { Metadata } from "next";
import {
  getAvailableWeeks,
  getGamesForWeek,
  getRunForWeek,
  getScoredWeeks,
  type Game,
} from "@/lib/queries";
import { getCurrentRatings, getV5Performance, type Performance } from "@/lib/v5";
import { selectsV5 } from "@/lib/run-selection";
import { publicationScope } from "@/lib/publication";
import { overallRanks, weekRecord } from "@/lib/picks-proto";
import { assertPrototypeEnabled } from "@/lib/proto-gate";
import { Footer } from "@/components/Header";
import { ProtoHeader } from "@/components/picks-proto/ProtoHeader";
import { ProtoResultsRecord } from "@/components/picks-proto/ProtoResultsRecord";
import { ProtoResultsSlate } from "@/components/picks-proto/ProtoResultsSlate";
import { ResultHighlights } from "@/components/picks-proto/ResultHighlights";

// Design prototype for the Results page. Not linked from the site navigation.
export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Results prototype",
  robots: { index: false, follow: false },
};

type SearchParams = Promise<{ week?: string }>;

export default async function ResultsPrototype({ searchParams }: { searchParams: SearchParams }) {
  assertPrototypeEnabled();
  const params = await searchParams;

  const season = publicationScope.season;
  let week = 0;
  let weeks: number[] = [];
  let upcomingWeeks: number[] = [];
  let redirectTo: string | null = null;
  let games: Game[] = [];
  let performance: Performance[] = [];
  let ranks: Record<string, number> = {};
  let error: string | null = null;

  if (process.env.CFB_UI_TEST_MODE === "1") {
    const fx = await import("@/test/fixtures/picks-prototype");
    games = fx.protoResultGames();
    performance = fx.protoPerformance;
    ranks = fx.protoRanks;
    week = 4;
    weeks = [4];
    upcomingWeeks = [5];
  } else if (publicationScope.mode !== "predictions") {
    error = "The prototype needs CFB_PUBLICATION_MODE=predictions.";
  } else {
    try {
      const [scored, available] = await Promise.all([
        getScoredWeeks(season),
        getAvailableWeeks(season),
      ]);
      weeks = scored;
      upcomingWeeks = available.filter((w) => !scored.includes(w));
      const requested = Number(params.week);
      // Same split as the live site: unscored weeks belong on Picks.
      if (Number.isInteger(requested) && upcomingWeeks.includes(requested)) {
        redirectTo = `/test-picks?week=${requested}`;
      }
      week = Number.isInteger(requested) && scored.includes(requested)
        ? requested
        : scored[scored.length - 1] ?? 0;
      if (!redirectTo && scored.length > 0) {
        const run = await getRunForWeek(season, week);
        [games, performance] = await Promise.all([
          getGamesForWeek(season, week),
          selectsV5(run?.modelId) ? getV5Performance(season, week) : Promise.resolve([]),
        ]);
        try {
          ranks = overallRanks(await getCurrentRatings(season));
        } catch {
          ranks = {};
        }
      }
    } catch (err) {
      console.error("Results prototype data query failed", err);
      error = "Weekly results data is temporarily unavailable.";
    }
  }

  // redirect() throws, so it must run outside the try/catch above.
  if (redirectTo) redirect(redirectTo);

  const first = games.find((g) => g.publicationMode === "predictions");
  const updatedAt = games.reduce<Date | null>(
    (max, g) => (max === null || g.updatedAt > max ? g.updatedAt : max),
    null,
  );

  return (
    <div className="flex min-h-screen flex-col">
      <ProtoHeader
        tab="results"
        season={season}
        week={week}
        weeks={weeks}
        otherWeeks={upcomingWeeks}
        systemName={first?.publicationMode === "predictions" ? first.systemName : null}
        runState={first?.publicationMode === "predictions" ? first.runState : null}
        retrospective={first?.publicationMode === "predictions" && first.evidenceClass === "replay"}
        publishedAt={updatedAt}
      />
      <main className="mx-auto w-full max-w-6xl flex-1 space-y-4 px-4 py-6">
        <p role="note" className="rounded-lg border border-warn-line bg-warn-soft px-3 py-2 text-xs text-warn">
          Design prototype at /test-results — same data as Results, new layout. Not linked from the site.
        </p>
        {error ? (
          <div className="rounded-xl border border-warn-line bg-warn-soft p-4 text-sm text-warn">{error}</div>
        ) : weeks.length === 0 ? (
          <div className="rounded-xl border border-line bg-surface-card p-6 text-center text-sm text-ink-faint">
            No completed or scored weeks have been recorded for {season} yet.
          </div>
        ) : (
          <>
            <ProtoResultsRecord week={week} weekRec={weekRecord(games)} performance={performance} />
            <ResultHighlights games={games} />
            <ProtoResultsSlate games={games} ranks={ranks} />
          </>
        )}
      </main>
      <Footer publicationMode="predictions" />
    </div>
  );
}
