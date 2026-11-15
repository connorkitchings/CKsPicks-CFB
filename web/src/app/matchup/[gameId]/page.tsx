import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Header, Footer } from "@/components/Header";
import { MatchupHero } from "@/components/matchup/MatchupHero";
import { getMatchupData } from "@/lib/matchup";
import { parseGameId } from "@/lib/matchup-id";
import { isMatchupEnabled } from "@/lib/matchup-gate";
import { pageNow, type SlateSearchParams } from "@/lib/slate-page";
import { publicationScope } from "@/lib/publication";
import { teamAbbr } from "@/lib/team-logos";
import { teamHref } from "@/lib/team-routes";
import { PHONE_PAGE_RHYTHM } from "@/lib/page-width";
import { MatchupAnalysis } from "@/components/matchup/MatchupAnalysis";

// Revalidate every 5 minutes (ISR)
export const revalidate = 300;

const noindex = { robots: { index: false, follow: false } } satisfies Metadata;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ gameId: string }>;
}): Promise<Metadata> {
  const id = parseGameId((await params).gameId);
  if (!isMatchupEnabled() || id === null) return noindex;
  const matchup = await getMatchupData(id).catch(() => null);
  return matchup ? { ...noindex, title: `${matchup.awayTeam} at ${matchup.homeTeam} · Matchup` } : noindex;
}

export default async function MatchupPage({
  params,
  searchParams,
}: {
  params: Promise<{ gameId: string }>;
  searchParams: SlateSearchParams;
}) {
  if (!isMatchupEnabled()) notFound();
  const { gameId } = await params;
  const parsedGameId = parseGameId(gameId);
  if (parsedGameId === null) notFound();

  // A database failure surfaces as an error page; only a genuinely unknown or
  // unpublished game is a 404.
  const matchup = await getMatchupData(parsedGameId);
  if (!matchup) notFound();

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        season={matchup.season}
        systemName={matchup.systemName}
        updatedAt={null}
        publicationMode={publicationScope.mode}
        allowedSeasons={publicationScope.allowedSeasons}
        width="wide"
        back={{
          href: `/?week=${matchup.week}&status=all`,
          label: `Week ${matchup.week} games`,
          // Abbreviated so it fits beside the back and menu buttons; the page's h1 carries the full names.
          title: `${teamAbbr(matchup.awayTeam)} at ${teamAbbr(matchup.homeTeam)}`,
        }}
      />

      <main id="main-content" tabIndex={-1} className={`mx-auto w-full max-w-[1200px] flex-1 px-4 sm:px-6 sm:space-y-8 sm:py-8 ${PHONE_PAGE_RHYTHM}`}>
        {/* Hero Section */}
        <MatchupHero matchup={matchup} now={pageNow(await searchParams)} />

        <MatchupAnalysis matchup={matchup} />

        <div className="flex flex-wrap items-center gap-3">
          <Link
            href={`/?week=${matchup.week}&status=all`}
            className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-line bg-surface-elevated px-3 py-2 text-sm font-medium text-ink hover:border-accent hover:text-accent-ink"
          >
            All Week {matchup.week} games
          </Link>
          {[matchup.awayTeam, matchup.homeTeam].map((team) => (
            <Link
              key={team}
              href={teamHref(team)}
              className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-line bg-surface-elevated px-3 py-2 text-sm font-medium text-ink hover:border-accent hover:text-accent-ink"
            >
              {team} team page
            </Link>
          ))}
        </div>
      </main>

      <Footer publicationMode={publicationScope.mode} width="wide" />
    </div>
  );
}
