import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Header, Footer } from "@/components/Header";
import { MatchupHero } from "@/components/matchup/MatchupHero";
import { getMatchupData } from "@/lib/matchup";
import { isMatchupEnabled } from "@/lib/matchup-gate";
import { publicationScope } from "@/lib/publication";
import { UnitMatchupTable } from "@/components/matchup/UnitMatchupTable";

// Revalidate every 5 minutes (ISR)
export const revalidate = 300;

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default async function MatchupPage({
  params,
}: {
  params: Promise<{ gameId: string }>;
}) {
  if (!isMatchupEnabled()) notFound();
  const { gameId } = await params;
  const parsedGameId = Number(gameId);

  if (!Number.isInteger(parsedGameId) || parsedGameId <= 0) {
    notFound();
  }

  // A database failure surfaces as an error page; only a genuinely unknown or
  // unpublished game is a 404.
  const matchup = await getMatchupData(parsedGameId);
  if (!matchup) notFound();

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        season={matchup.season}
        systemName={matchup.systemName}
        updatedAt={matchup.startDate}
        publicationMode={publicationScope.mode}
        allowedSeasons={publicationScope.allowedSeasons}
      />

      <main className="mx-auto w-full max-w-4xl flex-1 space-y-6 px-4 py-6">
        {/* Hero Section */}
        <MatchupHero matchup={matchup} />

        {matchup.stats ? (
          <section aria-label="Team stats" className="space-y-4">
            <p className="text-xs leading-relaxed text-ink-muted">
              Stats through Week {matchup.stats.asOfWeek - 1} (before this game): {matchup.awayTeam}{" "}
              {matchup.stats.awayGames} games, {matchup.homeTeam} {matchup.stats.homeGames} games.
              FBS opponents only, garbage time excluded. Possession metrics are the raw measures behind the V5 ratings (regulation only).
              {matchup.stats.cohortSize !== null && ` Ranks are among ${matchup.stats.cohortSize} teams.`}{" "}
              Defense columns show what that defense allowed.
            </p>
            <UnitMatchupTable
              offenseTeam={matchup.awayTeam}
              defenseTeam={matchup.homeTeam}
              rows={matchup.stats.awayOffVsHomeDef}
            />
            <UnitMatchupTable
              offenseTeam={matchup.homeTeam}
              defenseTeam={matchup.awayTeam}
              rows={matchup.stats.homeOffVsAwayDef}
            />
          </section>
        ) : (
          <section
            aria-label="Team stats"
            className="rounded-2xl border border-line bg-surface-card p-6 text-sm text-ink-muted shadow-sm"
          >
            Team stats are not published for this game yet.
          </section>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Link
            href={`/teams/${encodeURIComponent(matchup.awayTeam)}`}
            className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface-elevated px-3 py-1.5 text-xs font-medium text-ink hover:border-accent hover:text-accent-ink"
          >
            {`${matchup.awayTeam} ratings & history →`}
          </Link>
          <Link
            href={`/teams/${encodeURIComponent(matchup.homeTeam)}`}
            className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface-elevated px-3 py-1.5 text-xs font-medium text-ink hover:border-accent hover:text-accent-ink"
          >
            {`${matchup.homeTeam} ratings & history →`}
          </Link>
          <Link
            href={`/matchup?week=${matchup.week}`}
            className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface-elevated px-3 py-1.5 text-xs font-medium text-ink hover:border-accent hover:text-accent-ink"
          >
            All Week {matchup.week} matchups
          </Link>
          <Link
            href={`/?week=${matchup.week}`}
            className="ml-auto text-xs text-ink-faint hover:text-ink hover:underline"
          >
            Return to Week {matchup.week} Picks
          </Link>
        </div>
      </main>

      <Footer publicationMode={publicationScope.mode} />
    </div>
  );
}
