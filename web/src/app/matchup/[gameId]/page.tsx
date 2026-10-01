import Link from "next/link";
import { notFound } from "next/navigation";
import { Header, Footer } from "@/components/Header";
import { MatchupHero } from "@/components/matchup/MatchupHero";
import { UnitMatchupTable } from "@/components/matchup/UnitMatchupTable";
import { TeamProfilePillars } from "@/components/matchup/TeamProfilePillars";
import { MatchupKeyTakeaways } from "@/components/matchup/MatchupKeyTakeaways";
import { getMatchupData } from "@/lib/matchup";
import { publicationScope } from "@/lib/publication";

// Revalidate every 5 minutes (ISR)
export const revalidate = 300;

export default async function MatchupPage({
  params,
}: {
  params: Promise<{ gameId: string }>;
}) {
  const { gameId } = await params;
  const parsedGameId = Number(gameId);

  if (!Number.isInteger(parsedGameId) || parsedGameId <= 0) {
    notFound();
  }

  let matchup: Awaited<ReturnType<typeof getMatchupData>> = null;
  try {
    matchup = await getMatchupData(parsedGameId);
  } catch (error) {
    console.error("Failed to load matchup breakdown", error);
  }

  if (!matchup) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header
          season={publicationScope.season}
          systemName="Blitzkrieg V5"
          updatedAt={new Date()}
          publicationMode={publicationScope.mode}
          allowedSeasons={publicationScope.allowedSeasons}
        />
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-12 text-center">
          <div className="rounded-2xl border border-line bg-surface-card p-8">
            <h1 className="text-xl font-bold text-ink">Matchup Not Found</h1>
            <p className="mt-2 text-sm text-ink-muted">
              We couldn&rsquo;t find game #{gameId} in the active forecast database.
            </p>
            <div className="mt-6">
              <Link
                href="/"
                className="rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-accent-ink hover:opacity-90"
              >
                ← Return to Weekly Picks
              </Link>
            </div>
          </div>
        </main>
        <Footer publicationMode={publicationScope.mode} />
      </div>
    );
  }

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

        {/* Center Unit-vs-Unit Showdowns */}
        <section aria-labelledby="unit-matchups-heading" className="space-y-4">
          <h2 id="unit-matchups-heading" className="sr-only">
            Unit-vs-Unit Advanced Stats Matchup
          </h2>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <UnitMatchupTable
              title={`${matchup.awayTeam} Offense vs ${matchup.homeTeam} Defense`}
              subtitle="Passing, rushing, and scoring opportunities showdown"
              awayTeam={matchup.awayTeam}
              homeTeam={matchup.homeTeam}
              rows={matchup.awayOffVsHomeDef}
            />
            <UnitMatchupTable
              title={`${matchup.awayTeam} Defense vs ${matchup.homeTeam} Offense`}
              subtitle="Defensive stops, finishing efficiency, and conversions"
              awayTeam={matchup.awayTeam}
              homeTeam={matchup.homeTeam}
              rows={matchup.awayDefVsHomeOff}
            />
          </div>
        </section>

        {/* Team Profile Pillars */}
        <section aria-labelledby="team-profiles-heading">
          <h2 id="team-profiles-heading" className="sr-only">
            Team Statistical Profiles
          </h2>
          <TeamProfilePillars
            awayProfile={matchup.awayProfile}
            homeProfile={matchup.homeProfile}
          />
        </section>

        {/* Key Analytical Takeaways */}
        <MatchupKeyTakeaways
          awayTeam={matchup.awayTeam}
          homeTeam={matchup.homeTeam}
          takeaways={matchup.takeaways}
        />
      </main>

      <Footer publicationMode={publicationScope.mode} />
    </div>
  );
}
