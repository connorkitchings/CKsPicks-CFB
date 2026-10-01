import clsx from "clsx";
import type { Lean } from "@/lib/picks-proto";
import { leanDetail } from "@/lib/picks-proto";
import { LeanMarker } from "./LeanMarker";

const LABEL = { spread: "Spread", total: "Total" } as const;

/**
 * One lean: bet type, direction marker, the pick with its edge in parentheses,
 * and one line under it with the model's prediction and the sportsbook the
 * (best available) line came from.
 */
export function LeanPill({ lean, compact = false }: { lean: Lean; compact?: boolean }) {
  const sentence = leanDetail(lean);
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
        <p
          className="truncate pl-[3.75rem] text-[11px] text-ink-muted max-[380px]:overflow-visible max-[380px]:whitespace-normal"
          title={lean.source ? `${sentence} (best available line for the model's side)` : sentence}
        >
          {sentence}
        </p>
      )}
    </div>
  );
}
