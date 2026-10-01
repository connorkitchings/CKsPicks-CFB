import type { Performance } from "@/lib/v5";
import type { Tally } from "@/lib/picks-proto";
import { BAR_SCALE_NOTE, RecordBlock } from "./ProtoRecord";

/**
 * This week's record next to the season's live and replay records. Season
 * records are compared to break-even; a single week is too small a sample to
 * judge, so it shows the record and win rate only.
 */
export function ProtoResultsRecord({
  week,
  weekRec,
  performance,
}: {
  week: number;
  weekRec: { spread: Tally; total: Tally };
  performance: Performance[];
}) {
  const live = performance.find((p) => p.classification === "live");
  const replay = performance.find((p) => p.classification === "replay");
  return (
    <section aria-label="Record" className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="grid gap-4 md:grid-cols-3">
        <RecordBlock title={`Week ${week}`} note="this slate · small sample" spread={weekRec.spread} total={weekRec.total} benchmark={false} />
        <RecordBlock title="Season · Live" note="frozen before kickoff" spread={live?.spread ?? null} total={live?.total ?? null} benchmark />
        <RecordBlock title="Season · Replay" note="recalculated after the games" spread={replay?.spread ?? null} total={replay?.total ?? null} benchmark />
      </div>
      <p className="mt-3 text-[11px] text-ink-faint">{BAR_SCALE_NOTE} A single week is not compared to it.</p>
    </section>
  );
}
