import { getV5PerformanceDetail, type PerformanceDetail } from "@/lib/v5";
import { v5PerformanceDetailFixture } from "@/test/fixtures/publication";
import { PerformanceDashboard } from "@/components/PerformanceDashboard";

// Selection changes must not serve a record baked into an earlier build.
export const dynamic = "force-dynamic";

export default async function PerformancePage() {
  let detail: PerformanceDetail | null = null;
  let unavailable = false;

  if (process.env.CFB_UI_TEST_MODE === "1") {
    detail = v5PerformanceDetailFixture;
  } else {
    try {
      detail = await getV5PerformanceDetail(2026);
    } catch (error) {
      console.error("V5 performance query failed", error);
      unavailable = true;
    }
  }

  const hasData = detail !== null && (detail.summary.games > 0 || detail.gradedGames.length > 0);

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 space-y-6 px-4 py-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">
          2026 · V5
        </p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight text-ink">
          Season record & performance
        </h1>
        <p className="mt-2 text-sm text-ink-muted">
          Results, profit/loss unit tracking, and calibration for every selected V5 forecast in 2026.
        </p>
        <p role="note" className="mt-2 text-xs text-ink-faint">
          Weeks 0–4 use retrospective predictions and grades recalculated after the games with the repaired V5 ratings. They were not the picks originally published before kickoff.
        </p>
      </div>

      {unavailable ? (
        <p
          role="status"
          className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted"
        >
          Performance data is temporarily unavailable.
        </p>
      ) : hasData && detail ? (
        <PerformanceDashboard data={detail} />
      ) : (
        <p
          role="status"
          className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted"
        >
          No graded V5 results are available yet.
        </p>
      )}

      <p className="text-xs leading-relaxed text-ink-faint">
        Win rate excludes pushes. A game without an eligible market line does not
        count as a win or loss. Unit profits assume 1.0u flat risk per graded pick at closing/captured line.
      </p>
    </main>
  );
}
