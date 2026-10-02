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

const noindex = { robots: { index: false, follow: false } } satisfies Metadata;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ gameId: string }>;
}): Promise<Metadata> {
  const id = Number((await params).gameId);
  if (!isMatchupEnabled() || !Number.isInteger(id) || id <= 0) return noindex;
  const matchup = await getMatchupData(id).catch(() => null);
  return matchup ? { ...noindex, title: `${matchup.awayTeam} at ${matchup.homeTeam} · Matchup` } : noindex;
}

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
        updatedAt={matchup.updatedAt}
        publicationMode={publicationScope.mode}
        allowedSeasons={publicationScope.allowedSeasons}
        wide
      />

      <main className="mx-auto w-full max-w-5xl flex-1 space-y-6 px-4 py-6">
        {/* Hero Section */}
        <MatchupHero matchup={matchup} />

        {matchup.stats ? (
          <section aria-label="Team stats" className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-2">
              <UnitMatchupTable
                offenseTeam={matchup.awayTeam}
                defenseTeam={matchup.homeTeam}
                rows={matchup.stats.awayOffVsHomeDef}
                offenseRating={{ rank: matchup.awayRating.offenseRank, value: matchup.awayRating.offenseRating }}
                defenseRating={{ rank: matchup.homeRating.defenseRank, value: matchup.homeRating.defenseRating }}
              />
              <UnitMatchupTable
                offenseTeam={matchup.homeTeam}
                defenseTeam={matchup.awayTeam}
                rows={matchup.stats.homeOffVsAwayDef}
                offenseRating={{ rank: matchup.homeRating.offenseRank, value: matchup.homeRating.offenseRating }}
                defenseRating={{ rank: matchup.awayRating.defenseRank, value: matchup.awayRating.defenseRating }}
              />
            </div>
            <section aria-label="Notes" data-testid="matchup-notes" className="space-y-1.5 pt-1 text-[11px] leading-relaxed text-ink-faint">
              <p>
                Stats through Week {matchup.stats.asOfWeek - 1}, before this game. FBS opponents only, regulation
                play, garbage time excluded; raw, not opponent-adjusted. Defense columns show what that defense
                allowed.
                {matchup.stats.cohortSize !== null && ` Ranks are among ${matchup.stats.cohortSize} teams; T = tied.`}
              </p>
            </section>
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

      <Footer publicationMode={publicationScope.mode} wide />
    </div>
  );
}
