import clsx from "clsx";
import type { Lean } from "@/lib/picks-proto";
import { LeanMarker } from "./LeanMarker";

const LABEL = { spread: "Spread", total: "Total" } as const;

/**
 * One lean: bet type, direction marker, the pick with its edge in parentheses,
 * and the model's own prediction on one line under it.
 */
export function LeanPill({ lean, compact = false }: { lean: Lean; compact?: boolean }) {
  const sentence = lean.model ? `model: ${lean.model}` : null;
  return (
    <div className="space-y-0.5">
      <div className="flex items-baseline gap-2">
        <span className="w-12 shrink-0 text-[10px] font-semibold uppercase tracking-wide text-ink-faint">
          {LABEL[lean.kind]}
        </span>
        <span className="flex min-w-0 items-center gap-2">
          <LeanMarker lean={lean} />
          <span className={clsx("min-w-0 truncate font-semibold text-accent-ink", compact ? "text-xs" : "text-sm")}>
            {lean.pick}
          </span>
          <span className="shrink-0 text-xs tabular-nums text-ink-muted" title="Edge: points the model differs from the market">
            ({lean.edge.toFixed(1)})
          </span>
        </span>
      </div>
      {sentence && (
        <p className="truncate pl-[3.75rem] text-[11px] text-ink-muted" title={sentence}>
          {sentence}
        </p>
      )}
    </div>
  );
}
