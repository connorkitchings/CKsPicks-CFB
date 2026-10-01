import clsx from "clsx";
import type { Lean } from "@/lib/picks-proto";
import { EdgeMeter } from "./EdgeMeter";

const LABEL = { spread: "Spread", total: "Total" } as const;

/** One lean: bet type, the pick, and its edge. Same shape for spread and total. */
export function LeanPill({ lean, compact = false }: { lean: Lean; compact?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-12 shrink-0 text-[10px] font-semibold uppercase tracking-wide text-ink-faint">
        {LABEL[lean.kind]}
      </span>
      <span
        className={clsx(
          "min-w-0 truncate font-semibold text-accent-ink",
          compact ? "text-xs" : "text-sm",
        )}
      >
        {lean.pick}
      </span>
      <span className="ml-auto flex shrink-0 items-center gap-1.5 text-xs tabular-nums text-ink-muted">
        <span>Edge {lean.edge.toFixed(1)}</span>
        <EdgeMeter tier={lean.tier} />
      </span>
    </div>
  );
}
