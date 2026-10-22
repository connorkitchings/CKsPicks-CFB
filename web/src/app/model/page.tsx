import { getV5PerformanceDetail, type PerformanceDetail } from "@/lib/v5";
import { mobilePerformanceFixture } from "@/test/fixtures/performance-mobile";
import { publicationScope } from "@/lib/publication";
import { PageShell } from "@/components/PageShell";
import { ModelTabs } from "@/components/model/ModelTabs";
import { Notice } from "@/components/ui/Notice";
import { PageHeading } from "@/components/ui/PageHeading";
import { PerformanceDashboard, type PerformanceView } from "@/components/PerformanceDashboard";
import { loadPerformanceRecord } from "@/lib/performance-sections";

// Selection changes must not serve a record baked into an earlier build.
export const dynamic = "force-dynamic";

// The client bundle receives only the fields the dashboard renders.
function clientView(detail: PerformanceDetail): PerformanceView {
  return {
    summary: detail.summary,
    weeks: detail.weeks,
    gradedGames: detail.gradedGames.map(({ week, spreadResult, totalResult }) => ({ week, spreadResult, totalResult })),
  };
}

export default async function ModelPage() {
  const record = process.env.CFB_UI_TEST_MODE === "1"
    ? { status: "ok" as const, value: mobilePerformanceFixture }
    : await loadPerformanceRecord(
      () => getV5PerformanceDetail(2026),
      error => console.error("V5 cumulative performance query failed", error),
    );
  const title = "2026 V5 cumulative record";
  return (
    <PageShell
      width="wide"
      header={{
        season: publicationScope.season,
        systemName: null,
        updatedAt: null,
        allowedSeasons: publicationScope.allowedSeasons,
      }}
      mainClassName="space-y-4 py-3 sm:py-6"
    >
        <ModelTabs active="record" />
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">2026 · V5</p>
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
        ) : <PerformanceDashboard data={clientView(record.value)} title={title} />}
        <p className="text-xs leading-relaxed text-ink-muted">
          Win rate excludes pushes. A game without an eligible market line does not count as a win or loss.
          Grades use captured selected lines and forecasts use point-in-time inputs.
        </p>
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
