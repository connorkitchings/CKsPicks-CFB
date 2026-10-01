import type { Performance } from "@/lib/v5";
import type { Tally } from "@/lib/picks-proto";
import { RecordBlock } from "./ProtoRecord";

/** This week's record next to the season's live and replay records. */
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
        <RecordBlock title={`Week ${week}`} note="this slate" spread={weekRec.spread} total={weekRec.total} emptyText="Nothing graded this week." />
        <RecordBlock title="Season · Live" note="frozen before kickoff" spread={live?.spread ?? null} total={live?.total ?? null} />
        <RecordBlock title="Season · Replay" note="recalculated after the games" spread={replay?.spread ?? null} total={replay?.total ?? null} />
      </div>
    </section>
  );
}
