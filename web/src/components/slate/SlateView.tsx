import { Header, Footer } from "@/components/Header";
import { ModelRecord } from "@/components/slate/ModelRecord";
import { SlateStatusRow } from "@/components/slate/SlateStatusRow";
import { TopLeans } from "@/components/slate/TopLeans";
import { ResultHighlights } from "@/components/slate/ResultHighlights";
import { PicksSlate } from "@/components/slate/PicksSlate";
import { ResultsSlate } from "@/components/slate/ResultsSlate";
import { WeekNav } from "@/components/WeekNav";
import { weekRecord, type Tally } from "@/lib/slate";
import type { Game } from "@/lib/queries";
import type { Performance } from "@/lib/v5";

export interface SlateViewProps {
  mode: "picks" | "results";
  season: number;
  week: number;
  weeks: number[];
  basePath?: string;
  games: Game[];
  performance?: Performance[];
  /** Season track record over each scored week's top leans (Picks only). */
  topLeansRecord?: Tally | null;
  systemName?: string | null;
  runState?: string | null;
  retrospective?: boolean;
  updatedAt?: Date | null;
  publicationMode: "predictions" | "market";
  allowedSeasons: readonly number[];
  dbError?: string | null;
  retrospectiveRepair?: boolean;
  /** Notice for a display-only run; null when the run is an ordinary one. */
  displayOnlyNotice?: string | null;
  initialSort?: "kickoff" | "spreadEdge" | "totalEdge";
  emptyMessage?: string;
}

/**
 * Layout shell for the weekly slate views (Picks `/` and Results `/results`).
 * Standardizes header, skip links, model record, status line, week
 * navigation, and the lean-sentence slate, with the fail-closed market-mode
 * card path for games without predictions.
 */
export function SlateView({
  mode,
  season,
  week,
  weeks,
  basePath = "/",
  games,
  performance = [],
  topLeansRecord = null,
  systemName = null,
  runState = null,
  retrospective = false,
  updatedAt = null,
  publicationMode,
  allowedSeasons,
  dbError = null,
  retrospectiveRepair = false,
  displayOnlyNotice = null,
  initialSort = "kickoff",
  emptyMessage,
}: SlateViewProps) {
  const predictionsVisible = games.some((g) => g.publicationMode === "predictions");
  const showBetResult = mode === "results";

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
        updatedAt={null}
        publicationMode={publicationMode}
        allowedSeasons={allowedSeasons}
        containerWidth="max-w-6xl"
        status={
          <SlateStatusRow
            runState={runState}
            retrospective={retrospective}
            publishedAt={updatedAt}
          />
        }
      />

      <main id="main-content" className="mx-auto w-full max-w-6xl flex-1 space-y-3 px-4 py-3 sm:space-y-4 sm:py-6">
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
              <ModelRecord
                performance={performance}
                week={mode === "results" ? { number: week, ...weekRecord(games) } : undefined}
              />
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

            {displayOnlyNotice && (
              <p
                role="note"
                data-testid="display-only-notice"
                className="rounded-xl border border-line bg-surface-card px-4 py-3 text-sm text-ink-muted"
              >
                {displayOnlyNotice}
              </p>
            )}

            {mode === "picks" && predictionsVisible && <TopLeans games={games} record={topLeansRecord} season={season} />}
            {mode === "results" && predictionsVisible && <ResultHighlights games={games} />}

            {weeks.length > 1 && (
              <WeekNav season={season} week={week} weeks={weeks} basePath={basePath} />
            )}

            {mode === "results" && (
              <p className="px-1 text-xs text-ink-faint">
                {`Final scores, model picks, and graded results for completed Week ${week} games.`}
              </p>
            )}

            {games.length === 0 ? (
              mode === "picks" ? (
                <div className="rounded-2xl border border-line bg-surface-card p-8 sm:p-12 text-center shadow-xs">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-accent-line/40 bg-accent-soft text-accent-ink shadow-2xs">
                    <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <h2 className="mt-5 text-xl font-bold tracking-tight text-ink sm:text-2xl">
                    Week {week} Picks Dropping Soon
                  </h2>
                  <p className="mx-auto mt-2.5 max-w-lg text-sm text-ink-muted leading-relaxed sm:text-base">
                    Blitzkrieg V5 model predictions and top leans will be posted as betting lines open across sportsbooks ahead of kickoff.
                  </p>
                  <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
                    <a
                      href={`/results?week=${week > 0 ? week - 1 : 0}`}
                      className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-xs font-semibold text-accent-ink shadow-xs transition hover:opacity-90 active:scale-[0.98]"
                    >
                      View Week {week > 0 ? week - 1 : 0} Results & Graded Picks →
                    </a>
                    <a
                      href="/performance"
                      className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface-inset px-4 py-2.5 text-xs font-semibold text-ink transition hover:bg-surface-card active:scale-[0.98]"
                    >
                      Performance Dashboard
                    </a>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-line bg-surface-card p-6 text-center text-sm text-ink-faint">
                  {emptyMessage ?? `No games loaded for ${season} week ${week}.`}
                </div>
              )
            ) : mode === "picks" ? (
              <PicksSlate
                games={games}
                showBetResult={showBetResult}
                initialSort={initialSort}
              />
            ) : (
              <ResultsSlate
                games={games}
                showBetResult={showBetResult}
                initialSort={
                  initialSort === "kickoff" ? "kickoff" : "bestEdge"
                }
              />
            )}
          </>
        )}
      </main>

      <Footer publicationMode={publicationMode} containerWidth="max-w-6xl" />
    </div>
  );
}
