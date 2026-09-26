import Link from "next/link";
import clsx from "clsx";
import { getWeeklyRatings, RATING_PERIODS, type Rating, type RatingPeriod } from "@/lib/v5";
import { v5RatingFixture } from "@/test/fixtures/publication";

export const revalidate = 300;

type Sort = "overall" | "offense" | "defense";
const fields: Record<Sort, keyof Rating> = {
  overall: "overallRating",
  offense: "offenseRating",
  defense: "defenseRating",
};

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
  const requestedPeriod = params.period ?? params.week ?? "post-3";

  let ratings: Rating[] = [];
  let period: RatingPeriod = "post-3";
  let periodMeta = RATING_PERIODS[0];
  let unavailable = false;

  if (process.env.CFB_UI_TEST_MODE === "1") {
    ratings = [v5RatingFixture];
  } else {
    try {
      const result = await getWeeklyRatings(season, requestedPeriod);
      ratings = result.ratings;
      period = result.period;
      periodMeta = result.periodMeta;
    } catch (error) {
      console.error("V5 ratings query failed", error);
      unavailable = true;
    }
  }

  const visible = ratings
    .filter((rating) => rating.team.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => Number(b[fields[sort]]) - Number(a[fields[sort]]));

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 space-y-6 px-4 py-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">
          {season} · {periodMeta.label} · V5
        </p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight text-ink">Team ratings</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">
          {periodMeta.description} Higher is better for overall, offense, and defense.
        </p>
      </div>

      <section aria-labelledby="methodology-heading" className="rounded-xl border border-line bg-surface-card p-5 text-sm">
        <h2 id="methodology-heading" className="font-semibold text-ink">About V5 possession ratings</h2>
        <p className="mt-2 text-ink-muted leading-relaxed">
          Ratings represent expected <strong>scoring efficiency per possession (PPP)</strong> against an average FBS opponent under standard conditions.
          Both offense and defense are oriented so higher is better: positive offense scores more points per possession, while positive defense holds opponents to fewer.
        </p>
        <p className="mt-2 text-ink-muted leading-relaxed">
          Game margin forecasts are derived from possession ratings through a through-2025 Ridge regression bridge with earlier-only non-offense offsets.
          Uncertainty (±) is one rating standard deviation, narrowing smoothly as completed games provide evidence.
        </p>
      </section>

      {/* Rating Period Navigation Tabs */}
      <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="Ratings timeline">
        <span className="mr-1 text-xs font-semibold text-ink-muted">Ratings timeline:</span>
        {RATING_PERIODS.map((p) => {
          const isActive = period === p.id;
          return (
            <Link
              key={p.id}
              href={`/ratings?${buildQuery({ period: p.id, sort, q: query, season: String(season) })}`}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-accent",
                isActive
                  ? "bg-accent text-white shadow-xs"
                  : "border border-line bg-surface-card text-ink-muted hover:bg-surface-inset"
              )}
            >
              {p.label}
            </Link>
          );
        })}
      </div>

      {/* Search and Sort Form */}
      <form action="/ratings" className="flex flex-wrap gap-3" role="search">
        <input type="hidden" name="period" value={period} />
        {params.season && <input type="hidden" name="season" value={String(season)} />}
        <label className="sr-only" htmlFor="team-search">Search team</label>
        <input
          id="team-search"
          name="q"
          defaultValue={query}
          placeholder="Search team"
          className="min-w-48 flex-1 rounded-lg border border-line bg-surface-card px-3 py-2 text-sm text-ink focus-visible:outline-2 focus-visible:outline-accent"
        />
        <label className="sr-only" htmlFor="rating-sort">Sort ratings</label>
        <select
          id="rating-sort"
          name="sort"
          defaultValue={sort}
          className="rounded-lg border border-line bg-surface-card px-3 py-2 text-sm text-ink focus-visible:outline-2 focus-visible:outline-accent"
        >
          <option value="overall">Overall</option>
          <option value="offense">Offense</option>
          <option value="defense">Defense</option>
        </select>
        <button
          type="submit"
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          Apply
        </button>
      </form>

      {unavailable ? (
        <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted">
          Ratings are temporarily unavailable.
        </p>
      ) : ratings.length === 0 ? (
        <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted">
          No certified ratings published for the {season} season yet.
        </p>
      ) : visible.length === 0 ? (
        <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted">
          No teams match &ldquo;{query}&rdquo;.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface-card">
          <table className="w-full min-w-[580px] text-sm tabular-nums">
            <caption className="sr-only">
              {season} {periodMeta.label} V5 team ratings
            </caption>
            <thead className="border-b border-line bg-surface-inset text-xs uppercase tracking-wide text-ink-faint">
              <tr>
                <th scope="col" className="w-12 px-3 py-3 text-center">#</th>
                <th scope="col" className="px-4 py-3 text-left">Team</th>
                <th scope="col" className="px-3 py-3 text-right">Overall</th>
                <th scope="col" className="px-3 py-3 text-right">Offense</th>
                <th scope="col" className="px-3 py-3 text-right">Defense</th>
                <th scope="col" className="px-4 py-3 text-right">Uncertainty</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((rating, index) => (
                <tr key={rating.team} className="border-b border-line last:border-0 hover:bg-surface-inset/50">
                  <td className="px-3 py-3 text-center font-mono text-xs text-ink-faint">{index + 1}</td>
                  <th scope="row" className="px-4 py-3 text-left font-semibold text-ink">
                    <Link
                      className="hover:text-accent-ink hover:underline focus-visible:rounded focus-visible:outline-2 focus-visible:outline-accent"
                      href={`/teams/${encodeURIComponent(rating.team)}`}
                    >
                      {rating.team}
                    </Link>
                  </th>
                  <td className="px-3 py-3 text-right font-medium text-ink">{rating.overallRating.toFixed(2)}</td>
                  <td className="px-3 py-3 text-right text-ink-muted">{rating.offenseRating.toFixed(2)}</td>
                  <td className="px-3 py-3 text-right text-ink-muted">{rating.defenseRating.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right text-ink-faint">±{Math.sqrt(Math.max(0, rating.overallVariance)).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
