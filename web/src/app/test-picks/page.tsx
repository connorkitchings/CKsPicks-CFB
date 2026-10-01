import { redirect } from "next/navigation";
import type { Metadata } from "next";
import {
  getAvailableWeeks,
  getCurrentWeek,
  getGamesForWeek,
  getRunForWeek,
  getScoredWeeks,
  type Game,
} from "@/lib/queries";
import { getCurrentRatings, getV5Performance, type Performance } from "@/lib/v5";
import { selectsV5 } from "@/lib/run-selection";
import { publicationScope } from "@/lib/publication";
import { overallRanks } from "@/lib/picks-proto";
import { assertPrototypeEnabled } from "@/lib/proto-gate";
import { Footer } from "@/components/Header";
import { ProtoHeader } from "@/components/picks-proto/ProtoHeader";
import { ModelRecord } from "@/components/picks-proto/ProtoRecord";
import { ProtoSlate } from "@/components/picks-proto/ProtoSlate";
import { TopLeans } from "@/components/picks-proto/TopLeans";

// Design prototype for the Picks page. Not linked from the site navigation.
export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Picks prototype",
  robots: { index: false, follow: false },
};

type SearchParams = Promise<{ week?: string }>;

export default async function PicksPrototype({ searchParams }: { searchParams: SearchParams }) {
  assertPrototypeEnabled();
  const params = await searchParams;

  const season = publicationScope.season;
  let week = 0;
  let weeks: number[] = [];
  let scoredWeeks: number[] = [];
  let redirectTo: string | null = null;
  let games: Game[] = [];
  let performance: Performance[] = [];
  let ranks: Record<string, number> = {};
  let error: string | null = null;

  if (process.env.CFB_UI_TEST_MODE === "1") {
    const fx = await import("@/test/fixtures/picks-prototype");
    games = fx.protoGames();
    performance = fx.protoPerformance;
    ranks = fx.protoRanks;
    week = 5;
    weeks = [5];
    scoredWeeks = [4];
  } else if (publicationScope.mode !== "predictions") {
    error = "The prototype needs CFB_PUBLICATION_MODE=predictions.";
  } else {
    try {
      const [current, available, scored] = await Promise.all([
        getCurrentWeek(),
        getAvailableWeeks(season),
        getScoredWeeks(season),
      ]);
      scoredWeeks = scored;
      // Same split as the live site: Picks = upcoming/unscored weeks, Results = scored weeks.
      const upcoming = available.filter((w) => !scored.includes(w));
      weeks = upcoming.length > 0 ? upcoming : available;
      const requested = Number(params.week);
      if (Number.isInteger(requested) && scored.includes(requested)) {
        redirectTo = `/results?week=${requested}`;
      }
      week = Number.isInteger(requested) && weeks.includes(requested)
        ? requested
        : current && weeks.includes(current.week)
          ? current.week
          : weeks[weeks.length - 1] ?? 0;
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
    } catch (err) {
      console.error("Prototype data query failed", err);
      error = "Weekly data is temporarily unavailable.";
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
        tab="picks"
        season={season}
        week={week}
        weeks={weeks}
        otherWeeks={scoredWeeks}
        systemName={first?.publicationMode === "predictions" ? first.systemName : null}
        runState={first?.publicationMode === "predictions" ? first.runState : null}
        retrospective={first?.publicationMode === "predictions" && first.evidenceClass === "replay"}
        publishedAt={updatedAt}
      />
      <main className="mx-auto w-full max-w-6xl flex-1 space-y-4 px-4 py-6">
        <p role="note" className="rounded-lg border border-warn-line bg-warn-soft px-3 py-2 text-xs text-warn">
          Design prototype at /test-picks — same data as Picks, new layout. Not linked from the site.
        </p>
        {error ? (
          <div className="rounded-xl border border-warn-line bg-warn-soft p-4 text-sm text-warn">{error}</div>
        ) : (
          <>
            {performance.length > 0 && <ModelRecord performance={performance} />}
            <TopLeans games={games} />
            <ProtoSlate games={games} ranks={ranks} />
          </>
        )}
      </main>
      <Footer publicationMode="predictions" />
    </div>
  );
}
