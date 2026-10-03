import Link from "next/link";
import clsx from "clsx";
import { getRatingPeriods, getWeeklyRatings, type PeriodMeta, type Rating, type RatingPeriod } from "@/lib/v5";
import { v5RatingFixture } from "@/test/fixtures/publication";
import { RatingsView } from "@/components/ratings/RatingsView";

export const revalidate = 300;

type Sort = "overall" | "offense" | "defense";

function buildQuery(params: Record<string, string | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") q.set(k, v);
  }
  return q.toString();
}

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
    ratings = [v5RatingFixture];
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
    <main className="mx-auto w-full max-w-5xl flex-1 space-y-4 px-4 py-3 sm:py-6">
      {/* Title & Description */}
      <div>
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent-ink">
          <span>{season}</span>
          <span className="text-ink-faint">·</span>
          <span>{periodMeta.label}</span>
          <span className="text-ink-faint">·</span>
          <span>V5</span>
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-3xl">Team ratings</h1>
        <p className="mt-1 text-xs text-ink-muted sm:text-sm">
          {periodMeta.description} Higher is better for overall, offense, and defense.
        </p>
      </div>

      {/* Collapsible Methodology Explainer */}
      <details className="group rounded-xl border border-line bg-surface-card transition-all">
        <summary className="flex cursor-pointer items-center justify-between p-3.5 text-xs font-semibold text-ink select-none sm:text-sm">
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent-soft text-[11px] font-bold text-accent-ink">
              ℹ
            </span>
            <span>About V5 possession ratings</span>
          </div>
          <svg
            className="h-4 w-4 text-ink-muted transition-transform group-open:rotate-180"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </summary>
        <div className="border-t border-line px-4 pt-3 pb-4 text-xs text-ink-muted sm:text-sm">
          <p className="leading-relaxed">
            Ratings represent expected <strong>scoring efficiency per possession (PPP)</strong> against an average FBS opponent under standard conditions.
            Both offense and defense are oriented so higher is better: positive offense scores more points per possession, while positive defense holds opponents to fewer.
          </p>
          <p className="mt-2 leading-relaxed">
            Game margin forecasts are derived from possession ratings through a through-2025 Ridge regression bridge with earlier-only non-offense offsets.
            Uncertainty (±) is one rating standard deviation, narrowing smoothly as completed games provide evidence.
          </p>
        </div>
      </details>

      {/* Rating Period Timeline Navigation */}
      <nav
        className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 scrollbar-none"
        aria-label="Ratings timeline"
      >
        <span className="shrink-0 mr-1 text-xs font-semibold text-ink-muted">Timeline:</span>
        {timeline.map((p) => {
          const isActive = period === p.id;
          return (
            <Link
              key={p.id}
              href={`/ratings?${buildQuery({ period: p.id, sort, q: query, season: String(season) })}`}
              aria-current={isActive ? "page" : undefined}
              className={clsx(
                "shrink-0 rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-accent",
                isActive
                  ? "bg-accent text-white shadow-2xs"
                  : "border border-line bg-surface-card text-ink-muted hover:bg-surface-inset"
              )}
            >
              {p.label}
            </Link>
          );
        })}
      </nav>

      {unavailable ? (
        <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted">
          Ratings are temporarily unavailable.
        </p>
      ) : (
        <RatingsView
          ratings={ratings}
          periodMeta={periodMeta}
          season={season}
          initialSort={sort}
          initialQuery={query}
        />
      )}

      {ratings[0] && (
        <p className="text-xs text-ink-faint">
          {period === "preseason"
            ? "Preseason baseline priors before 2026 kickoff. Uncertainty is one rating standard deviation."
            : `Evidence cutoff: ${ratings[0].cutoffUtc.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" })} UTC. Uncertainty is one rating standard deviation.`}
        </p>
      )}
    </main>
  );
}
