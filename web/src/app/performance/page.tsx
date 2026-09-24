import { getV5Performance, type Performance } from "@/lib/v5";
import { v5PerformanceFixture } from "@/test/fixtures/publication";

export const dynamic = "force-dynamic";

function metric(value: number | null, unit: string): string {
  return value === null ? "—" : `${(value * (unit === "%" ? 100 : 1)).toFixed(1)}${unit}`;
}

function Record({ label, value }: { label: string; value: { win: number; loss: number; push: number } }) {
  return <div><dt className="text-xs text-ink-faint">{label}</dt><dd className="mt-1 font-mono text-lg text-ink">{value.win}–{value.loss}–{value.push}</dd></div>;
}

export default async function PerformancePage() {
  let performance: Performance[] = [];
  let unavailable = false;
  if (process.env.CFB_UI_TEST_MODE === "1") performance = v5PerformanceFixture;
  else {
    try { performance = await getV5Performance(2026); }
    catch (error) { console.error("V5 performance query failed", error); unavailable = true; }
  }
  return <main className="mx-auto w-full max-w-4xl flex-1 space-y-6 px-4 py-8">
    <div><p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">2026 · V5</p><h1 className="mt-1 text-3xl font-bold tracking-tight text-ink">Performance</h1><p className="mt-2 max-w-2xl text-sm text-ink-muted">Every selected V5 forecast contributes to the season view. Replay forecasts were reconstructed after those games; live forecasts were frozen before kickoff.</p></div>
    {unavailable ? <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted">Performance data is temporarily unavailable.</p> :
    <div className="grid gap-4 md:grid-cols-3">{performance.map((row) => <section key={row.classification} className="rounded-xl border border-line bg-surface-card p-5 shadow-sm"><h2 className="text-lg font-semibold capitalize text-ink">{row.classification === "all" ? "Full season" : row.classification}</h2><p className="mt-1 text-xs text-ink-faint">{row.games} selected games · {row.evaluated} evaluated</p><dl className="mt-5 grid grid-cols-2 gap-4"><div><dt className="text-xs text-ink-faint">Margin MAE</dt><dd className="mt-1 font-mono text-lg text-ink">{metric(row.marginMae, " pts")}</dd></div><div><dt className="text-xs text-ink-faint">Total MAE</dt><dd className="mt-1 font-mono text-lg text-ink">{metric(row.totalMae, " pts")}</dd></div><div><dt className="text-xs text-ink-faint">Margin 95% coverage</dt><dd className="mt-1 font-mono text-lg text-ink">{metric(row.marginCoverage95, "%")}</dd></div><div><dt className="text-xs text-ink-faint">Total 95% coverage</dt><dd className="mt-1 font-mono text-lg text-ink">{metric(row.totalCoverage95, "%")}</dd></div><Record label="Eligible spread grades" value={row.spread} /><Record label="Eligible total grades" value={row.total} /></dl></section>)}</div>}
    <p className="text-xs leading-relaxed text-ink-faint">MAE is average absolute forecast error on games with final scores. Coverage is the share of final results inside each forecast’s 95% interval. Market grades appear only when an eligible pre-kickoff line exists; missing lines never count as losses or wins.</p>
  </main>;
}
