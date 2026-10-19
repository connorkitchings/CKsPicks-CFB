import { getRatingPeriods, getWeeklyRatings, type PeriodMeta, type Rating, type RatingPeriod } from "@/lib/v5";
import { ratingsFixture } from "@/test/fixtures/ratings";
import { Disclosure } from "@/components/ui/Disclosure";
import { PageHeading } from "@/components/ui/PageHeading";
import { RatingsView } from "@/components/ratings/RatingsView";

export const revalidate = 300;

type Sort = "overall" | "offense" | "defense";

export default async function RatingsPage({ searchParams }: {
  searchParams: Promise<{ q?: string; sort?: string; season?: string; week?: string; period?: string }>;
}) {
  const params = await searchParams;
  const sort: Sort = params.sort === "offense" || params.sort === "defense" ? params.sort : "overall";
  const query = (params.q ?? "").trim().slice(0, 80);
  const requestedSeason = params.season ? Number(params.season) : 2026;
  const season = Number.isInteger(requestedSeason) && requestedSeason > 0 ? requestedSeason : 2026;
  const requestedPeriod = params.period ?? params.week ?? "current";

  let ratings: Rating[] = [];
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
  } else {
    try {
      const result = await getWeeklyRatings(season, requestedPeriod);
      ratings = result.ratings;
      period = result.period;
      periodMeta = result.periodMeta;
      timeline = await getRatingPeriods(season);
    } catch (error) {
      console.error("V5 ratings query failed", error);
      unavailable = true;
    }
  }

  return (
    <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-5xl flex-1 space-y-4 px-4 py-3 sm:py-6">
      <PageHeading title="Team ratings">
        <p className="text-xs font-semibold uppercase tracking-wider text-accent-ink">{season} · {periodMeta.label} · V5</p>
        <p className="mt-1">{periodMeta.description} Higher is better for overall, offense, and defense.</p>
      </PageHeading>

      <Disclosure title="About V5 possession ratings">
        <p className="leading-relaxed">
          Ratings represent expected <strong>scoring efficiency per possession (PPP)</strong> against an average FBS opponent under standard conditions.
          Both offense and defense are oriented so higher is better: positive offense scores more points per possession, while positive defense holds opponents to fewer.
        </p>
        <p className="mt-2 leading-relaxed">
          Game margin forecasts are derived from possession ratings through a through-2025 Ridge regression bridge with earlier-only non-offense offsets.
          Overall uncertainty (±) is one overall rating standard deviation, narrowing smoothly as completed games provide evidence.
        </p>
      </Disclosure>

      {unavailable ? (
        <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted">
          Ratings are temporarily unavailable.
        </p>
      ) : (
        <RatingsView
          key={period}
          period={period}
          timeline={timeline}
          ratings={ratings}
          periodMeta={periodMeta}
          season={season}
          initialSort={sort}
          initialQuery={query}
        />
      )}

      {ratings[0] && (
        <p className="text-xs text-ink-muted">
          {period === "preseason"
            ? "Preseason baseline priors before 2026 kickoff. Overall uncertainty is one overall rating standard deviation."
            : `Evidence cutoff: ${ratings[0].cutoffUtc.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" })} UTC. Overall uncertainty is one overall rating standard deviation.`}
        </p>
      )}
    </main>
  );
}
