import Link from "next/link";
import { notFound } from "next/navigation";
import { Header, Footer } from "@/components/Header";
import { MatchupHero } from "@/components/matchup/MatchupHero";
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

        {/* Authentic Status & Advanced Metrics Ingestion Notice */}
        <section
          aria-labelledby="advanced-stats-notice"
          className="rounded-2xl border border-line bg-surface-card p-6 shadow-sm"
        >
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-accent" />
            <h2 id="advanced-stats-notice" className="text-sm font-semibold uppercase tracking-wider text-ink">
              Advanced Matchup Stats · Ingestion In Progress
            </h2>
          </div>

          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            We are currently building the data ingestion pipeline to publish verified, play-by-play football metrics directly to our web serving layer.
            Only 100% genuine model forecasts and certified Blitzkrieg team ratings are shown above.
          </p>

          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-line/60 bg-surface-inset p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ink">
                Upcoming Efficiency Metrics
              </h3>
              <ul className="mt-2 space-y-1.5 text-xs text-ink-muted">
                <li className="flex items-center gap-1.5">
                  <span className="text-accent-ink">•</span>
                  <span>Passing EPA/play & Rushing EPA/play</span>
                </li>
                <li className="flex items-center gap-1.5">
                  <span className="text-accent-ink">•</span>
                  <span>Scoring Opportunity Rate (trips inside 40)</span>
                </li>
                <li className="flex items-center gap-1.5">
                  <span className="text-accent-ink">•</span>
                  <span>Points Per Scoring Opportunity (PPSO)</span>
                </li>
              </ul>
            </div>

            <div className="rounded-xl border border-line/60 bg-surface-inset p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ink">
                Upcoming Context Metrics
              </h3>
              <ul className="mt-2 space-y-1.5 text-xs text-ink-muted">
                <li className="flex items-center gap-1.5">
                  <span className="text-accent-ink">•</span>
                  <span>Average Starting Field Position</span>
                </li>
                <li className="flex items-center gap-1.5">
                  <span className="text-accent-ink">•</span>
                  <span>Explosive Play Rate (20+ yard gains)</span>
                </li>
                <li className="flex items-center gap-1.5">
                  <span className="text-accent-ink">•</span>
                  <span>3rd & 4th Down Conversion Efficiencies</span>
                </li>
              </ul>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-line/60 pt-4">
            <Link
              href={`/teams/${encodeURIComponent(matchup.awayTeam)}`}
              className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface-elevated px-3 py-1.5 text-xs font-medium text-ink hover:border-accent hover:text-accent-ink"
            >
              Explore {matchup.awayTeam} Ratings & History →
            </Link>
            <Link
              href={`/teams/${encodeURIComponent(matchup.homeTeam)}`}
              className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface-elevated px-3 py-1.5 text-xs font-medium text-ink hover:border-accent hover:text-accent-ink"
            >
              Explore {matchup.homeTeam} Ratings & History →
            </Link>
            <Link
              href={`/?week=${matchup.week}`}
              className="ml-auto text-xs text-ink-faint hover:text-ink hover:underline"
            >
              Return to Week {matchup.week} Picks
            </Link>
          </div>
        </section>
      </main>

      <Footer publicationMode={publicationScope.mode} />
    </div>
  );
}
