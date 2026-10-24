import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { publicationScope } from "@/lib/publication";
import { resolveTeam } from "@/lib/teams";
import { getTeamGames, getTeamHistory, getWeeklyRatings, type Rating } from "@/lib/v5";
import { rankSosByTeam } from "@/lib/sos-rank";
import { ratingsFixture } from "@/test/fixtures/ratings";
import { v5RatingFixture } from "@/test/fixtures/publication";
import { Card } from "@/components/ui/Card";
import { Notice } from "@/components/ui/Notice";
import { PageHeading } from "@/components/ui/PageHeading";
import { homeSpreadFromMargin, homeSpreadText } from "@/lib/betting-format";

export const revalidate = 300;

export async function generateMetadata({ params }: { params: Promise<{ team: string }> }): Promise<Metadata> {
  const resolved = resolveTeam((await params).team);
  return resolved ? { title: `${resolved.gameName} · Team page` } : { robots: { index: false, follow: false } };
}

const rankText = (rank: number | null | undefined) => (typeof rank === "number" ? `#${rank}` : "—");

/** Record, SOR rank and the three SOS ranks from the current ratings period, ranked against the whole field. */
function teamSummary(current: Rating[], ratingName: string) {
  const rating = current.find((row) => row.team === ratingName);
  if (!rating) return null;
  const sos = rankSosByTeam(current).get(ratingName);
  const record = typeof rating.wins === "number" && typeof rating.losses === "number" ? `${rating.wins}–${rating.losses}` : "—";
  return [
    ["Record", record],
    ["SOR", rankText(rating.sorRank)],
    ["SOS played", rankText(sos?.played)],
    ["SOS remaining", rankText(sos?.remaining)],
    ["SOS full", rankText(sos?.full)],
  ] as const;
}

export default async function TeamPage({ params }: { params: Promise<{ team: string }> }) {
  const resolved = resolveTeam((await params).team);
  if (!resolved) notFound();
  const { gameName: team, ratingName } = resolved;
  let history: Rating[] = [];
  let games: Awaited<ReturnType<typeof getTeamGames>> = [];
  let current: Rating[] = [];
  let unavailable = false;
  if (process.env.CFB_UI_TEST_MODE === "1") {
    current = ratingsFixture("current").ratings;
    if (ratingName === v5RatingFixture.team) {
      history = [v5RatingFixture];
      games = [{ week: 0, startDate: v5RatingFixture.cutoffUtc,
        homeTeam: team, awayTeam: "Ohio State", predictedMargin: 3.5,
        predictedTotal: 52, homePoints: 24, awayPoints: 21,
        evidenceClass: "replay" }];
    }
  } else {
    try {
      // Rating snapshots store nine teams under legacy names; games use CFBD names.
      [history, games] = await Promise.all([getTeamHistory(2026, ratingName), getTeamGames(2026, team)]);
      // The summary is secondary: a failed ratings read leaves it out instead of hiding the page.
      current = await getWeeklyRatings(2026, "current").then((result) => result.ratings).catch(() => []);
    } catch (error) {
      console.error("V5 team page query failed", error);
      unavailable = true;
    }
  }
  const summary = teamSummary(current, ratingName);
  return (
    <PageShell
      width="narrow"
      header={{ season: 2026, systemName: null, updatedAt: null, allowedSeasons: publicationScope.allowedSeasons }}
      mainClassName="space-y-7 py-8"
    >
      <div><Link href="/ratings" className="text-sm text-accent-ink hover:underline max-sm:inline-flex max-sm:min-h-11 max-sm:items-center">← All ratings</Link><div className="mt-3"><PageHeading title={team}>V5 team state and selected 2026 forecasts.</PageHeading></div>
        {summary && <dl aria-label="Team summary" className="mt-3 grid grid-cols-3 gap-x-3 gap-y-2 sm:grid-cols-5">{summary.map(([label, value]) => <div key={label} className="min-w-0"><dt className="text-[10px] uppercase tracking-wide text-ink-muted">{label}</dt><dd className="font-mono text-sm font-semibold tabular-nums text-ink">{value}</dd></div>)}</dl>}</div>
      {unavailable ? <Notice tone="empty">Team data is temporarily unavailable.</Notice> : <>
        <section aria-labelledby="rating-history"><h2 id="rating-history" className="mb-3 text-lg font-semibold text-ink">Rating history</h2>
          {history.length === 0 ? <Notice tone="empty">No certified rating history is available for this team.</Notice> :
          <Card padding="none" className="overflow-x-auto"><table className="w-full min-w-[540px] text-sm tabular-nums"><thead className="border-b border-line bg-surface-inset text-xs uppercase tracking-wide text-ink-faint"><tr><th scope="col" className="px-4 py-3 text-left">Before game</th><th scope="col" className="px-3 py-3 text-right">Overall</th><th scope="col" className="px-3 py-3 text-right">Offense</th><th scope="col" className="px-3 py-3 text-right">Defense</th><th scope="col" className="px-4 py-3 text-right">Uncertainty</th></tr></thead><tbody>{history.map((rating, index) => <tr key={`${rating.cutoffUtc.toISOString()}-${index}`} className="border-b border-line last:border-0"><td className="px-4 py-3 text-ink">Week {rating.week}</td><td className="px-3 py-3 text-right text-ink">{rating.overallRating.toFixed(2)}</td><td className="px-3 py-3 text-right text-ink-muted">{rating.offenseRating.toFixed(2)}</td><td className="px-3 py-3 text-right text-ink-muted">{rating.defenseRating.toFixed(2)}</td><td className="px-4 py-3 text-right text-ink-muted">±{Math.sqrt(Math.max(0, rating.overallVariance)).toFixed(2)}</td></tr>)}</tbody></table></Card>}
          <p className="mt-2 text-xs text-ink-faint">These are pregame states. Preseason information has more influence early; completed games gain weight as evidence accumulates.</p>
        </section>
        <section aria-labelledby="team-games"><h2 id="team-games" className="mb-3 text-lg font-semibold text-ink">Games and forecasts</h2>
          {games.length === 0 ? <Notice tone="empty">No selected V5 forecasts are available yet.</Notice> :
          <div className="space-y-2">{games.map((game) => <Card as="article" key={`${game.week}-${game.startDate.toISOString()}`}><div className="flex flex-wrap items-center justify-between gap-2"><div><span className="text-xs uppercase tracking-wide text-ink-faint">Week {game.week} · {game.evidenceClass ?? "forecast unavailable"}</span><p className="font-semibold text-ink">{game.awayTeam} at {game.homeTeam}</p></div><div className="text-right text-sm tabular-nums text-ink-muted"><p>Forecast: {homeSpreadText(game.homeTeam, homeSpreadFromMargin(game.predictedMargin))} · {game.predictedTotal?.toFixed(1) ?? "—"} total</p><p>{game.homePoints === null || game.awayPoints === null ? "Not final" : `Final: ${game.awayPoints}–${game.homePoints}`}</p></div></div></Card>)}</div>}
        </section>
      </>}
    </PageShell>
  );
}
