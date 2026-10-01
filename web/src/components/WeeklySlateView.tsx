import { Header, Footer } from "@/components/Header";
import { V5PerformanceBanner } from "@/components/V5PerformanceBanner";
import { WeekNav } from "@/components/WeekNav";
import { GamesList } from "@/components/GamesList";
import type { Game } from "@/lib/queries";
import type { Performance } from "@/lib/v5";

export interface WeeklySlateViewProps {
  mode: "picks" | "results";
  season: number;
  week: number;
  weeks: number[];
  basePath?: string;
  games: Game[];
  ranks?: Map<string, number>;
  performance?: Performance[];
  systemName?: string | null;
  updatedAt?: Date | null;
  publicationMode: "predictions" | "market";
  allowedSeasons: readonly number[];
  dbError?: string | null;
  retrospectiveRepair?: boolean;
  initialSort?: "kickoff" | "spreadEdge" | "totalEdge";
  emptyMessage?: string;
}

/**
 * Reusable layout shell for weekly slate views (Picks `/` and Results `/results`).
 * Standardizes header, skip links, performance banners, week navigation,
 * games list with day grouping and rankings, and footer.
 */
export function WeeklySlateView({
  mode,
  season,
  week,
  weeks,
  basePath = "/",
  games,
  ranks,
  performance = [],
  systemName = null,
  updatedAt = null,
  publicationMode,
  allowedSeasons,
  dbError = null,
  retrospectiveRepair = false,
  initialSort = "kickoff",
  emptyMessage,
}: WeeklySlateViewProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface-card focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-ink focus:shadow-lg"
      >
        Skip to main content
      </a>
      <Header
        season={season > 0 ? season : null}
        systemName={systemName}
        updatedAt={updatedAt}
        publicationMode={publicationMode}
        allowedSeasons={allowedSeasons}
      />

      <main id="main-content" className="mx-auto w-full max-w-4xl flex-1 space-y-4 px-4 py-6">
        {dbError && (
          <div className="rounded-xl border border-warn-line bg-warn-soft p-4 text-sm text-warn">
            {dbError}
          </div>
        )}

        {!dbError && season <= 0 && (
          <div className="rounded-xl border border-line bg-surface-card p-6 text-center text-sm text-ink-faint">
            {emptyMessage ??
              "No active week has been published yet. Complete the Week 0 publication workflow to load the approved schedule and market data."}
          </div>
        )}

        {!dbError && season > 0 && (
          <>
            {publicationMode === "predictions" && performance.length > 0 && (
              <V5PerformanceBanner performance={performance} />
            )}

            {retrospectiveRepair && (
              <p
                role="note"
                className="rounded-xl border border-line bg-surface-card px-4 py-3 text-sm text-ink-muted"
              >
                Retrospective replay: these predictions and grades were recalculated after the games
                using the repaired V5 ratings. They were not the picks originally published before kickoff.
              </p>
            )}

            {weeks.length > 1 && (
              <WeekNav season={season} week={week} weeks={weeks} basePath={basePath} />
            )}

            <p className="px-1 text-xs text-ink-faint">
              {mode === "picks"
                ? "Market lines reflect the selected pre-kickoff quote; edge shows the model\u2019s difference."
                : `Final scores, model picks, and graded results for completed Week ${week} games.`}
            </p>

            {games.length === 0 ? (
              <div className="rounded-xl border border-line bg-surface-card p-6 text-center text-sm text-ink-faint">
                {emptyMessage ?? `No games loaded for ${season} week ${week}.`}
              </div>
            ) : (
              <GamesList
                games={games}
                initialSort={initialSort}
                ranks={ranks}
              />
            )}
          </>
        )}
      </main>

      <Footer publicationMode={publicationMode} />
    </div>
  );
}
