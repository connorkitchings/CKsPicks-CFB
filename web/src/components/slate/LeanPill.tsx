import clsx from "clsx";
import type { Lean } from "@/lib/slate";
import { edgeTone, leanDetail } from "@/lib/slate";
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
        {/* The pick is never truncated: a long team name wraps the edge to the next line instead. */}
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5">
          <LeanMarker lean={lean} />
          <span data-pick className={clsx("min-w-0 break-words font-semibold text-accent-ink", compact ? "text-xs" : "text-sm")}>
            {lean.pick}
          </span>
          <span className={clsx("whitespace-nowrap text-xs tabular-nums", edgeTone(lean.edge, lean.kind))} title="Edge: points the model differs from the market">
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
