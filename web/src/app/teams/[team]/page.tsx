import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { publicationScope } from "@/lib/publication";
import { resolveTeam } from "@/lib/teams";
import { getTeamGames, getTeamHistory, getWeeklyRatings, type Rating } from "@/lib/v5";
import { competitionRanks, rankSosByTeam } from "@/lib/sos-rank";
import { ratingsFixture } from "@/test/fixtures/ratings";
import { v5RatingFixture } from "@/test/fixtures/publication";
import { Card } from "@/components/ui/Card";
import { Notice } from "@/components/ui/Notice";
import { RatingHistoryTable } from "@/components/teams/RatingHistoryTable";
import { RatingSparkline } from "@/components/teams/RatingSparkline";
import TeamLogo from "@/components/TeamLogo";
import { ratingText, StatGrid, type StatCell } from "@/components/ratings/StatGrid";
import { teamAbbr } from "@/lib/team-logos";
import { MatchupButton } from "@/components/MatchupLinks";
import { MatchupRowLink } from "@/components/teams/MatchupRowLink";
import { TeamGameRow } from "@/components/teams/TeamGameRow";
import { isFinal } from "@/lib/team-games";

export const revalidate = 300;

export async function generateMetadata({ params }: { params: Promise<{ team: string }> }): Promise<Metadata> {
  const resolved = resolveTeam((await params).team);
  return resolved ? { title: `${resolved.gameName} · Team page` } : { robots: { index: false, follow: false } };
}

const rankText = (rank: number | null | undefined) => (typeof rank === "number" ? `#${rank}` : "—");

/** Record, ratings and ranks from the current ratings period, ranked against the whole field. */
function teamSummary(current: Rating[], ratingName: string) {
  const index = current.findIndex((row) => row.team === ratingName);
  const rating = current[index];
  if (!rating) return null;
  const sos = rankSosByTeam(current).get(ratingName);
  const overallRank = competitionRanks(current.map((row) => row.overallRating))[index];
  const record = typeof rating.wins === "number" && typeof rating.losses === "number" ? `${rating.wins}–${rating.losses}` : null;
  const cells: StatCell[] = [
    { label: "OFF", title: "Offense rating", value: ratingText(rating.offenseRating) },
    { label: "DEF", title: "Defense rating", value: ratingText(rating.defenseRating) },
    { label: "SOR", title: "Strength of record rank", value: rankText(rating.sorRank) },
    { label: "SOS", title: "Strength of schedule played", value: rankText(sos?.played) },
  ];
  return { record, overall: ratingText(rating.overallRating), overallRank: rankText(overallRank), cells };
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
      history = [v5RatingFixture, { ...v5RatingFixture, week: 1, overallRating: 5.9, cutoffUtc: new Date(v5RatingFixture.cutoffUtc.getTime() + 7 * 864e5) }];
      games = [{ gameId: 1, week: 0, startDate: v5RatingFixture.cutoffUtc,
        homeTeam: team, awayTeam: "Ohio State", predictedMargin: 3.5,
        homeTeamSpreadLine: -2.5, totalLine: 51.5, predictedTotal: 52, homePoints: 24, awayPoints: 21,
        evidenceClass: "replay" },
        { gameId: 2, week: 1, startDate: new Date(v5RatingFixture.cutoffUtc.getTime() + 7 * 864e5),
          homeTeam: "Ohio State", awayTeam: team, homeTeamSpreadLine: -7, totalLine: 55.5, predictedMargin: 6.2, predictedTotal: 54.84,
          homePoints: null, awayPoints: null, evidenceClass: "replay" }];
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
  const nextGame = games.find((game) => !isFinal(game));
  const summary = teamSummary(current, ratingName);
  return (
    <PageShell
      width="slate"
      header={{ season: 2026, systemName: null, updatedAt: null, allowedSeasons: publicationScope.allowedSeasons,
        back: { href: "/ratings", label: "Back to ratings", title: teamAbbr(team) } }}
      mainClassName="space-y-4 py-4 sm:py-8"
    >
      <Link href="/ratings" className="inline-block text-sm text-accent-ink hover:underline max-sm:hidden">← All ratings</Link>
      <Card as="section" aria-label="Team summary" data-testid="team-hero">
        <div className="flex items-center gap-3 sm:gap-4">
          <TeamLogo name={team} px={64} priority className="max-sm:h-12 max-sm:w-12" />
          <div className="min-w-0">
            <h1 className="text-balance text-xl font-bold leading-tight tracking-tight text-ink sm:text-3xl">{team}</h1>
            {summary?.record && <p className="text-sm text-ink-muted" title="Record against FBS teams">{summary.record}</p>}
          </div>
        </div>
        {summary && <div className="mt-3 flex items-baseline justify-between gap-3" title="Overall rating">
          <span className="text-[10px] font-medium uppercase tracking-wide text-ink-muted">Overall</span>
          <span><span className="font-mono text-lg font-bold tabular-nums text-ink">{summary.overall}</span> <span className="font-mono text-sm tabular-nums text-ink-muted" title="Overall rank">{summary.overallRank}</span></span>
        </div>}
        {summary && <StatGrid cells={summary.cells} className="mt-2" />}
      </Card>
      {unavailable ? <Notice tone="empty">Team data is temporarily unavailable.</Notice> : (
        <div className="grid gap-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] sm:items-start">
          <div className="min-w-0 space-y-4">
            <section aria-labelledby="team-games"><h2 id="team-games" className="mb-3 text-lg font-semibold text-ink">Schedule</h2>
              {games.length === 0 ? <Notice tone="empty">No selected V5 forecasts are available yet.</Notice> : <>
                {nextGame && <Card padding="none" className="mb-3" aria-label="Next game"><p className="px-3 pt-2.5 text-[10px] font-medium uppercase tracking-wide text-accent-ink">Next game</p><div className="px-3 pb-1 pt-1"><TeamGameRow game={nextGame} team={team} /></div><div className="flex justify-end px-3 pb-1"><MatchupButton gameId={nextGame.gameId} /></div></Card>}
                <Card padding="none"><ul aria-label="Schedule" className="divide-y divide-line">{games.map((game) => <li key={game.gameId}><MatchupRowLink gameId={game.gameId}><TeamGameRow game={game} team={team} /></MatchupRowLink></li>)}</ul></Card>
              </>}
            </section>
          </div>
          <div className="min-w-0 space-y-4">
            <section aria-labelledby="rating-history"><h2 id="rating-history" className="mb-3 text-lg font-semibold text-ink">Rating history</h2>
              {history.length === 0 ? <Notice tone="empty">No certified rating history is available for this team.</Notice> :
              <><RatingSparkline history={history} /><RatingHistoryTable history={history} /></>}
              <p className="mt-2 text-xs text-ink-faint">These are pregame states. Preseason information has more influence early; completed games gain weight as evidence accumulates.</p>
            </section>
          </div>
        </div>
      )}
    </PageShell>
  );
}
