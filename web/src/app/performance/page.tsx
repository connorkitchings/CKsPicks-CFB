import { getV5Performance, type Performance } from "@/lib/v5";
import { v5PerformanceFixture } from "@/test/fixtures/publication";

export const dynamic = "force-dynamic";

type Record = Performance["spread"];

function winRate(record: Record): string {
  const decisions = record.win + record.loss;
  return decisions ? `${((record.win / decisions) * 100).toFixed(1)}%` : "—";
}

function Scoreboard({ label, record }: { label: string; record: Record }) {
  return (
    <section className="rounded-xl border border-line bg-surface-card p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-ink">{label}</h2>
      <p className="mt-4 font-mono text-3xl text-ink">{record.win}–{record.loss}–{record.push}</p>
      <p className="mt-1 text-sm text-ink-muted">{winRate(record)} win rate</p>
      <p className="mt-4 text-xs text-ink-faint">Wins · losses · pushes</p>
    </section>
  );
}

export default async function PerformancePage() {
  let performance: Performance[] = [];
  let unavailable = false;
  if (process.env.CFB_UI_TEST_MODE === "1") performance = v5PerformanceFixture;
  else {
    try { performance = await getV5Performance(2026); }
    catch (error) { console.error("V5 performance query failed", error); unavailable = true; }
  }
  const season = performance.find((row) => row.classification === "all");
  return <main className="mx-auto w-full max-w-4xl flex-1 space-y-6 px-4 py-8">
    <div><p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">2026 · V5</p><h1 className="mt-1 text-3xl font-bold tracking-tight text-ink">Season record</h1><p className="mt-2 max-w-2xl text-sm text-ink-muted">Results for every selected V5 forecast in 2026.</p></div>
    {unavailable ? <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted">Performance data is temporarily unavailable.</p> :
    <>{season ? <><p className="text-sm text-ink-muted">{season.games} selected games</p><div className="grid gap-4 sm:grid-cols-2"><Scoreboard label="Spread" record={season.spread} /><Scoreboard label="Total" record={season.total} /></div></> : <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted">No graded V5 results are available yet.</p>}</>}
    <p className="text-xs leading-relaxed text-ink-faint">Win rate excludes pushes. A game without an eligible market line does not count as a win or loss.</p>
  </main>;
}
