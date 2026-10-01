import type { Performance } from "@/lib/v5";
import { BREAK_EVEN_PCT, winRatePct } from "@/lib/picks-proto";

type Rec = Performance["spread"];

const MIN = 35;
const MAX = 70;
const pos = (pct: number) => `${Math.min(100, Math.max(0, ((pct - MIN) / (MAX - MIN)) * 100))}%`;

export function RecordCell({ label, rec }: { label: string; rec: Rec }) {
  const rate = winRatePct(rec.win, rec.loss);
  return (
    <div className="rounded-lg bg-surface-inset px-3 py-2.5">
      <div className="flex items-baseline justify-between">
        <span className="text-[10px] font-medium uppercase tracking-wide text-ink-faint">{label}</span>
        <span className="text-xs tabular-nums text-ink-muted">{rate === null ? "—" : `${rate.toFixed(1)}%`}</span>
      </div>
      <div className="mt-0.5 font-mono text-xl font-semibold tabular-nums text-ink">
        {rec.win}–{rec.loss}–{rec.push}
      </div>
      <div
        role="img"
        aria-label={
          rate === null
            ? "No decided games yet"
            : `Win rate ${rate.toFixed(1)} percent against a ${BREAK_EVEN_PCT} percent break-even`
        }
        className="relative mt-2 h-1.5 rounded-full bg-line"
      >
        {rate !== null && (
          <div className="absolute inset-y-0 left-0 rounded-full bg-accent" style={{ width: pos(rate) }} />
        )}
        <div className="absolute -inset-y-1 w-px bg-ink" style={{ left: pos(BREAK_EVEN_PCT) }} />
      </div>
      <div className="relative mt-1 h-3 text-[9px] text-ink-faint">
        <span className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: pos(BREAK_EVEN_PCT) }}>
          break-even {BREAK_EVEN_PCT}%
        </span>
      </div>
    </div>
  );
}

/** A titled pair of spread/total records; shows an empty state when ungraded. */
export function RecordBlock({
  title,
  note,
  spread,
  total,
  emptyText = "No graded games yet.",
}: {
  title: string;
  note: string;
  spread: Rec | null;
  total: Rec | null;
  emptyText?: string;
}) {
  const empty = !spread || !total || spread.win + spread.loss + spread.push + total.win + total.loss + total.push === 0;
  return (
    <div>
      <div className="mb-1.5 flex flex-wrap items-baseline gap-x-2">
        <h3 className="text-xs font-semibold text-ink">{title}</h3>
        <span className="text-[11px] text-ink-faint">{note}</span>
      </div>
      {empty || !spread || !total ? (
        <p className="rounded-lg bg-surface-inset px-3 py-4 text-xs text-ink-faint">{emptyText}</p>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          <RecordCell label="Spread" rec={spread} />
          <RecordCell label="Total" rec={total} />
        </div>
      )}
    </div>
  );
}

/** Separates prospective (frozen before kickoff) results from retrospective replay. */
export function ProtoRecord({ performance }: { performance: Performance[] }) {
  const live = performance.find((p) => p.classification === "live");
  const replay = performance.find((p) => p.classification === "replay");
  return (
    <section aria-label="Record" className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="grid gap-4 md:grid-cols-2">
        <RecordBlock title="Live" note="frozen before kickoff" spread={live?.spread ?? null} total={live?.total ?? null} />
        <RecordBlock title="Replay" note="recalculated after the games; not original picks" spread={replay?.spread ?? null} total={replay?.total ?? null} />
      </div>
    </section>
  );
}
