import Link from "next/link";
import { getCurrentRatings, type Rating } from "@/lib/v5";
import { v5RatingFixture } from "@/test/fixtures/publication";

export const revalidate = 300;

type Sort = "overall" | "offense" | "defense";
const fields: Record<Sort, keyof Rating> = {
  overall: "overallRating",
  offense: "offenseRating",
  defense: "defenseRating",
};

export default async function RatingsPage({ searchParams }: {
  searchParams: Promise<{ q?: string; sort?: string }>;
}) {
  const params = await searchParams;
  const sort: Sort = params.sort === "offense" || params.sort === "defense" ? params.sort : "overall";
  const query = (params.q ?? "").trim().slice(0, 80);
  let ratings: Rating[] = [];
  let unavailable = false;
  if (process.env.CFB_UI_TEST_MODE === "1") {
    ratings = [v5RatingFixture];
  } else {
    try {
      ratings = await getCurrentRatings(2026);
    } catch (error) {
      console.error("V5 ratings query failed", error);
      unavailable = true;
    }
  }
  const visible = ratings.filter((rating) => rating.team.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => Number(b[fields[sort]]) - Number(a[fields[sort]]));
  return (
    <main className="mx-auto w-full max-w-4xl flex-1 space-y-6 px-4 py-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">2026 · V5</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight text-ink">Team ratings</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">Higher is better for overall, offense, and defense. Ratings combine preseason evidence with completed games; uncertainty narrows as evidence grows.</p>
      </div>
      <form action="/ratings" className="flex flex-wrap gap-3" role="search">
        <label className="sr-only" htmlFor="team-search">Search team</label>
        <input id="team-search" name="q" defaultValue={query} placeholder="Search team" className="min-w-48 flex-1 rounded-lg border border-line bg-surface-card px-3 py-2 text-sm text-ink" />
        <label className="sr-only" htmlFor="rating-sort">Sort ratings</label>
        <select id="rating-sort" name="sort" defaultValue={sort} className="rounded-lg border border-line bg-surface-card px-3 py-2 text-sm text-ink">
          <option value="overall">Overall</option><option value="offense">Offense</option><option value="defense">Defense</option>
        </select>
        <button className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white">Apply</button>
      </form>
      {unavailable ? <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted">Ratings are temporarily unavailable.</p> :
      visible.length === 0 ? <p className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted">No ratings match this search yet.</p> :
      <div className="overflow-x-auto rounded-xl border border-line bg-surface-card">
        <table className="w-full min-w-[580px] text-sm tabular-nums">
          <caption className="sr-only">Current V5 team ratings</caption>
          <thead className="border-b border-line bg-surface-inset text-xs uppercase tracking-wide text-ink-faint"><tr><th scope="col" className="px-4 py-3 text-left">Team</th><th scope="col" className="px-3 py-3 text-right">Overall</th><th scope="col" className="px-3 py-3 text-right">Offense</th><th scope="col" className="px-3 py-3 text-right">Defense</th><th scope="col" className="px-4 py-3 text-right">Uncertainty</th></tr></thead>
          <tbody>{visible.map((rating) => <tr key={rating.team} className="border-b border-line last:border-0">
            <th scope="row" className="px-4 py-3 text-left font-semibold text-ink"><Link className="hover:text-accent-ink hover:underline" href={`/teams/${encodeURIComponent(rating.team)}`}>{rating.team}</Link></th>
            <td className="px-3 py-3 text-right text-ink">{rating.overallRating.toFixed(2)}</td>
            <td className="px-3 py-3 text-right text-ink-muted">{rating.offenseRating.toFixed(2)}</td>
            <td className="px-3 py-3 text-right text-ink-muted">{rating.defenseRating.toFixed(2)}</td>
            <td className="px-4 py-3 text-right text-ink-muted">±{Math.sqrt(Math.max(0, rating.overallVariance)).toFixed(2)}</td>
          </tr>)}</tbody>
        </table>
      </div>}
      {ratings[0] && <p className="text-xs text-ink-faint">Evidence updated {ratings[0].cutoffUtc.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" })} UTC. Uncertainty is one rating standard deviation.</p>}
    </main>
  );
}
