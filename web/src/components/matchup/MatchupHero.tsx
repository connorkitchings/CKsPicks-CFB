import Link from "next/link";
import TeamLogo from "@/components/TeamLogo";
import type { MatchupData } from "@/lib/matchup";

function formatKickoff(startDate: Date): string {
  return startDate.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function formatRating(value: number | null): string {
  if (value === null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

export function MatchupHero({ matchup }: { matchup: MatchupData }) {
  const isFinal = matchup.homeFinalPoints !== null && matchup.awayFinalPoints !== null;

  return (
    <section aria-labelledby="matchup-header" className="space-y-4">
      {/* Top Breadcrumb & Metadata Strip */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3 text-xs text-ink-muted">
        <Link
          href={isFinal ? `/results?week=${matchup.week}` : `/?week=${matchup.week}`}
          className="inline-flex items-center gap-1 font-medium text-accent-ink hover:underline"
        >
          ← Back to {isFinal ? "Results" : "Picks"} (Week {matchup.week})
        </Link>
        <div className="flex items-center gap-2 text-ink-faint">
          <span>{formatKickoff(matchup.startDate)}</span>
          {matchup.systemName && (
            <>
              <span>·</span>
              <span className="font-mono">{matchup.systemName}</span>
            </>
          )}
          <span className="rounded bg-surface-inset px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
            Game Breakdown
          </span>
        </div>
      </div>

      {/* Main Scorecard / Matchup Hero Grid */}
      <div className="rounded-2xl border border-line bg-surface-card p-5 shadow-sm sm:p-6">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
          {/* Away Team Card (Left) */}
          <div className="flex items-center gap-4 sm:flex-col sm:text-center">
            <TeamLogo
              name={matchup.awayTeam}
              px={80}
              decorative={false}
              className="h-16 w-16 sm:h-20 sm:w-20"
            />
            <div className="min-w-0 flex-1 sm:w-full">
              <div className="flex items-center gap-1.5 sm:justify-center">
                <Link
                  href={`/teams/${encodeURIComponent(matchup.awayTeam)}`}
                  className="truncate text-xl font-bold tracking-tight text-ink hover:underline hover:text-accent-ink"
                >
                  {matchup.awayTeam}
                </Link>
              </div>
              <p className="text-xs text-ink-faint">Away</p>

              {/* Score (if final) or V5 Certified Ratings */}
              {isFinal ? (
                <div className="mt-3 flex flex-col items-center">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
                    Final Score
                  </span>
                  <span className="font-mono text-3xl font-bold text-ink">
                    {matchup.awayFinalPoints}
                  </span>
                </div>
              ) : (
                <div className="mt-3 flex flex-col items-center gap-1 text-xs">
                  <div className="inline-flex items-center gap-1 rounded bg-surface-inset px-2 py-0.5 font-mono text-xs font-semibold text-ink">
                    <span>Rank #{matchup.awayRating.rank ?? "—"}</span>
                    <span className="text-ink-faint">·</span>
                    <span>{formatRating(matchup.awayRating.overallRating)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-ink-muted">
                    <span>Off: #{matchup.awayRating.offenseRank ?? "—"}</span>
                    <span>·</span>
                    <span>Def: #{matchup.awayRating.defenseRank ?? "—"}</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Center Matchup Odds & Model Summary */}
          <div className="flex flex-col items-center justify-center rounded-xl border border-line/60 bg-surface-inset px-5 py-4 text-center sm:min-w-[360px]">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
              Forecast & Lines
            </span>

            <div className="mt-3 inline-grid grid-cols-[auto_1fr] items-center gap-x-3.5 gap-y-2 text-sm text-left">
              <span className="text-ink-muted font-medium whitespace-nowrap">Market:</span>
              <div className="font-mono text-ink whitespace-nowrap flex items-center">
                <span className="font-medium">{matchup.marketSpread}</span>
                {matchup.marketTotal && (
                  <span className="ml-1.5 font-sans text-xs text-ink-muted">· O/U {matchup.marketTotal.toFixed(1)}</span>
                )}
              </div>

              {matchup.publicationMode === "predictions" && (
                <>
                  <span className="text-ink-muted font-medium whitespace-nowrap">Model:</span>
                  <div className="font-mono text-ink whitespace-nowrap flex items-center">
                    <span className="font-medium">{matchup.modelSpread}</span>
                    {matchup.modelTotal && (
                      <span className="ml-1.5 font-sans text-xs text-ink-muted">· O/U {matchup.modelTotal.toFixed(1)}</span>
                    )}
                  </div>

                  <span className="text-ink-muted font-medium whitespace-nowrap">Model Bet:</span>
                  <div className="font-mono text-sm whitespace-nowrap flex items-center">
                    {matchup.spreadLean ? (
                      <span className="font-medium text-accent-ink">
                        {matchup.spreadLean === "home" ? matchup.homeTeam : matchup.awayTeam} Lean
                      </span>
                    ) : (
                      <span className="text-ink-faint">No Spread</span>
                    )}

                    {matchup.totalLean && (
                      <>
                        <span className="mx-1.5 font-sans text-xs text-ink-muted">·</span>
                        <span className="font-medium text-accent-ink">
                          {matchup.totalLean === "over" ? "Over" : "Under"}
                        </span>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>

            {isFinal && (
              <span className="mt-2.5 rounded-full bg-surface-card px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-muted border border-line">
                Final: {matchup.awayFinalPoints}–{matchup.homeFinalPoints}
              </span>
            )}
          </div>

          {/* Home Team Card (Right) */}
          <div className="flex items-center gap-4 sm:flex-col sm:text-center">
            <TeamLogo
              name={matchup.homeTeam}
              px={80}
              decorative={false}
              className="h-16 w-16 sm:h-20 sm:w-20"
            />
            <div className="min-w-0 flex-1 sm:w-full">
              <div className="flex items-center gap-1.5 sm:justify-center">
                <Link
                  href={`/teams/${encodeURIComponent(matchup.homeTeam)}`}
                  className="truncate text-xl font-bold tracking-tight text-ink hover:underline hover:text-accent-ink"
                >
                  {matchup.homeTeam}
                </Link>
              </div>
              <p className="text-xs text-ink-faint">Home</p>

              {/* Score (if final) or V5 Certified Ratings */}
              {isFinal ? (
                <div className="mt-3 flex flex-col items-center">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
                    Final Score
                  </span>
                  <span className="font-mono text-3xl font-bold text-ink">
                    {matchup.homeFinalPoints}
                  </span>
                </div>
              ) : (
                <div className="mt-3 flex flex-col items-center gap-1 text-xs">
                  <div className="inline-flex items-center gap-1 rounded bg-surface-inset px-2 py-0.5 font-mono text-xs font-semibold text-ink">
                    <span>Rank #{matchup.homeRating.rank ?? "—"}</span>
                    <span className="text-ink-faint">·</span>
                    <span>{formatRating(matchup.homeRating.overallRating)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-ink-muted">
                    <span>Off: #{matchup.homeRating.offenseRank ?? "—"}</span>
                    <span>·</span>
                    <span>Def: #{matchup.homeRating.defenseRank ?? "—"}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
