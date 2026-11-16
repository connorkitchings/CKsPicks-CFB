import type { Metadata } from "next";
import { getTeamSeasonRoster } from "@/lib/chart-queries";
import type { RosterRow } from "@/lib/conferences";
import { getRatingAnalysisHistory, getRatingPeriods, getWeeklyRatings } from "@/lib/v5";
import { analysisPeriod, boundedRatingHistory, type RatingHistoryPeriod } from "@/lib/team-analysis";
import { normalizeRatingPeriod } from "@/lib/rating-request";
import { ratingsFixture, ratingsRosterFixture } from "@/test/fixtures/ratings";
import { publicationScope, resolveSeasonParam } from "@/lib/publication";
import { Header, Footer } from "@/components/Header";
import { Notice } from "@/components/ui/Notice";
import { PageHeading } from "@/components/ui/PageHeading";
import { TeamsHub } from "@/components/ratings/TeamsHub";
import { etDateYearTime } from "@/lib/time-et";

export const revalidate = 300;
export const metadata: Metadata = { title: "Teams · Stratum CFB", description: "Explore team strength, weekly trends, résumé and same-period comparisons." };
export default async function TeamsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const season = resolveSeasonParam(typeof params.season === "string" ? params.season : undefined, publicationScope.season);
  const requested = typeof params.period === "string" ? params.period : typeof params.week === "string" ? params.week : "current";
  let current: RatingHistoryPeriod = { period: { id: "current", label: "Current" }, ratings: [] };
  let history: RatingHistoryPeriod[] = [];
  let timeline: { id: string; label: string }[] = [];
  let roster: RosterRow[] = [];
  let unavailable = false;
  if (process.env.CFB_UI_TEST_MODE === "1") {
    const fixture = ratingsFixture(requested);
    current = analysisPeriod(fixture.periodMeta, fixture.ratings);
    history = boundedRatingHistory(fixture.timeline.map((meta) => {
      const { ratings } = ratingsFixture(meta.id);
      return analysisPeriod(meta, ratings);
    }), current);
    timeline = fixture.timeline.map((meta) => ({ id: meta.id, label: meta.postWeek === undefined ? meta.label : `Through Week ${meta.postWeek}` }));
    roster = ratingsRosterFixture;
  } else {
    try {
      const [periods, loadedRoster] = await Promise.all([getRatingPeriods(season), getTeamSeasonRoster(season).catch(() => null)]);
      const result = await getWeeklyRatings(season, normalizeRatingPeriod(requested, periods.map((meta) => meta.id)));
      current = analysisPeriod(result.periodMeta, result.ratings);
      history = await getRatingAnalysisHistory(season, result.period).catch(() => [current]);
      timeline = periods.map((meta) => ({ id: meta.id, label: meta.postWeek === undefined ? meta.label : `Through Week ${meta.postWeek}` }));
      roster = loadedRoster ?? [];
    } catch (error) {
      console.error("Teams analysis query failed", error);
      unavailable = true;
    }
  }
  return <div className="flex min-h-screen flex-col"><Header season={season} systemName={null} updatedAt={null} publicationMode={publicationScope.mode} allowedSeasons={publicationScope.allowedSeasons} width="wide" /><main id="main-content" tabIndex={-1} className="mx-auto flex w-full max-w-[1200px] flex-1 flex-col gap-6 px-4 pt-5 pb-8 sm:px-6 sm:py-10"><PageHeading title="Teams"><p className="max-w-3xl">Understand team strength, see what changed, and compare what each team has accomplished.</p><p className="mt-2 text-xs font-semibold text-ink-muted">{season} · V5 · {current.period.label}</p></PageHeading>{unavailable ? <Notice tone="empty">Team ratings are temporarily unavailable.</Notice> : <TeamsHub current={current} history={history} timeline={timeline} roster={roster} season={season} />}{current.period.cutoffUtc && <p className="text-xs text-ink-muted">Evidence cutoff: {etDateYearTime(new Date(current.period.cutoffUtc))}. Ratings reflect the selected certified snapshot.</p>}</main><Footer publicationMode={publicationScope.mode} width="wide" /></div>;
}
