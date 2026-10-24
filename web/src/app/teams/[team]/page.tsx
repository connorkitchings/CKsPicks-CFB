import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { publicationScope } from "@/lib/publication";
import { resolveTeam } from "@/lib/teams";
import { getTeamGames, getTeamHistory, getWeeklyRatings, type Rating } from "@/lib/v5";
import { ratingsFixture } from "@/test/fixtures/ratings";
import { v5RatingFixture } from "@/test/fixtures/publication";
import { Notice } from "@/components/ui/Notice";
import { RatingHistoryTable } from "@/components/teams/RatingHistoryTable";
import { RatingTrend } from "@/components/teams/RatingTrend";
import { UnitProfile } from "@/components/teams/UnitProfile";
import { Disclosure } from "@/components/ui/Disclosure";
import { getTeamPossessionStats, getTeamSeasonStats } from "@/lib/queries";
import { buildUnitRows, type UnitMatchupRow } from "@/lib/team-stats";
import { fixtureRows } from "@/test/fixtures/matchup";
import { teamAbbr } from "@/lib/team-logos";
import { getTeamGameStats, getTeamSeasonRoster, getV5RatingSnapshots } from "@/lib/chart-queries";
import { teamRankHistory } from "@/lib/team-rank-history";
import { buildTeamSummary } from "@/lib/team-summary";
import { TeamHero } from "@/components/teams/TeamHero";
import { TeamResume } from "@/components/teams/TeamResume";
import { chartsRosterFixture } from "@/test/fixtures/charts";
import { teamRankSnapshotsFixture, texasGameStatsFixture, texasGamesFixture } from "@/test/fixtures/team-page";
import { GameLogChart } from "@/components/teams/GameLogChart";
import { TeamSchedule } from "@/components/teams/TeamSchedule";
import { TeamSection } from "@/components/teams/TeamSection";
import { gameLogBars } from "@/lib/team-game-log";
import { isFinal } from "@/lib/team-games";
import type { RatingSnapshotRow, RosterRow, TeamGameRow } from "@/lib/charts";

export const revalidate = 300;

export async function generateMetadata({ params }: { params: Promise<{ team: string }> }): Promise<Metadata> {
  const resolved = resolveTeam((await params).team);
  return resolved ? { title: `${resolved.gameName} · Team page` } : { robots: { index: false, follow: false } };
}

/** The team's offense and defense stats as of `week`, or null when they cannot be read or none are published. */
async function loadUnitRows(team: string, week: number): Promise<UnitMatchupRow[] | null> {
  try {
    const [season, possession] = await Promise.all([getTeamSeasonStats(2026, week, [team]), getTeamPossessionStats(2026, week, [team])]);
    const rows = [...season, ...possession];
    return rows.length === 0 ? null : buildUnitRows(rows, team, team);
  } catch (error) {
    console.error("Team unit stats query failed", error);
    return null;
  }
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
  let gameStats: TeamGameRow[] | null = [];
  let unavailable = false;
  if (process.env.CFB_UI_TEST_MODE === "1") {
    current = ratingsFixture("current").ratings;
    snapshots = teamRankSnapshotsFixture(current);
    roster = chartsRosterFixture;
    if (ratingName === v5RatingFixture.team) {
      history = [v5RatingFixture, { ...v5RatingFixture, week: 1, overallRating: 5.9, cutoffUtc: new Date(v5RatingFixture.cutoffUtc.getTime() + 7 * 864e5) }];
      games = texasGamesFixture;
      gameStats = texasGameStatsFixture;
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
    [current, snapshots, roster, gameStats] = await Promise.all([
      getWeeklyRatings(2026, "current").then((result) => result.ratings).catch(() => []),
      getV5RatingSnapshots(2026).then((rows) => rows ?? []).catch(() => []),
      getTeamSeasonRoster(2026).then((rows) => rows ?? []).catch(() => []),
      getTeamGameStats(2026).catch(() => null),
    ]);
  }
  const nextGame = games.find((game) => !isFinal(game)) ?? null;
  // Stats snapshots cover games completed before a week's slate: the next game's week, else the one after the last game.
  const statsWeek = nextGame ? nextGame.week : games.length > 0 ? games[games.length - 1].week + 1 : null;
  const unitRows = statsWeek === null ? null
    : process.env.CFB_UI_TEST_MODE === "1" ? buildUnitRows(fixtureRows([team], ""), team, team)
    : await loadUnitRows(team, statsWeek);
  const rankHistory = teamRankHistory(snapshots, ratingName);
  const summary = buildTeamSummary(current, ratingName, rankHistory);
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
            <TeamSchedule games={games} team={team} />
            {gameStats === null ? (
              <TeamSection id="team-game-log" title="Game log"><Notice tone="empty">The game log is not available right now.</Notice></TeamSection>
            ) : <GameLogChart bars={gameLogBars(gameStats, [team, ratingName])} />}
          </div>
          <div className="min-w-0 space-y-4">
            <RatingTrend points={rankHistory} />
            {summary && <TeamResume summary={summary} />}
            {unitRows ? <UnitProfile rows={unitRows} /> : (
              <TeamSection id="team-unit-profile" title="Unit profile"><Notice tone="empty">Unit stats are not available right now.</Notice></TeamSection>
            )}
            {history.length > 0 && (
              <Disclosure title="Weekly ratings">
                <RatingHistoryTable history={history} />
                <p className="mt-2 text-xs text-ink-faint">These are pregame states. Preseason information has more influence early; completed games gain weight as evidence accumulates.</p>
              </Disclosure>
            )}
          </div>
        </div>
      )}
    </PageShell>
  );
}
