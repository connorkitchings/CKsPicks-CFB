import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { publicationScope } from "@/lib/publication";
import { resolveTeam } from "@/lib/teams";
import { getTeamGames, getTeamHistory, getWeeklyRatings, type Rating } from "@/lib/v5";
import { ratingsFixture } from "@/test/fixtures/ratings";
import { v5RatingFixture } from "@/test/fixtures/publication";
import { Card } from "@/components/ui/Card";
import { Notice } from "@/components/ui/Notice";
import { RatingHistoryTable } from "@/components/teams/RatingHistoryTable";
import { RatingSparkline } from "@/components/teams/RatingSparkline";
import { teamAbbr } from "@/lib/team-logos";
import { getTeamSeasonRoster, getV5RatingSnapshots } from "@/lib/chart-queries";
import { teamRankHistory } from "@/lib/team-rank-history";
import { buildTeamSummary } from "@/lib/team-summary";
import { TeamHero } from "@/components/teams/TeamHero";
import { TeamResume } from "@/components/teams/TeamResume";
import { chartsRosterFixture } from "@/test/fixtures/charts";
import { teamRankSnapshotsFixture, texasGamesFixture } from "@/test/fixtures/team-page";
import { MatchupRowLink } from "@/components/teams/MatchupRowLink";
import { TeamGameRow } from "@/components/teams/TeamGameRow";
import { isFinal } from "@/lib/team-games";
import type { RatingSnapshotRow, RosterRow } from "@/lib/charts";

export const revalidate = 300;

export async function generateMetadata({ params }: { params: Promise<{ team: string }> }): Promise<Metadata> {
  const resolved = resolveTeam((await params).team);
  return resolved ? { title: `${resolved.gameName} · Team page` } : { robots: { index: false, follow: false } };
}

export default async function TeamPage({ params }: { params: Promise<{ team: string }> }) {
  const resolved = resolveTeam((await params).team);
  if (!resolved) notFound();
  const { gameName: team, ratingName } = resolved;
  let history: Rating[] = [];
  let games: Awaited<ReturnType<typeof getTeamGames>> = [];
  let current: Rating[] = [];
  let snapshots: RatingSnapshotRow[] = [];
  let roster: RosterRow[] = [];
  let unavailable = false;
  if (process.env.CFB_UI_TEST_MODE === "1") {
    current = ratingsFixture("current").ratings;
    snapshots = teamRankSnapshotsFixture(current);
    roster = chartsRosterFixture;
    if (ratingName === v5RatingFixture.team) {
      history = [v5RatingFixture, { ...v5RatingFixture, week: 1, overallRating: 5.9, cutoffUtc: new Date(v5RatingFixture.cutoffUtc.getTime() + 7 * 864e5) }];
      games = texasGamesFixture;
    }
  } else {
    try {
      // Rating snapshots store nine teams under legacy names; games use CFBD names.
      [history, games] = await Promise.all([getTeamHistory(2026, ratingName), getTeamGames(2026, team)]);
    } catch (error) {
      console.error("V5 team page query failed", error);
      unavailable = true;
    }
    // The summary, rank history and conference are secondary: a failed read leaves them out instead of hiding the page.
    [current, snapshots, roster] = await Promise.all([
      getWeeklyRatings(2026, "current").then((result) => result.ratings).catch(() => []),
      getV5RatingSnapshots(2026).then((rows) => rows ?? []).catch(() => []),
      getTeamSeasonRoster(2026).then((rows) => rows ?? []).catch(() => []),
    ]);
  }
  const nextGame = games.find((game) => !isFinal(game)) ?? null;
  const summary = buildTeamSummary(current, ratingName, teamRankHistory(snapshots, ratingName));
  const conference = roster.find((row) => row.team === ratingName || row.team === team)?.conference ?? null;
  return (
    <PageShell
      width="slate"
      header={{ season: 2026, systemName: null, updatedAt: null, allowedSeasons: publicationScope.allowedSeasons,
        back: { href: "/ratings", label: "Back to ratings", title: teamAbbr(team) } }}
      mainClassName="space-y-4 py-4 sm:py-8"
    >
      <Link href="/ratings" className="inline-block text-sm text-accent-ink hover:underline max-sm:hidden">← All ratings</Link>
      <TeamHero team={team} conference={conference} summary={summary} nextGame={nextGame} />
      {unavailable ? <Notice tone="empty">Team data is temporarily unavailable.</Notice> : (
        <div className="grid gap-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] sm:items-start">
          <div className="min-w-0 space-y-4">
            <section aria-labelledby="team-games"><h2 id="team-games" className="mb-3 text-lg font-semibold text-ink">Schedule</h2>
              {games.length === 0 ? <Notice tone="empty">No selected V5 forecasts are available yet.</Notice> :
                <Card padding="none"><ul aria-label="Schedule" className="divide-y divide-line">{games.map((game) => <li key={game.gameId}><MatchupRowLink gameId={game.gameId}><TeamGameRow game={game} team={team} /></MatchupRowLink></li>)}</ul></Card>}
            </section>
          </div>
          <div className="min-w-0 space-y-4">
            <section aria-labelledby="rating-history"><h2 id="rating-history" className="mb-3 text-lg font-semibold text-ink">Rating history</h2>
              {history.length === 0 ? <Notice tone="empty">No certified rating history is available for this team.</Notice> :
              <><RatingSparkline history={history} /><RatingHistoryTable history={history} /></>}
              <p className="mt-2 text-xs text-ink-faint">These are pregame states. Preseason information has more influence early; completed games gain weight as evidence accumulates.</p>
            </section>
            {summary && <TeamResume summary={summary} />}
          </div>
        </div>
      )}
    </PageShell>
  );
}
