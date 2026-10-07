import { getV5PerformanceDetail, type PerformanceDetail } from "@/lib/v5";
import { v5PerformanceDetailFixture } from "@/test/fixtures/publication";
import { PerformanceDashboard } from "@/components/PerformanceDashboard";
import { loadPerformanceSections, type SectionResult } from "@/lib/performance-sections";

// Selection changes must not serve a record baked into an earlier build.
export const dynamic = "force-dynamic";

export default async function PerformancePage() {
  let replay: SectionResult<PerformanceDetail>;
  let prospective: SectionResult<PerformanceDetail>;

  if (process.env.CFB_UI_TEST_MODE === "1") {
    replay = { status: "ok", value: v5PerformanceDetailFixture };
    prospective = {
      status: "ok",
      value: { ...v5PerformanceDetailFixture, classification: "prospective", selectedGames: 0, gradedGames: [] },
    };
  } else {
    ({ replay, prospective } = await loadPerformanceSections(
      () => getV5PerformanceDetail(2026, "replay"),
      () => getV5PerformanceDetail(2026, "prospective"),
      (section, error) => console.error(`V5 ${section} performance query failed`, error),
    ));
  }

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 space-y-4 px-4 py-3 sm:py-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">
          2026 · V5
        </p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-3xl">
          Season record & performance
        </h1>
        <p className="mt-1 text-xs text-ink-muted sm:text-sm">
          Separate performance records for selected retrospective replays and explicitly designated prospective V5 runs.
        </p>
        <p role="note" className="mt-1.5 text-xs text-ink-faint">
          Replays are recalculated after games and are not evidence of picks published before kickoff. Prospective records come only from the explicit freeze designation; no latest-run fallback is used.
        </p>
      </div>

      <div className="space-y-8">
        {replay.status === "unavailable" ? (
          <StatusCard title="Selected retrospective replay" message="Performance data is temporarily unavailable." />
        ) : replay.value.selectedGames === 0 ? (
          <StatusCard title="Selected retrospective replay" message="No retrospective replay weeks are selected." />
        ) : replay.value.gradedGames.length === 0 ? (
          <StatusCard title="Selected retrospective replay" message="The selected replay has games, but no grades are available yet." />
        ) : <PerformanceDashboard data={replay.value} title="Selected retrospective replay" />}
        {prospective.status === "unavailable" ? (
          <StatusCard title="Designated prospective V5 performance" message="Prospective performance data is temporarily unavailable." />
        ) : prospective.value.gradedGames.length > 0 ? (
          <PerformanceDashboard data={prospective.value} title="Designated prospective V5 performance" />
        ) : (
          <section aria-labelledby="prospective-empty" className="rounded-xl border border-line bg-surface-card p-5 text-sm text-ink-muted">
            <h2 id="prospective-empty" className="font-semibold text-ink">Designated prospective V5 performance</h2>
            <p className="mt-1">{prospective.value.selectedGames > 0 ? "A prospective run is designated, but it has no graded results yet." : "No prospective V5 week has been explicitly designated."}</p>
          </section>
        )}
      </div>

      <p className="text-xs leading-relaxed text-ink-faint">
        Win rate excludes pushes. A game without an eligible market line does not
        count as a win or loss. Grades use captured selected lines; replays are retrospective evidence.
      </p>
    </main>
  );
}

function StatusCard({ title, message }: { title: string; message: string }) {
  return <section role="status" className="rounded-xl border border-line bg-surface-card p-5 text-sm text-ink-muted">
    <h2 className="font-semibold text-ink">{title}</h2><p className="mt-1">{message}</p>
  </section>;
}
