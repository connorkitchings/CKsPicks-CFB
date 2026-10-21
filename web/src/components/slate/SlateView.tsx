import Link from "next/link";
import { PageHeading } from "@/components/ui/PageHeading";
import { Card } from "@/components/ui/Card";
import { Notice } from "@/components/ui/Notice";
import { Header, Footer } from "@/components/Header";
import { ModelRecord } from "@/components/slate/ModelRecord";
import { SlateStatusRow } from "@/components/slate/SlateStatusRow";
import { TopLeans } from "@/components/slate/TopLeans";
import { ResultHighlights } from "@/components/slate/ResultHighlights";
import { SlateList } from "@/components/slate/SlateList";
import { WeekNav } from "@/components/WeekNav";
import { hasGradedPick, weekPhase, weekRecord, type SlateSort, type Tally, type WeekPhase } from "@/lib/slate";
import type { RosterRow } from "@/lib/conferences";
import type { Game } from "@/lib/queries";
import type { Performance } from "@/lib/v5";

export interface SlateViewProps {
  season: number;
  week: number;
  weeks: number[];
  basePath?: string;
  games: Game[];
  roster?: RosterRow[];
  /** Season record before the week. */
  performance?: Performance[];
  /** The week's own record and accuracy; empty until a game is graded. */
  weekPerformance?: Performance[];
  /** Season track record over each scored week's top leans. */
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
  initialSort?: SlateSort;
  emptyMessage?: string;
}

const PHASE_LABEL: Record<WeekPhase, string> = {
  upcoming: "Upcoming",
  "in-progress": "In progress",
  final: "Final",
};

/**
 * Layout shell for the Games week view (`/`). One view covers every phase of a
 * week: leans before kickoff, graded picks after, both while a week is in
 * progress. Standardizes header, model record, status line, week navigation and
 * the slate, with the fail-closed market-mode card path for games without
 * predictions.
 */
export function SlateView({
  season,
  week,
  weeks,
  basePath = "/",
  games,
  roster = [],
  performance = [],
  weekPerformance = [],
  topLeansRecord = null,
  systemName = null,
  runState = null,
  retrospective = false,
  updatedAt = null,
  publicationMode,
  allowedSeasons,
  dbError = null,
  displayOnlyNotice = null,
  initialSort = "kickoff",
  emptyMessage,
}: SlateViewProps) {
  const predictionsVisible = games.some((g) => g.publicationMode === "predictions");
  const phase = weekPhase(games);
  const graded = hasGradedPick(games);

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        season={season > 0 ? season : null}
        systemName={systemName}
        updatedAt={null}
        publicationMode={publicationMode}
        allowedSeasons={allowedSeasons}
        width="slate"
        status={
          <SlateStatusRow
            runState={runState}
            retrospective={retrospective}
            publishedAt={updatedAt}
          />
        }
      />

      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 space-y-3 px-4 py-3 sm:space-y-4 sm:py-6">
        {dbError && (
          <Notice tone="warn">{dbError}</Notice>
        )}

        {!dbError && season <= 0 && (
          <Notice tone="empty">
            {emptyMessage ??
              "No active week has been published yet. Complete the Week 0 publication workflow to load the approved schedule and market data."}
          </Notice>
        )}

        {!dbError && season > 0 && (
          <>
            <PageHeading
              title={`Week ${week}`}
              actions={weeks.length > 1 ? <WeekNav season={season} week={week} weeks={weeks} basePath={basePath} compact /> : undefined}
            >
              <span
                data-testid="week-phase"
                data-phase={phase}
                className="inline-flex items-center rounded-full border border-line bg-surface-inset px-2 py-0.5 text-xs font-semibold text-ink-muted"
              >
                {PHASE_LABEL[phase]}
              </span>
            </PageHeading>
            {publicationMode === "predictions" && (performance.length > 0 || graded) && (
              <ModelRecord
                performance={performance}
                weekNumber={week}
                week={graded ? weekRecord(games) : undefined}
                weekPerformance={graded ? weekPerformance : undefined}
              />
            )}

            {displayOnlyNotice && (
              <p
                role="note"
                data-card=""
                data-testid="display-only-notice"
                className="rounded-xl border border-line bg-surface-card px-4 py-3 text-sm text-ink-muted"
              >
                {displayOnlyNotice}
              </p>
            )}

            {predictionsVisible && phase !== "final" && <TopLeans games={games} record={topLeansRecord} season={season} />}
            {predictionsVisible && phase !== "upcoming" && <ResultHighlights games={games} />}

            {games.length === 0 ? (
              <Card padding="none" className="p-8 text-center sm:p-12">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-accent-line/40 bg-accent-soft text-accent-ink shadow-2xs">
                  <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h2 className="mt-5 text-xl font-bold tracking-tight text-ink sm:text-2xl">
                  Week {week} Games Dropping Soon
                </h2>
                <p className="mx-auto mt-2.5 max-w-lg text-sm text-ink-muted leading-relaxed sm:text-base">
                  {emptyMessage ?? "Blitzkrieg V5 model predictions and top leans will be posted as betting lines open across sportsbooks ahead of kickoff."}
                </p>
                <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
                  {week > 0 && (
                    <Link
                      href={`/?week=${week - 1}`}
                      className="inline-flex items-center gap-2 rounded-xl bg-accent-solid px-4 py-2.5 text-xs font-semibold text-on-accent-solid shadow-xs transition hover:opacity-90 active:scale-[0.98]"
                    >
                      View Week {week - 1} games →
                    </Link>
                  )}
                  <Link
                    href="/model"
                    className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface-inset px-4 py-2.5 text-xs font-semibold text-ink transition hover:bg-surface-card active:scale-[0.98]"
                  >
                    Model record
                  </Link>
                </div>
              </Card>
            ) : (
              <SlateList games={games} roster={roster} initialSort={initialSort} />
            )}
          </>
        )}
      </main>

      <Footer publicationMode={publicationMode} width="slate" />
    </div>
  );
}
