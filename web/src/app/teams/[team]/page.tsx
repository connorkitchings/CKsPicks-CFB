import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { publicationScope, resolveSeasonParam } from "@/lib/publication";
import { notFoundMetadata, pageMetadata } from "@/lib/metadata";
import { canonicalTeamSegment, resolveTeam, teamHref } from "@/lib/team-routes";
import { getTeamGames, getTeamHistory, getWeeklyRatings, getRatingAnalysisHistory, type Rating } from "@/lib/v5";
import { ratingsFixture } from "@/test/fixtures/ratings";
import { v5RatingFixture } from "@/test/fixtures/publication";
import { Notice } from "@/components/ui/Notice";
import { RatingHistoryTable } from "@/components/teams/RatingHistoryTable";
import { RatingTrend } from "@/components/teams/RatingTrend";
import { UnitProfile } from "@/components/teams/UnitProfile";
import { Disclosure } from "@/components/ui/Disclosure";
import { getTeamPossessionStats, getTeamSeasonStats } from "@/lib/queries";
import { buildUnitRows, type UnitMatchupRow } from "@/lib/team-stats";
import { YPP_KEYS, fixtureRows } from "@/test/fixtures/matchup";
import { teamAbbr } from "@/lib/team-logos";
import { getTeamGameStats, getTeamSeasonRoster } from "@/lib/chart-queries";
import { analysisPeriod, boundedRatingHistory, nationalRanks, type RatingHistoryPeriod } from "@/lib/team-analysis";
import { getTeamRatingEvidence } from "@/lib/team-rating-evidence";
import { TeamRatingEvidence } from "@/components/teams/TeamRatingEvidence";
import type { UnitRatingBreakdown } from "@/lib/rating-breakdown";
import { buildTeamSummary } from "@/lib/team-summary";
import { TeamHero } from "@/components/teams/TeamHero";
import { TeamResume } from "@/components/teams/TeamResume";
import { chartsRosterFixture } from "@/test/fixtures/charts";
import { texasGameStatsFixture, texasGamesFixture } from "@/test/fixtures/team-page";
import { GameLogChart } from "@/components/teams/GameLogChart";
import { ModelOnTeam } from "@/components/teams/ModelOnTeam";
import { TeamSchedule } from "@/components/teams/TeamSchedule";
import { TeamSection } from "@/components/teams/TeamSection";
import { pageNow, isUiTestMode, type SlateSearchParams } from "@/lib/slate-page";
import { gameLogBars } from "@/lib/team-game-log";
import { isFinal, nextUpcomingGame } from "@/lib/team-games";
import type { RosterRow, TeamGameRow } from "@/lib/charts";

export const revalidate = 300;

export async function generateMetadata({ params }: { params: Promise<{ team: string }> }): Promise<Metadata> {
  const resolved = resolveTeam((await params).team);
  if (!resolved) return notFoundMetadata;
  return pageMetadata(
    resolved.gameName,
    `${resolved.gameName} team rating, weekly trend, schedule and results.`,
    teamHref(resolved.gameName),
  );
}

/**
 * The team's offense and defense stats as of `week`, or the week before when that snapshot is not published
 * yet. Null when they cannot be read or none are published.
 */
async function loadUnitRows(season: number, team: string, week: number): Promise<UnitMatchupRow[] | null> {
  try {
    for (const asOfWeek of week > 0 ? [week, week - 1] : [week]) {
      const [seasonRows, possession] = await Promise.all([getTeamSeasonStats(season, asOfWeek, [team]), getTeamPossessionStats(season, asOfWeek, [team])]);
      const rows = [...seasonRows, ...possession];
      if (rows.length > 0) return buildUnitRows(rows, team, team);
    }
    return null;
  } catch (error) {
    console.error("Team unit stats query failed", error);
    return null;
  }
}

