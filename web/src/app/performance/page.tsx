import { getV5PerformanceDetail } from "@/lib/v5";
import { mobilePerformanceFixture } from "@/test/fixtures/performance-mobile";
import { publicationScope } from "@/lib/publication";
import { Header, Footer } from "@/components/Header";
import { PageHeading } from "@/components/ui/PageHeading";
import { PerformanceDashboard } from "@/components/PerformanceDashboard";
import { loadPerformanceRecord } from "@/lib/performance-sections";

// Selection changes must not serve a record baked into an earlier build.
export const dynamic = "force-dynamic";

export default async function PerformancePage() {
  const record = process.env.CFB_UI_TEST_MODE === "1"
    ? { status: "ok" as const, value: mobilePerformanceFixture }
    : await loadPerformanceRecord(
      () => getV5PerformanceDetail(2026),
      error => console.error("V5 cumulative performance query failed", error),
    );
  const title = "2026 V5 cumulative record";
  return (
    <div className="flex min-h-screen flex-col">
      <Header
        season={publicationScope.season}
        systemName={null}
        updatedAt={null}
        publicationMode={publicationScope.mode}
        allowedSeasons={publicationScope.allowedSeasons}
        wide
      />
      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-5xl flex-1 space-y-4 px-4 py-3 sm:py-6">
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
        ) : <PerformanceDashboard data={record.value} title={title} />}
        <p className="text-xs leading-relaxed text-ink-muted">
          Win rate excludes pushes. A game without an eligible market line does not count as a win or loss.
          Grades use captured selected lines and forecasts use point-in-time inputs.
        </p>
      </main>
      <Footer publicationMode={publicationScope.mode} wide />
    </div>
  );
}

function StatusCard({ title, message }: { title: string; message: string }) {
  return (
    <section role="status" className="rounded-xl border border-line bg-surface-card p-5 text-sm text-ink-muted">
      <h2 className="font-semibold text-ink">{title}</h2>
      <p className="mt-1">{message}</p>
    </section>
  );
}
