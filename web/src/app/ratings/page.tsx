import { getTeamSeasonRoster } from "@/lib/chart-queries";
import type { RosterRow } from "@/lib/conferences";
import { getRatingPeriods, getWeeklyRatings, type PeriodMeta, type Rating, type RatingPeriod } from "@/lib/v5";
import { ratingsFixture, ratingsRosterFixture } from "@/test/fixtures/ratings";
import { parseRatingsSort } from "@/lib/sos-rank";
import { publicationScope } from "@/lib/publication";
import { Header, Footer } from "@/components/Header";
import { Disclosure } from "@/components/ui/Disclosure";
import { Notice } from "@/components/ui/Notice";
import { PageHeading } from "@/components/ui/PageHeading";
import { RatingsView, type RatingRow } from "@/components/ratings/RatingsView";

export const revalidate = 300;

export default async function RatingsPage({ searchParams }: {
  searchParams: Promise<{ q?: string; conf?: string; sort?: string; dir?: string; season?: string; week?: string; period?: string }>;
}) {
  const params = await searchParams;
  const { sort, dir } = parseRatingsSort(params.sort, params.dir);
  const query = (params.q ?? "").trim().slice(0, 80);
  const conference = (params.conf ?? "all").trim().slice(0, 40) || "all";
  const requestedSeason = params.season ? Number(params.season) : 2026;
  const season = Number.isInteger(requestedSeason) && requestedSeason > 0 ? requestedSeason : 2026;
  const requestedPeriod = params.period ?? params.week ?? "current";

  let ratings: Rating[] = [];
  let roster: RosterRow[] = [];
  let period: RatingPeriod = "current";
  let periodMeta: PeriodMeta = {
    id: "current",
    label: "Current",
    shortLabel: "Current",
    description: "Latest frozen team ratings (active model state).",
  };
  let timeline: PeriodMeta[] = [];
  let unavailable = false;

  if (process.env.CFB_UI_TEST_MODE === "1") {
    ({ ratings, period, periodMeta, timeline } = ratingsFixture(requestedPeriod));
    roster = ratingsRosterFixture;
  } else {
    try {
      const [result, loadedTimeline, loadedRoster] = await Promise.all([
        getWeeklyRatings(season, requestedPeriod),
        getRatingPeriods(season),
        getTeamSeasonRoster(season).catch(() => null),
      ]);
      ratings = result.ratings;
      period = result.period;
      periodMeta = result.periodMeta;
      timeline = loadedTimeline;
      roster = loadedRoster ?? [];
    } catch (error) {
      console.error("V5 ratings query failed", error);
      unavailable = true;
    }
  }

  const ratingRows: RatingRow[] = ratings.map((r) => ({
    team: r.team,
    overallRating: r.overallRating,
    offenseRating: r.offenseRating,
    defenseRating: r.defenseRating,
    wins: r.wins,
    losses: r.losses,
    sosPlayedAverage: r.sosPlayedAverage,
    sosRemainingAverage: r.sosRemainingAverage,
    sosFullAverage: r.sosFullAverage,
    sor: r.sor,
    sorRank: r.sorRank,
  }));

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        season={season}
        systemName={null}
        updatedAt={null}
        publicationMode={publicationScope.mode}
        allowedSeasons={publicationScope.allowedSeasons}
        width="wide"
      />
      <main id="main-content" tabIndex={-1} className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-4 px-4 py-3 sm:py-6">
        {/* Phones: the app bar names the page and the summary line carries the period, so the heading is screen-reader only. */}
        <div className="max-sm:sr-only">
          <PageHeading title="Team ratings">
            <p className="hidden text-xs font-semibold uppercase tracking-wider text-accent-ink sm:block">{season} · {periodMeta.label} · V5</p>
            <p className="mt-1 hidden sm:block">{periodMeta.description} Higher is better for overall, offense, and defense.</p>
          </PageHeading>
        </div>

        {/* Phones: the disclosure follows the list and the cutoff note. */}
        <Disclosure title="About V5 possession ratings" className="max-sm:order-last">
          {/* Phones keep the summary sentence here instead of above the controls. */}
          <p className="mb-2 leading-relaxed sm:hidden">{periodMeta.description} Higher is better for overall, offense, and defense.</p>
          <p className="leading-relaxed">
            Ratings represent expected <strong>scoring efficiency per possession (PPP)</strong> against an average FBS opponent under standard conditions.
            Both offense and defense are oriented so higher is better: positive offense scores more points per possession, while positive defense holds opponents to fewer.
          </p>
          <p className="mt-2 leading-relaxed">
            Game margin forecasts are derived from possession ratings through a through-2025 Ridge regression bridge with earlier-only non-offense offsets.
          </p>
        </Disclosure>

        {unavailable ? (
          <Notice tone="empty">Ratings are temporarily unavailable.</Notice>
        ) : (
          <RatingsView
            key={period}
            period={period}
            timeline={timeline.map(({ id, label }) => ({ id, label }))}
            ratings={ratingRows}
            roster={roster}
            periodMeta={{ label: periodMeta.label }}
            season={season}
            initialSort={sort}
            initialDirection={dir}
            initialQuery={query}
            initialConference={conference}
          />
        )}

        {ratings[0] && (
          <p className="text-xs text-ink-muted max-sm:order-last">
            {period === "preseason"
              ? "Preseason baseline priors before 2026 kickoff."
              : `Evidence cutoff: ${ratings[0].cutoffUtc.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" })} UTC.`}
          </p>
        )}
      </main>
      <Footer publicationMode={publicationScope.mode} width="wide" />
    </div>
  );
}
