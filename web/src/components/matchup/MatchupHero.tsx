import Image from "next/image";
import Link from "next/link";
import { logoUrl } from "@/lib/teams";
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
          <span>·</span>
          <span className="font-mono">{matchup.systemName}</span>
          <span className="rounded bg-surface-inset px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
            Advanced Stats Preview
          </span>
        </div>
      </div>

      {/* Main Scorecard / Matchup Hero Grid */}
      <div className="rounded-2xl border border-line bg-surface-card p-5 shadow-sm sm:p-6">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3 sm:items-center">
          {/* Away Team Card (Left) */}
          <div className="flex items-center gap-4 sm:flex-col sm:text-center">
            <Image
              src={logoUrl(matchup.awayTeam)}
              alt={matchup.awayTeam}
              width={64}
              height={64}
              className="h-16 w-16 shrink-0 object-contain sm:h-20 sm:w-20"
              unoptimized
            />
            <div className="min-w-0 flex-1 sm:w-full">
              <div className="flex items-center gap-1.5 sm:justify-center">
                {matchup.awayProfile.rank && matchup.awayProfile.rank <= 25 && (
                  <span className="text-sm font-bold text-accent-ink">
                    #{matchup.awayProfile.rank}
                  </span>
                )}
                <h2 className="truncate text-xl font-bold tracking-tight text-ink">
                  {matchup.awayTeam}
                </h2>
              </div>
              <p className="text-xs text-ink-faint">Away</p>
              {/* Score / Projection */}
              <div className="mt-3 flex items-center gap-4 sm:justify-center">
                <div>
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
                    Win Prob
                  </span>
                  <div className="font-mono text-2xl font-bold text-ink">
                    {matchup.awayWinProb.toFixed(1)}%
                  </div>
                </div>
                <div className="h-8 w-px bg-line" />
                <div>
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
                    Proj Pts
                  </span>
                  <div className="font-mono text-2xl font-bold text-ink">
                    {isFinal ? matchup.awayFinalPoints : matchup.awayProjPoints.toFixed(1)}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Center Matchup Odds & Model Summary */}
          <div className="flex flex-col items-center justify-center rounded-xl border border-line/60 bg-surface-inset p-4 text-center">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
              Forecast & Lines
            </span>

            <div className="mt-2.5 space-y-1 text-sm">
              <div className="text-ink">
                Market: <span className="font-mono font-medium">{matchup.marketSpread}</span>
                {matchup.marketTotal && (
                  <span className="ml-1 text-ink-muted">· O/U {matchup.marketTotal.toFixed(1)}</span>
                )}
              </div>
              <div className="text-ink">
                Model: <span className="font-mono font-medium">{matchup.modelSpread}</span>
                {matchup.modelTotal && (
                  <span className="ml-1 text-ink-muted">· O/U {matchup.modelTotal.toFixed(1)}</span>
                )}
              </div>
            </div>

            {/* Lean Badge */}
            <div className="mt-3 flex flex-wrap items-center justify-center gap-1.5">
              {matchup.spreadLean ? (
                <span className="inline-flex items-center gap-1 rounded-md bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent-ink">
                  {matchup.spreadLean === "home" ? matchup.homeTeam : matchup.awayTeam} Lean
                  {matchup.edgeSpread !== null && (
                    <span className="text-[11px] font-normal opacity-80">
                      (+{matchup.edgeSpread.toFixed(1)})
                    </span>
                  )}
                </span>
              ) : (
                <span className="rounded-md bg-surface-card px-2.5 py-1 text-xs text-ink-faint">
                  No Spread Lean
                </span>
              )}

              {matchup.totalLean && (
                <span className="inline-flex items-center gap-1 rounded-md bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent-ink">
                  {matchup.totalLean === "over" ? "Over" : "Under"}
                  {matchup.edgeTotal !== null && (
                    <span className="text-[11px] font-normal opacity-80">
                      (+{matchup.edgeTotal.toFixed(1)})
                    </span>
                  )}
                </span>
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
            <Image
              src={logoUrl(matchup.homeTeam)}
              alt={matchup.homeTeam}
              width={64}
              height={64}
              className="h-16 w-16 shrink-0 object-contain sm:h-20 sm:w-20"
              unoptimized
            />
            <div className="min-w-0 flex-1 sm:w-full">
              <div className="flex items-center gap-1.5 sm:justify-center">
                {matchup.homeProfile.rank && matchup.homeProfile.rank <= 25 && (
                  <span className="text-sm font-bold text-accent-ink">
                    #{matchup.homeProfile.rank}
                  </span>
                )}
                <h2 className="truncate text-xl font-bold tracking-tight text-ink">
                  {matchup.homeTeam}
                </h2>
              </div>
              <p className="text-xs text-ink-faint">Home</p>
              {/* Score / Projection */}
              <div className="mt-3 flex items-center gap-4 sm:justify-center">
                <div>
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
                    Win Prob
                  </span>
                  <div className="font-mono text-2xl font-bold text-ink">
                    {matchup.homeWinProb.toFixed(1)}%
                  </div>
                </div>
                <div className="h-8 w-px bg-line" />
                <div>
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
                    Proj Pts
                  </span>
                  <div className="font-mono text-2xl font-bold text-ink">
                    {isFinal ? matchup.homeFinalPoints : matchup.homeProjPoints.toFixed(1)}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
