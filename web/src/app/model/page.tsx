import type { Metadata } from "next";
import { pageMetadata } from "@/lib/metadata";
import { getV5PerformanceDetail,type PerformanceDetail } from "@/lib/v5";
import { archivePerformanceFixture, mobilePerformanceFixture, partialPerformanceFixture } from "@/test/fixtures/performance-mobile";
import { isUiTestMode } from "@/lib/slate-page";
import {
  lineSourceCounts,
  marketComparison,
  type MarketTarget,
} from "@/lib/performance-market";
import { pairedErrors } from "@/lib/performance-errors";
import { weeklyAndCumulative } from "@/lib/performance-trend";
import { publicationScope } from "@/lib/publication";
import { PHONE_PAGE_RHYTHM } from "@/lib/page-width";
import { PageShell } from "@/components/PageShell";
import { ModelTabs } from "@/components/model/ModelTabs";
import { Notice } from "@/components/ui/Notice";
import { Disclosure } from "@/components/ui/Disclosure";
import { PageHeading } from "@/components/ui/PageHeading";
import { PerformanceDashboard, type MarketView, type PerformanceView } from "@/components/PerformanceDashboard";
import { loadPerformanceRecord } from "@/lib/performance-sections";

// Selection changes must not serve a record baked into an earlier build.
export const dynamic = "force-dynamic";

// The client bundle receives only the fields the dashboard renders.
const EXPLAINER = `Win rate excludes pushes. A game without an eligible market line does not count as a win or loss. Grades use captured selected lines and forecasts use point-in-time inputs. The record is settled at the best quote found for each pick; the comparison with the betting line uses the retained pre-kickoff line.`;

function marketView(detail: PerformanceDetail, target: MarketTarget): MarketView {
  return {
    comparison: marketComparison(detail.gradedGames, target),
    counts: lineSourceCounts(detail.gradedGames, target),
  };
}

function clientView(detail: PerformanceDetail): PerformanceView {
  const gradedGames = detail.gradedGames.map(({ week, spreadResult, totalResult }) => ({ week, spreadResult, totalResult }));
  return {
    summary: detail.summary,
    weeks: detail.weeks,
    gradedGames,
    weekRows: detail.weekRows,
    trend: weeklyAndCumulative(gradedGames, detail.weeks),
    market: { spread: marketView(detail, "spread"), total: marketView(detail, "total") },
    pairs: { spread: pairedErrors(detail.gradedGames, "spread"), total: pairedErrors(detail.gradedGames, "total") },
  };
}

export const metadata: Metadata = pageMetadata("Model", "Season record and performance of the forecasts: accuracy, betting results and error by week.", "/model");

export default async function ModelPage({ searchParams }: { searchParams?: Promise<{ fixture?: string; target?: string | string[] }> }) {
  // `?target=` only picks which already-loaded target the error view opens on; unknown values fall back.
  // `?fixture=partial|archive` are UI-test variants and are read only in fixture mode.
  const params = await searchParams;
  const fixture = isUiTestMode() ? params?.fixture : undefined;
  const record = isUiTestMode()
    ? { status: "ok" as const, value: fixture === "partial" ? partialPerformanceFixture : fixture === "archive" ? archivePerformanceFixture : mobilePerformanceFixture }
    : await loadPerformanceRecord(
      () => getV5PerformanceDetail(publicationScope.season),
      error => console.error("V5 cumulative performance query failed", error),
    );
  const title = `${publicationScope.season} V5 cumulative record`;
  return (
    <PageShell
      width="wide"
      header={{
        season: publicationScope.season,
        systemName: null,
        updatedAt: null,
        allowedSeasons: publicationScope.allowedSeasons,
      }}
      mainClassName={`${PHONE_PAGE_RHYTHM} sm:space-y-4 sm:py-6`}
    >
        <ModelTabs active="record" />
        {/* Phones: the app bar names the page, so the heading stays for screen readers only. */}
        <div className="max-sm:sr-only">
          <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink max-sm:hidden">{publicationScope.season} · V5</p>
          <PageHeading title="Season record & performance">
            One continuous V5 record from Week 0 onward, with spreads and totals reported separately.
          </PageHeading>
        </div>
        {record.status === "unavailable" ? (
          <StatusCard title={title} message="Performance data is temporarily unavailable." />
        ) : record.value.selectedGames === 0 ? (
          <StatusCard title={title} message="No V5 weeks are selected." />
        ) : record.value.gradedGames.length === 0 ? (
          <StatusCard title={title} message="The selected runs have games, but no grades are available yet." />
        ) : <PerformanceDashboard data={clientView(record.value)} title={title} season={publicationScope.season} />}
        <p className="text-xs leading-relaxed text-ink-muted max-sm:hidden">{EXPLAINER}</p>
        <Disclosure title="About this record" className="sm:hidden">
          <div className="space-y-2 text-xs leading-relaxed">
            <p>One continuous V5 record from Week 0 onward, with spreads and totals reported separately.</p>
            <p>{EXPLAINER}</p>
            <p>Select any week to view its full game-by-game results and graded picks on the Games tab.</p>
          </div>
        </Disclosure>
    </PageShell>
  );
}

function StatusCard({ title, message }: { title: string; message: string }) {
  return (
    <Notice tone="empty">
      <h2 className="font-semibold text-ink">{title}</h2>
      <p className="mt-1">{message}</p>
    </Notice>
  );
}