export default async function TeamPage({ params, searchParams }: { params: Promise<{ team: string }>; searchParams: SlateSearchParams }) {
  const segment = (await params).team;
  const resolved = resolveTeam(segment);
  if (!resolved) notFound();
  const canonical = canonicalTeamSegment(segment);
  if (canonical) redirect(`/teams/${canonical}`);
  const { gameName: team, ratingName } = resolved;
  // `?now=` and `?season=` are read only in UI-test mode so production keeps the page statically revalidated.
  const query = isUiTestMode() ? await searchParams : undefined;
  const season = resolveSeasonParam(query?.season, publicationScope.season);
  let history: Rating[] = [];
  let games: Awaited<ReturnType<typeof getTeamGames>> = [];
  let current: Rating[] = [];
  let analysisHistory: RatingHistoryPeriod[] = [];
  let roster: RosterRow[] = [];
  let gameStats: TeamGameRow[] | null = [];
  let unavailable = false;
  if (process.env.CFB_UI_TEST_MODE === "1") {
    current = ratingsFixture("current").ratings;
    const fixture = ratingsFixture("current");
    const selected = analysisPeriod(fixture.periodMeta, current);
    analysisHistory = boundedRatingHistory(fixture.timeline.map((period) => analysisPeriod(period, ratingsFixture(period.id).ratings)), selected);
    roster = chartsRosterFixture;
    if (ratingName === v5RatingFixture.team) {
      history = [v5RatingFixture, { ...v5RatingFixture, week: 1, overallRating: 5.9, cutoffUtc: new Date(v5RatingFixture.cutoffUtc.getTime() + 7 * 864e5) }];
      games = texasGamesFixture;
      gameStats = texasGameStatsFixture;
    }
  } else {
    try {
      // Rating snapshots store nine teams under legacy names; games use CFBD names.
      [history, games] = await Promise.all([getTeamHistory(season, ratingName), getTeamGames(season, team)]);
    } catch (error) {
      console.error("V5 team page query failed", error);
      unavailable = true;
    }
    // The summary, rank history and conference are secondary: a failed read leaves them out instead of hiding the page.
    [current, analysisHistory, roster, gameStats] = await Promise.all([
      getWeeklyRatings(season, "current").then((result) => result.ratings).catch(() => []),
      getRatingAnalysisHistory(season, "current").catch(() => []),
      getTeamSeasonRoster(season).then((rows) => rows ?? []).catch(() => []),
      getTeamGameStats(season).catch(() => null),
    ]);
  }
  const now = pageNow(query);
  const nextGame = nextUpcomingGame(games, now);
  // Stats snapshots cover games completed before a week's slate: the week after the last played game, so a bye
  // before the next game does not ask for a snapshot that is not published yet.
  const played = games.filter(isFinal);
  const statsWeek = played.length > 0 ? played[played.length - 1].week + 1 : nextGame ? nextGame.week : null;
  const unitRows = statsWeek === null ? null
    : process.env.CFB_UI_TEST_MODE === "1" ? buildUnitRows(fixtureRows([team], "", query?.fixture === "no-ypp" ? YPP_KEYS : []), team, team)
    : await loadUnitRows(season, team, statsWeek);
  const rankHistory = analysisHistory.flatMap((entry) => {
    const row = entry.ratings.find((rating) => rating.team === ratingName);
    const rank = nationalRanks(entry.ratings, "overall").get(ratingName);
    return row && rank !== undefined && entry.period.postWeek !== undefined ? [{ week: entry.period.postWeek, rating: row.overallRating, rank }] : [];
  });
  const currentRow = current.find((row) => row.team === ratingName);
  const evidence: UnitRatingBreakdown[] = currentRow && publicationScope.mode === "predictions"
    ? await getTeamRatingEvidence(season, team, currentRow, current)
    : [];
  const summary = buildTeamSummary(current, ratingName, rankHistory);
  const conference = roster.find((row) => row.team === ratingName || row.team === team)?.conference ?? null;
  return (
    <PageShell
      width="slate"
      header={{ season, systemName: null, updatedAt: null, allowedSeasons: publicationScope.allowedSeasons,
        back: { href: "/teams", label: "Back to teams", title: teamAbbr(team) } }}
      mainClassName="space-y-4 py-4 sm:py-8"
    >
      <div className="flex flex-wrap items-center justify-between gap-3"><Link href="/teams" className="inline-flex min-h-11 items-center text-sm max-sm:hidden text-accent-ink hover:underline">← All teams</Link><Link href={`/teams?${new URLSearchParams({ view: "compare", team: ratingName, season: String(season) })}`} className="inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-semibold text-accent-ink">Compare this team</Link></div>
      <TeamHero team={team} conference={conference} summary={summary} nextGame={nextGame} />
      <nav aria-label="Team sections" className="flex flex-wrap gap-x-4 gap-y-1 border-b border-line pb-3 text-sm font-semibold text-accent-ink">{[["team-games", "Schedule"], ["team-rating-trend", "Strength"], ["team-rating-evidence", "Rating evidence"], ["team-game-log", "Game log"], ["team-unit-profile", "Unit profile"]].map(([id, label]) => <a key={id} href={`#${id}`} className="inline-flex min-h-11 items-center hover:underline">{label}</a>)}</nav>
      {unavailable ? <Notice tone="empty">Team data is temporarily unavailable.</Notice> : (
        <div className="grid gap-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] sm:items-start">
          <div className="min-w-0 space-y-4">
            <TeamSchedule games={games} team={team} now={now} />
            <ModelOnTeam games={games} team={team} />
            {gameStats === null ? (
              <TeamSection id="team-game-log" title="Game log"><Notice tone="empty">The game log is not available right now.</Notice></TeamSection>
            ) : <GameLogChart team={team} bars={gameLogBars(gameStats, [team, ratingName])} />}
          </div>
          <div className="min-w-0 space-y-4">
            <RatingTrend team={ratingName} history={analysisHistory} />
            {evidence.length > 0 && <TeamRatingEvidence units={evidence} />}
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
